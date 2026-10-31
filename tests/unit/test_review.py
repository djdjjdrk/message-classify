from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.models import Message, ReviewRecord
from backend.app.service.review import review_message
from backend.app.utils.jwt import create_access_token


def headers(user_id=2):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def messages(db):
    created_at = datetime(2026, 10, 30, 8)
    db.add_all([
        Message(id=1, author_id=1, content="待审核一", created_at=created_at,
                manual_label="normal", predicted_label="spam", prediction_status="success"),
        Message(id=2, author_id=1, content="待审核二", created_at=created_at,
                predicted_label="spam", prediction_status="success"),
        Message(id=3, author_id=1, content="已通过", review_status="approved"),
        Message(id=4, author_id=1, content="已驳回", review_status="rejected"),
        Message(id=5, author_id=1, content="已删除", deleted_at=created_at),
    ])
    db.commit()


def test_pending_list_is_admin_only_filtered_and_paginated(client, messages):
    assert client.get("/api/v1/reviews/pending").status_code == 401
    assert client.get("/api/v1/reviews/pending", headers=headers(1)).status_code == 403
    for page, expected_id in [(1, 2), (2, 1)]:
        response = client.get(
            "/api/v1/reviews/pending", headers=headers(), params={"page": page, "page_size": 1},
        )
        data = response.json()["data"]
        assert data["total"] == 2
        assert data["list"][0]["id"] == expected_id
    data = client.get("/api/v1/reviews/pending", headers=headers(), params={"page": 2, "page_size": 1}).json()["data"]
    assert data["list"][0]["effective_label"] == "normal"
    assert data["list"][0]["label_source"] == "manual"


@pytest.mark.parametrize("decision,comment", [("approved", ""), ("rejected", "  包含广告  ")])
def test_review_changes_visibility_and_records_evidence(client, db, messages, decision, comment):
    response = client.post(
        "/api/v1/reviews/messages/1", headers=headers(),
        json={"decision": decision, "comment": comment},
    )
    assert response.json()["code"] == 200
    message = db.get(Message, 1)
    db.refresh(message)
    assert message.review_status == decision
    assert message.manual_label == "normal"
    assert message.predicted_label == "spam"
    record = db.scalar(select(ReviewRecord).where(ReviewRecord.message_id == 1))
    assert (record.reviewer_id, record.review_source, record.previous_status) == (2, "manual", "pending")
    assert (record.decision, record.label_snapshot) == (decision, "normal")
    if decision == "rejected":
        assert record.comment == "包含广告"
    else:
        assert record.comment is None
    public = client.get("/api/v1/messages/public", headers=headers(1)).json()["data"]["list"]
    public_ids = []
    for item in public:
        public_ids.append(item["id"])
    assert (1 in public_ids) == (decision == "approved")
    mine = client.get("/api/v1/messages/mine", headers=headers(1)).json()["data"]["list"]
    for item in mine:
        if item["id"] == 1:
            assert item["review_status"] == decision
            break
    else:
        pytest.fail("审核后作者仍应能查看自己的留言")
    duplicate = client.post("/api/v1/reviews/messages/1", headers=headers(), json={"decision": decision, "comment": comment})
    assert duplicate.json()["code"] == 409
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 1
    history = client.get("/api/v1/reviews/history", headers=headers()).json()["data"]
    assert history["total"] == 1
    assert history["list"][0]["reviewer_username"] == "admin"
    assert history["list"][0]["label_snapshot"] == "normal"


@pytest.mark.parametrize("payload", [
    {}, {"decision": "pending"}, {"decision": "rejected"},
    {"decision": "rejected", "comment": "   "},
    {"decision": "approved", "comment": "字" * 501},
    {"decision": "approved", "reviewer_id": 1},
])
def test_invalid_review_does_not_write(client, db, messages, payload):
    response = client.post("/api/v1/reviews/messages/1", headers=headers(), json=payload)
    assert response.status_code == 422
    assert db.get(Message, 1).review_status == "pending"
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 0


def test_review_authorization_and_deleted_or_finished_messages(client, db, messages):
    for auth, status in [({}, 401), (headers(1), 403)]:
        assert client.post("/api/v1/reviews/messages/1", headers=auth, json={"decision": "approved"}).status_code == status
        assert client.get("/api/v1/reviews/history", headers=auth).status_code == status
    for message_id, code in [(3, 409), (4, 409), (5, 404), (999, 404)]:
        response = client.post(f"/api/v1/reviews/messages/{message_id}", headers=headers(), json={"decision": "approved"})
        assert response.json()["code"] == code
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 0


def test_review_write_failure_rolls_back_status_and_history(db, messages, monkeypatch):
    original_flush = db.flush

    def fail_flush(*args, **kwargs):
        original_flush(*args, **kwargs)
        raise SQLAlchemyError("模拟审核记录保存失败")

    with monkeypatch.context() as patch:
        patch.setattr(db, "flush", fail_flush)
        with pytest.raises(SQLAlchemyError):
            review_message(db, message_id=1, reviewer_id=2, decision="approved", comment=None)
    assert db.get(Message, 1).review_status == "pending"
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 0
