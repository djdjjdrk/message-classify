from datetime import datetime, timedelta

import pytest

from backend.app.models import Message
from backend.app.utils.jwt import create_access_token


def auth_headers(user_id=1):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def messages(db):
    created_at = datetime(2026, 10, 30, 8, 0)
    db.add_all([
        Message(id=10, author_id=1, content="较早的已通过留言", review_status="approved", created_at=created_at - timedelta(days=1)),
        Message(id=11, author_id=1, content="待审核留言", review_status="pending", created_at=created_at),
        Message(id=12, author_id=1, content="已驳回留言", review_status="rejected", created_at=created_at),
        Message(id=13, author_id=1, content="已删除留言", created_at=created_at, deleted_at=created_at),
        Message(id=20, author_id=2, content="其他账号的留言", created_at=created_at + timedelta(days=1)),
    ])
    db.commit()


@pytest.mark.parametrize("user_id,expected_ids", [(1, [12, 11, 10]), (2, [20])])
def test_mine_isolates_accounts_and_excludes_deleted_messages(client, messages, user_id, expected_ids):
    response = client.get(
        "/api/v1/messages/mine", headers=auth_headers(user_id),
        params={"author_id": 2 if user_id == 1 else 1},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == len(expected_ids)
    assert [message["id"] for message in data["list"]] == expected_ids
    assert all(message["author_id"] == user_id for message in data["list"])
    if user_id == 1:
        assert {message["review_status"] for message in data["list"]} == {"pending", "approved", "rejected"}


def test_mine_pagination_has_stable_order_and_matching_total(client, messages):
    pages = [client.get(
        "/api/v1/messages/mine", headers=auth_headers(),
        params={"page": page, "page_size": 2},
    ).json()["data"] for page in (1, 2, 3)]
    assert [[message["id"] for message in page["list"]] for page in pages] == [[12, 11], [10], []]
    assert all(page["total"] == 3 for page in pages)


def test_mine_empty_list(client):
    response = client.get("/api/v1/messages/mine", headers=auth_headers())
    assert response.json()["data"] == {"list": [], "total": 0}


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page": "invalid"},
    {"page_size": 0}, {"page_size": 101},
])
def test_mine_rejects_invalid_pagination(client, params):
    response = client.get("/api/v1/messages/mine", headers=auth_headers(), params=params)
    assert response.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}, auth_headers(999)])
def test_mine_requires_existing_logged_in_user(client, headers):
    response = client.get("/api/v1/messages/mine", headers=headers)
    assert response.status_code == 401
    assert response.json()["data"] is None
