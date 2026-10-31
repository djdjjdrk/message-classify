from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.models import Message, User
from backend.app.service.message import delete_message
from backend.app.utils.jwt import create_access_token


def auth_headers(user_id=1):
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def message(db):
    message = Message(
        id=50, author_id=1, content="删除检索关键词留言", review_status="approved",
        manual_label="normal", created_at=datetime(2026, 10, 30, 8, 0),
    )
    db.add(message)
    db.commit()
    return message


@pytest.mark.parametrize("review_status", ["pending", "approved", "rejected"])
def test_owner_soft_deletes_message_and_preserves_original_data(client, db, message, review_status):
    message.review_status = review_status
    db.commit()
    response = client.delete("/api/v1/messages/50", headers=auth_headers())
    assert response.json() == {"code": 200, "message": "留言已删除", "data": None}
    db.refresh(message)
    assert message.deleted_at is not None
    assert message.content == "删除检索关键词留言"
    assert message.author_id == 1
    assert message.review_status == review_status
    assert message.manual_label == "normal"
    assert message.created_at == datetime(2026, 10, 30, 8, 0)
    assert db.scalar(select(func.count()).select_from(Message)) == 1


def test_deletion_removes_message_from_both_lists_and_search_totals(client, message):
    headers = auth_headers()
    for scope in ("mine", "public"):
        response = client.get(f"/api/v1/messages/{scope}", headers=headers)
        assert response.json()["data"]["total"] == 1
    client.delete("/api/v1/messages/50", headers=headers)
    for scope in ("mine", "public"):
        for keyword in ("", "检索关键词"):
            response = client.get(
                f"/api/v1/messages/{scope}", headers=headers, params={"keyword": keyword},
            )
            assert response.json()["data"] == {"list": [], "total": 0}


@pytest.mark.parametrize("review_status", ["pending", "approved", "rejected"])
def test_admin_can_delete_another_users_message(client, db, message, review_status):
    message.review_status = review_status
    db.commit()
    response = client.delete("/api/v1/messages/50", headers=auth_headers(2))
    assert response.json()["code"] == 200
    db.refresh(message)
    assert message.deleted_at is not None


def test_student_cannot_delete_other_users_message_or_forge_role(client, db, message):
    message.author_id = 2
    db.commit()
    response = client.request(
        "DELETE", "/api/v1/messages/50", headers=auth_headers(),
        params={"role": "admin", "author_id": 1},
        json={"role": "admin", "author_id": 1},
    )
    assert response.json()["code"] == 403
    assert response.json()["message"] == "只能删除自己发布的留言"
    db.refresh(message)
    assert message.deleted_at is None


def test_delete_permission_uses_current_database_role(client, db, message):
    headers = auth_headers(2)
    admin = db.get(User, 2)
    admin.role = "student"
    db.commit()
    response = client.delete("/api/v1/messages/50", headers=headers)
    assert response.json()["code"] == 403
    db.refresh(message)
    assert message.deleted_at is None


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}, auth_headers(999)])
def test_delete_requires_existing_logged_in_user(client, db, message, headers):
    response = client.delete("/api/v1/messages/50", headers=headers)
    assert response.status_code == 401
    db.refresh(message)
    assert message.deleted_at is None


def test_missing_or_repeated_deletion_does_not_change_original_timestamp(client, db, message):
    missing = client.delete("/api/v1/messages/9999", headers=auth_headers())
    assert missing.json()["code"] == 404
    client.delete("/api/v1/messages/50", headers=auth_headers())
    db.refresh(message)
    deleted_at = message.deleted_at
    repeated = client.delete("/api/v1/messages/50", headers=auth_headers())
    assert repeated.json()["code"] == 404
    db.refresh(message)
    assert message.deleted_at == deleted_at


@pytest.mark.parametrize("message_id", [0, -1, "invalid", 2**63])
def test_delete_rejects_invalid_ids(client, message_id):
    response = client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers())
    assert response.status_code == 422


def test_database_failure_rolls_back_deletion(db, message, monkeypatch):
    user = db.get(User, 1)

    def fail_commit():
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError):
        delete_message(db, message_id=message.id, user=user)
    db.refresh(message)
    assert message.deleted_at is None
