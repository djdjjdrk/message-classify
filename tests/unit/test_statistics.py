from datetime import datetime

import pytest

from backend.app.models import Message
from backend.app.utils.jwt import create_access_token


PATH = "/api/v1/statistics"
ADMIN = {"Authorization": f"Bearer {create_access_token(2)}"}


def test_empty_statistics_returns_zero_counts(client):
    response = client.get(PATH, headers=ADMIN)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "total": 0,
        "classification": {"normal": 0, "spam": 0, "unclassified": 0},
        "review": {"pending": 0, "approved": 0, "rejected": 0},
    }


def test_statistics_matches_classification_filters_and_excludes_deleted(client, db):
    db.add_all([
        Message(author_id=1, content="正常预测", prediction_status="success", predicted_label="normal", review_status="approved"),
        Message(author_id=2, content="垃圾预测", prediction_status="success", predicted_label="spam", review_status="rejected"),
        Message(author_id=1, content="人工正常优先", manual_label="normal", prediction_status="success", predicted_label="spam"),
        Message(author_id=2, content="人工垃圾优先", manual_label="spam", prediction_status="success", predicted_label="normal"),
        Message(author_id=1, content="预测失败仍用人工", manual_label="normal", prediction_status="error", review_status="approved"),
        Message(author_id=1, content="预测成功缺少标签", prediction_status="success"),
        Message(author_id=1, content="已删除", manual_label="spam", review_status="approved", deleted_at=datetime(2026, 11, 1)),
        *[Message(author_id=1, content=f"非成功预测：{status}", prediction_status=status, predicted_label="spam")
          for status in ("pending", "error", "no_model", "no_features")],
    ])
    db.commit()
    data = client.get(PATH, headers=ADMIN).json()["data"]
    assert data == {
        "total": 10,
        "classification": {"normal": 3, "spam": 2, "unclassified": 5},
        "review": {"pending": 7, "approved": 2, "rejected": 1},
    }
    assert sum(data["classification"].values()) == data["total"]
    assert sum(data["review"].values()) == data["total"]
    for category, count in data["classification"].items():
        result = client.get("/api/v1/classification/messages", headers=ADMIN, params={"category": category}).json()["data"]
        assert result["total"] == count


def test_statistics_reflects_publish_annotation_review_and_soft_delete(client):
    message_id = client.post("/api/v1/messages", headers=ADMIN, json={"content": "校园讨论"}).json()["data"]["id"]
    initial = client.get(PATH, headers=ADMIN).json()["data"]
    assert initial["total"] == initial["classification"]["unclassified"] == initial["review"]["pending"] == 1

    annotated = client.post(f"/api/v1/classification/messages/{message_id}/annotations", headers=ADMIN, json={"label": "normal"})
    assert annotated.json()["code"] == 200
    reviewed = client.post(f"/api/v1/reviews/messages/{message_id}", headers=ADMIN, json={"decision": "approved"})
    assert reviewed.json()["code"] == 200
    updated = client.get(PATH, headers=ADMIN).json()["data"]
    assert updated["total"] == updated["classification"]["normal"] == updated["review"]["approved"] == 1
    assert updated["classification"]["unclassified"] == updated["review"]["pending"] == 0

    client.delete(f"/api/v1/messages/{message_id}", headers=ADMIN)
    deleted = client.get(PATH, headers=ADMIN).json()["data"]
    assert deleted["total"] == sum(deleted["classification"].values()) == sum(deleted["review"].values()) == 0


@pytest.mark.parametrize("user_id,expected", [(None, 401), (1, 403)])
def test_statistics_requires_admin(client, user_id, expected):
    headers = {} if user_id is None else {"Authorization": f"Bearer {create_access_token(user_id)}"}
    response = client.get(PATH, headers=headers)
    assert response.json()["code"] == expected
    assert response.json()["data"] is None
