from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.models import AnnotationRecord, Message, User
from backend.app.service.annotation import annotate_message
from backend.app.utils.jwt import create_access_token


def headers(user_id=2):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def message(db):
    message = Message(
        id=1, author_id=1, content="需要标注的留言", predicted_label="spam",
        prediction_status="success", predicted_probability=0.9,
        model_name="test-model", prediction_explanation=[{"feature": "测试", "weight": 0.3}],
        review_status="pending",
    )
    db.add(message)
    db.commit()
    return message


def test_annotation_saves_operator_effective_previous_label_and_preserves_other_fields(client, db, message):
    old_created_at = message.created_at
    response = client.post(
        "/api/v1/classification/messages/1/annotations", headers=headers(),
        json={"label": "normal", "reason": "  校园日常讨论\n不是广告  "},
    )
    assert response.json()["code"] == 200
    assert response.json()["data"] == {"message_id": 1, "manual_label": "normal", "changed": True}
    db.refresh(message)
    assert message.manual_label == "normal"
    assert message.content == "需要标注的留言"
    assert message.author_id == 1
    assert message.created_at == old_created_at
    assert message.updated_at >= old_created_at
    assert message.review_status == "pending"
    assert message.predicted_label == "spam"
    assert message.prediction_status == "success"
    assert message.predicted_probability == 0.9
    assert message.model_name == "test-model"
    assert message.prediction_explanation == [{"feature": "测试", "weight": 0.3}]
    record = db.scalar(select(AnnotationRecord))
    assert (record.message_id, record.annotator_id) == (1, 2)
    assert (record.previous_label, record.new_label) == ("spam", "normal")
    assert record.reason == "校园日常讨论\n不是广告"
    assert record.created_at is not None
    normal = client.get("/api/v1/classification/messages", headers=headers(), params={"category": "normal"})
    spam = client.get("/api/v1/classification/messages", headers=headers(), params={"category": "spam"})
    assert normal.json()["data"]["total"] == 1
    assert normal.json()["data"]["list"][0]["label_source"] == "manual"
    assert spam.json()["data"]["total"] == 0
    assert client.get("/api/v1/messages/public", headers=headers(1)).json()["data"]["total"] == 0


@pytest.mark.parametrize("prediction_status,previous_label", [
    ("success", "spam"), ("pending", None), ("error", None),
    ("no_model", None), ("no_features", None),
])
def test_first_confirmation_records_only_valid_previous_classification(client, db, message, prediction_status, previous_label):
    message.prediction_status = prediction_status
    db.commit()
    response = client.post(
        "/api/v1/classification/messages/1/annotations", headers=headers(),
        json={"label": "spam", "reason": " \n "},
    )
    assert response.json()["data"]["changed"] is True
    record = db.scalar(select(AnnotationRecord))
    assert record.previous_label == previous_label
    assert record.new_label == "spam"
    assert record.reason is None


def test_duplicate_is_noop_but_corrections_keep_full_history(client, db, message):
    for label, changed in [("normal", True), ("normal", False), ("spam", True)]:
        response = client.post(
            "/api/v1/classification/messages/1/annotations", headers=headers(), json={"label": label},
        )
        assert response.json()["data"]["changed"] is changed
        if not changed:
            assert db.scalar(select(func.count()).select_from(AnnotationRecord)) == 1
    records = db.scalars(select(AnnotationRecord).order_by(AnnotationRecord.id)).all()
    assert len(records) == 2
    assert (records[0].previous_label, records[0].new_label) == ("spam", "normal")
    assert (records[1].previous_label, records[1].new_label) == ("normal", "spam")


@pytest.mark.parametrize("payload", [
    {}, {"label": None}, {"label": "unclassified"}, {"label": "NORMAL"},
    {"label": ""}, {"label": 1}, {"label": "normal", "reason": "字" * 501},
    {"label": "normal", "annotator_id": 1}, {"label": "normal", "review_status": "approved"},
    {"label": "normal", "previous_label": "normal"},
])
def test_invalid_or_forged_annotation_does_not_write(client, db, message, payload):
    response = client.post("/api/v1/classification/messages/1/annotations", headers=headers(), json=payload)
    assert response.status_code == 422
    db.refresh(message)
    assert message.manual_label is None
    assert db.scalar(select(func.count()).select_from(AnnotationRecord)) == 0


@pytest.mark.parametrize("auth,status", [
    ({}, 401), ({"Authorization": "Bearer invalid"}, 401),
    (headers(999), 401), (headers(1), 403),
])
def test_writes_and_history_require_current_admin(client, db, message, auth, status):
    path = "/api/v1/classification/messages/1/annotations"
    assert client.post(path, headers=auth, json={"label": "normal"}).status_code == status
    assert client.get(path, headers=auth).status_code == status
    assert db.scalar(select(func.count()).select_from(AnnotationRecord)) == 0


def test_role_demotion_blocks_existing_token(client, db, message):
    auth = headers()
    db.get(User, 2).role = "student"
    db.commit()
    path = "/api/v1/classification/messages/1/annotations"
    assert client.post(path, headers=auth, json={"label": "normal"}).status_code == 403
    assert client.get(path, headers=auth).status_code == 403


@pytest.mark.parametrize("message_id", [1, 999])
def test_missing_or_deleted_message_cannot_be_annotated_or_read(client, db, message, message_id):
    message.deleted_at = datetime(2026, 10, 31)
    db.commit()
    path = f"/api/v1/classification/messages/{message_id}/annotations"
    assert client.post(path, headers=headers(), json={"label": "normal"}).json()["code"] == 404
    assert client.get(path, headers=headers()).json()["code"] == 404
    assert db.scalar(select(func.count()).select_from(AnnotationRecord)) == 0


def test_history_is_paginated_stable_scoped_and_does_not_leak_passwords(client, db, message):
    db.add(Message(id=2, author_id=1, content="其他留言"))
    db.flush()
    for record_id, message_id in [(1, 1), (2, 1), (3, 2)]:
        db.add(AnnotationRecord(
            id=record_id, message_id=message_id, annotator_id=2,
            previous_label=None, new_label="normal", created_at=datetime(2026, 10, 31, 8),
        ))
    db.commit()
    for page, expected_ids in [(1, [2]), (2, [1]), (3, [])]:
        response = client.get(
            "/api/v1/classification/messages/1/annotations", headers=headers(),
            params={"page": page, "page_size": 1},
        )
        data = response.json()["data"]
        assert data["total"] == 2
        actual_ids = []
        for record in data["list"]:
            actual_ids.append(record["id"])
            assert record["annotator_id"] == 2
            assert record["annotator_username"] == "admin"
            assert record["annotator_nickname"] == "管理员"
            assert "password_hash" not in record
        assert actual_ids == expected_ids


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_history_rejects_bad_pagination(client, message, params):
    response = client.get("/api/v1/classification/messages/1/annotations", headers=headers(), params=params)
    assert response.status_code == 422


def test_empty_history(client, message):
    response = client.get("/api/v1/classification/messages/1/annotations", headers=headers())
    assert response.json()["data"] == {"list": [], "total": 0}


def test_history_write_failure_rolls_back_label_and_allows_retry(db, message, monkeypatch):
    original_flush = db.flush

    def fail_history_write(*args, **kwargs):
        original_flush(*args, **kwargs)
        raise SQLAlchemyError("模拟历史写入失败")

    with monkeypatch.context() as patch:
        patch.setattr(db, "flush", fail_history_write)
        with pytest.raises(SQLAlchemyError):
            annotate_message(db, message_id=1, annotator_id=2, label="normal", reason=None)
    db.refresh(message)
    assert message.manual_label is None
    assert db.scalar(select(func.count()).select_from(AnnotationRecord)) == 0
    assert annotate_message(db, message_id=1, annotator_id=2, label="normal", reason=None)
    assert db.scalar(select(func.count()).select_from(AnnotationRecord)) == 1
