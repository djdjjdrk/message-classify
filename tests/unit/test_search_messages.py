from datetime import datetime

import pytest

from backend.app.models import Message
from backend.app.utils.jwt import create_access_token


HEADERS = {"Authorization": f"Bearer {create_access_token(1)}"}


@pytest.fixture
def searchable_messages(db):
    created_at = datetime(2026, 10, 30, 8, 0)
    db.add_all([
        Message(id=10, author_id=1, content="图书馆一起自习", review_status="approved", created_at=created_at),
        Message(id=11, author_id=1, content="图书馆借书", review_status="pending", created_at=created_at),
        Message(id=12, author_id=1, content="食堂意见", review_status="rejected", created_at=created_at),
        Message(id=13, author_id=1, content="图书馆已删除", review_status="approved", deleted_at=created_at),
        Message(id=20, author_id=2, content="图书馆开放时间", review_status="approved", created_at=created_at),
        Message(id=21, author_id=2, content="图书馆未审核", review_status="pending", created_at=created_at),
        Message(id=22, author_id=2, content="图书馆驳回", review_status="rejected", created_at=created_at),
        Message(id=23, author_id=2, content="图书馆删除", review_status="approved", deleted_at=created_at),
        Message(id=24, author_id=2, content="操场跑步", review_status="approved", created_at=created_at),
    ])
    db.commit()


@pytest.mark.parametrize("scope,expected", [("mine", [11, 10]), ("public", [20, 10])])
def test_search_filters_content_without_expanding_visibility(client, searchable_messages, scope, expected):
    response = client.get(
        f"/api/v1/messages/{scope}", headers=HEADERS,
        params={"keyword": "  图书馆 \n", "author_id": 2, "review_status": "pending"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert [message["id"] for message in data["list"]] == expected
    assert data["total"] == 2


@pytest.mark.parametrize("scope,expected", [("mine", [11, 10]), ("public", [20, 10])])
def test_search_pagination_preserves_filtered_total_and_order(client, searchable_messages, scope, expected):
    pages = [client.get(
        f"/api/v1/messages/{scope}", headers=HEADERS,
        params={"keyword": "图书馆", "page": page, "page_size": 1},
    ).json()["data"] for page in (1, 2, 3)]
    assert [[message["id"] for message in page["list"]] for page in pages] == [[expected[0]], [expected[1]], []]
    assert all(page["total"] == 2 for page in pages)


@pytest.mark.parametrize("scope,expected", [("mine", [12, 11, 10]), ("public", [24, 20, 10])])
@pytest.mark.parametrize("keyword", ["", " \t\u3000 "])
def test_empty_search_restores_unfiltered_list(client, searchable_messages, scope, expected, keyword):
    response = client.get(f"/api/v1/messages/{scope}", headers=HEADERS, params={"keyword": keyword})
    data = response.json()["data"]
    assert [message["id"] for message in data["list"]] == expected
    assert data["total"] == len(expected)


@pytest.mark.parametrize("scope", ["mine", "public"])
def test_search_without_matches_returns_empty_result(client, searchable_messages, scope):
    response = client.get(f"/api/v1/messages/{scope}", headers=HEADERS, params={"keyword": "不存在的正文"})
    assert response.json()["data"] == {"list": [], "total": 0}


@pytest.mark.parametrize("scope", ["mine", "public"])
@pytest.mark.parametrize("keyword", ["%", "_", "/", "\\", "' OR 1=1 --"])
def test_search_treats_special_characters_as_literal_text(client, db, scope, keyword):
    matched = Message(author_id=1, content=f"正文包含{keyword}符号", review_status="approved")
    db.add_all([matched, Message(author_id=1, content="普通正文", review_status="approved")])
    db.commit()
    response = client.get(f"/api/v1/messages/{scope}", headers=HEADERS, params={"keyword": keyword})
    data = response.json()["data"]
    assert data["total"] == 1
    assert [message["id"] for message in data["list"]] == [matched.id]


@pytest.mark.parametrize("scope", ["mine", "public"])
def test_search_keyword_length_is_validated(client, db, scope):
    db.add(Message(author_id=1, content="字" * 200, review_status="approved"))
    db.commit()
    accepted = client.get(f"/api/v1/messages/{scope}", headers=HEADERS, params={"keyword": "字" * 200})
    assert accepted.json()["data"]["total"] == 1
    rejected = client.get(f"/api/v1/messages/{scope}", headers=HEADERS, params={"keyword": "字" * 201})
    assert rejected.status_code == 422
