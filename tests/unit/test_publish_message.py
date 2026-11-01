import pytest
from sqlalchemy import func, select

from backend.app.models import Message
from backend.app.utils.jwt import create_access_token


def auth_headers(user_id=1):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.mark.parametrize("user_id", [1, 2])
def test_publish_saves_author_content_and_pending_review_without_model(client, db, user_id, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.service.message.settings.MODEL_PATH", str(tmp_path / "missing.joblib"))
    response = client.post(
        "/api/v1/messages", headers=auth_headers(user_id),
        json={"content": "  今晚图书馆有人一起自习吗？\n欢迎一起交流。  "},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "留言发布成功，等待审核"
    data = body["data"]
    saved = db.get(Message, data["id"])
    assert saved.author_id == data["author_id"] == user_id
    assert saved.content == data["content"] == "今晚图书馆有人一起自习吗？\n欢迎一起交流。"
    assert saved.review_status == data["review_status"] == "pending"
    assert saved.prediction_status == data["prediction_status"] == "no_model"
    assert saved.predicted_label is None
    assert saved.manual_label is None
    assert saved.deleted_at is None
    assert data["created_at"] and data["updated_at"]
    assert saved.created_at == saved.updated_at or saved.updated_at >= saved.created_at


@pytest.mark.parametrize("data", [
    {},
    {"content": ""},
    {"content": " \n\t\u3000 "},
    {"content": "字" * 2001},
    {"content": None},
    {"content": "合法正文", "author_id": 2},
    {"content": "合法正文", "review_status": "approved"},
    {"content": "合法正文", "manual_label": "normal"},
])
def test_invalid_or_forged_publication_does_not_write(client, db, data):
    response = client.post("/api/v1/messages", headers=auth_headers(), json=data)
    assert response.status_code == 422
    assert response.json()["data"] is None
    assert db.scalar(select(func.count()).select_from(Message)) == 0


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer invalid-token"},
    auth_headers(999),
])
def test_publish_requires_existing_logged_in_user(client, db, headers):
    response = client.post("/api/v1/messages", headers=headers, json={"content": "测试留言"})
    assert response.status_code == 401
    assert db.scalar(select(func.count()).select_from(Message)) == 0


@pytest.mark.parametrize("length", [1, 2000])
def test_publish_accepts_content_length_boundaries(client, db, length):
    response = client.post(
        "/api/v1/messages", headers=auth_headers(), json={"content": "字" * length},
    )
    assert response.json()["code"] == 200
    assert db.get(Message, response.json()["data"]["id"]).content == "字" * length
