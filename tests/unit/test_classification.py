from datetime import datetime

import pytest
from sqlalchemy import select

from backend.app.models import Message, User
from backend.app.utils.jwt import create_access_token


def admin_headers():
    token = create_access_token(2)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def classification_messages(db):
    messages = [
        Message(id=11, author_id=1, content="待预测留言"),
        Message(id=12, author_id=2, content="模型正常", predicted_label="normal", prediction_status="success", review_status="rejected"),
        Message(id=13, author_id=1, content="模型垃圾", predicted_label="spam", prediction_status="success", review_status="approved"),
        Message(id=14, author_id=1, content="人工正常覆盖模型垃圾", manual_label="normal", predicted_label="spam", prediction_status="success"),
        Message(id=15, author_id=2, content="人工垃圾覆盖模型正常", manual_label="spam", predicted_label="normal", prediction_status="success"),
        Message(id=16, author_id=1, content="预测失败但有人工标签", manual_label="normal", prediction_status="error"),
        Message(id=17, author_id=2, content="模型不存在", prediction_status="no_model"),
        Message(id=18, author_id=1, content="失败时遗留的预测标签", predicted_label="normal", prediction_status="error"),
        Message(id=19, author_id=2, content="预测成功但标签缺失", prediction_status="success"),
        Message(id=20, author_id=1, content="已删除分类记录", manual_label="normal", deleted_at=datetime(2026, 10, 30)),
        Message(id=21, author_id=1, content="没有有效特征", prediction_status="no_features"),
        Message(id=22, author_id=2, content="未预测时遗留的标签", predicted_label="spam"),
    ]
    for message in messages:
        message.created_at = datetime(2026, 10, 30, 8, 0)
        db.add(message)
    db.commit()


@pytest.mark.parametrize("category,expected_ids", [
    ("all", [22, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11]),
    ("unclassified", [22, 21, 19, 18, 17, 11]),
    ("normal", [16, 14, 12]),
    ("spam", [15, 13]),
])
def test_classification_filter_uses_manual_priority_and_valid_predictions(client, classification_messages, category, expected_ids):
    response = client.get(
        "/api/v1/classification/messages", headers=admin_headers(),
        params={"category": category, "page_size": 100},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    actual_ids = []
    for message in data["list"]:
        actual_ids.append(message["id"])
    assert actual_ids == expected_ids
    assert data["total"] == len(expected_ids)


def test_classification_effective_label_source_and_read_only_behavior(client, db, classification_messages):
    before = {}
    for message in db.scalars(select(Message)):
        before[message.id] = (
            message.content, message.predicted_label, message.manual_label,
            message.prediction_status, message.review_status, message.updated_at, message.deleted_at,
        )
    expected = {
        11: (None, "unclassified"),
        12: ("normal", "model"),
        13: ("spam", "model"),
        14: ("normal", "manual"),
        15: ("spam", "manual"),
        16: ("normal", "manual"),
        17: (None, "unclassified"),
        18: (None, "unclassified"),
        19: (None, "unclassified"),
        21: (None, "unclassified"),
        22: (None, "unclassified"),
    }
    response = client.get(
        "/api/v1/classification/messages", headers=admin_headers(), params={"page_size": 100},
    )
    for message in response.json()["data"]["list"]:
        assert (message["effective_label"], message["label_source"]) == expected[message["id"]]
        assert message["author_nickname"] in ("学生", "管理员")
        assert "password_hash" not in message
    for message in db.scalars(select(Message)):
        db.refresh(message)
        after = (
            message.content, message.predicted_label, message.manual_label,
            message.prediction_status, message.review_status, message.updated_at, message.deleted_at,
        )
        assert after == before[message.id]


def test_classification_pagination_keeps_filtered_total_and_stable_order(client, classification_messages):
    actual_pages = []
    for page in (1, 2, 3):
        response = client.get(
            "/api/v1/classification/messages", headers=admin_headers(),
            params={"category": "normal", "page": page, "page_size": 2},
        )
        data = response.json()["data"]
        actual_ids = []
        for message in data["list"]:
            actual_ids.append(message["id"])
        actual_pages.append(actual_ids)
        assert data["total"] == 3
    assert actual_pages == [[16, 14], [12], []]


@pytest.mark.parametrize("category", ["all", "unclassified", "normal", "spam"])
def test_classification_empty_list(client, category):
    response = client.get(
        "/api/v1/classification/messages", headers=admin_headers(), params={"category": category},
    )
    assert response.json()["data"] == {"list": [], "total": 0}


@pytest.mark.parametrize("params", [
    {"category": "approved"}, {"category": ""}, {"category": "NORMAL"},
    {"page": 0}, {"page_size": 101},
])
def test_classification_rejects_invalid_filters_and_pagination(client, params):
    response = client.get("/api/v1/classification/messages", headers=admin_headers(), params=params)
    assert response.status_code == 422


@pytest.mark.parametrize("headers,status_code", [
    ({}, 401),
    ({"Authorization": "Bearer invalid"}, 401),
    ({"Authorization": f"Bearer {create_access_token(999)}"}, 401),
    ({"Authorization": f"Bearer {create_access_token(1)}"}, 403),
])
def test_classification_requires_current_admin_identity(client, classification_messages, headers, status_code):
    response = client.get(
        "/api/v1/classification/messages", headers=headers, params={"role": "admin"},
    )
    assert response.status_code == status_code
    assert response.json()["data"] is None


def test_classification_checks_role_changes_on_each_request(client, db, classification_messages):
    headers = admin_headers()
    user = db.get(User, 2)
    user.role = "student"
    db.commit()
    response = client.get("/api/v1/classification/messages", headers=headers)
    assert response.status_code == 403
