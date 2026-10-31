from datetime import datetime, timedelta

import pytest

from backend.app.models import Message
from backend.app.utils.jwt import create_access_token


def auth_headers(user_id=1):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def public_message_data(db):
    created_at = datetime(2026, 10, 30, 8, 0)
    db.add_all([
        Message(id=10, author_id=1, content="较早的公开留言", review_status="approved", created_at=created_at - timedelta(days=1)),
        Message(id=11, author_id=2, content="其他用户的公开留言", review_status="approved", created_at=created_at),
        Message(id=12, author_id=1, content="同一时间按编号排序", review_status="approved", created_at=created_at),
        Message(id=13, author_id=2, content="已通过但被删除", review_status="approved", deleted_at=created_at),
        Message(id=14, author_id=2, content="预测正常但尚未审核", predicted_label="normal", review_status="pending"),
        Message(id=15, author_id=2, content="已驳回的留言", review_status="rejected"),
    ])
    db.commit()


@pytest.mark.parametrize("user_id", [1, 2])
def test_public_returns_only_approved_undeleted_messages_from_all_authors(client, db, public_message_data, user_id):
    response = client.get(
        "/api/v1/messages/public", headers=auth_headers(user_id),
        params={"review_status": "pending", "author_id": 2},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert [message["id"] for message in data["list"]] == [12, 11, 10]
    assert [message["author_nickname"] for message in data["list"]] == ["学生", "管理员", "学生"]
    for message in data["list"]:
        assert set(message) == {"id", "content", "author_nickname", "created_at", "can_delete"}
        if user_id == 1 and message["id"] == 11:
            assert message["can_delete"] is False
        else:
            assert message["can_delete"] is True
    assert db.get(Message, 14).review_status == "pending"


def test_public_pagination_and_total_share_visibility_rules(client, public_message_data):
    pages = [client.get(
        "/api/v1/messages/public", headers=auth_headers(),
        params={"page": page, "page_size": 2},
    ).json()["data"] for page in (1, 2, 3)]
    assert [[message["id"] for message in page["list"]] for page in pages] == [[12, 11], [10], []]
    assert all(page["total"] == 3 for page in pages)


def test_public_empty_list(client):
    response = client.get("/api/v1/messages/public", headers=auth_headers())
    assert response.json()["data"] == {"list": [], "total": 0}


def test_public_refresh_excludes_messages_after_rejection_or_deletion(client, db, public_message_data):
    db.get(Message, 12).review_status = "rejected"
    db.get(Message, 11).deleted_at = datetime(2026, 10, 30)
    db.commit()
    response = client.get("/api/v1/messages/public", headers=auth_headers())
    assert response.json()["data"]["total"] == 1
    assert [message["id"] for message in response.json()["data"]["list"]] == [10]


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page": "invalid"},
    {"page_size": 0}, {"page_size": 101},
])
def test_public_rejects_invalid_pagination(client, params):
    response = client.get("/api/v1/messages/public", headers=auth_headers(), params=params)
    assert response.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}, auth_headers(999)])
def test_public_requires_existing_logged_in_user(client, headers):
    response = client.get("/api/v1/messages/public", headers=headers)
    assert response.status_code == 401
