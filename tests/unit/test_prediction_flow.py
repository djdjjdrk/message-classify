"""发布、分类展示、人工纠正和故障降级的集成检查。"""

from copy import deepcopy

import pytest

from backend.app.models import Message
from backend.app.ml.predict import predict_text
from backend.app.utils.jwt import create_access_token


def headers(user=2):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def online_model(prediction_pipeline, monkeypatch):
    path, _ = prediction_pipeline
    monkeypatch.setattr("backend.app.service.message.settings.MODEL_PATH", str(path))
    return path


@pytest.mark.parametrize("content,label", [("免费 免费 领取", "spam"), ("学习", "normal")])
def test_publication_displays_real_prediction_and_manual_label_preserves_original(client, db, online_model, content, label):
    expected = predict_text(content, online_model)
    response = client.post("/api/v1/messages", headers=headers(1), json={"content": content})
    assert response.status_code == 200
    message_id = response.json()["data"]["id"]
    saved = db.get(Message, message_id)
    assert saved.prediction_status == "success" and saved.review_status == "pending"
    original = (saved.predicted_label, saved.predicted_probability, saved.model_name, deepcopy(saved.prediction_explanation))
    assert original == (label, expected.spam_probability, expected.model_name, expected.explanation)
    item = client.get("/api/v1/classification/messages", headers=headers()).json()["data"]["list"][0]
    assert item["predicted_label"] == item["effective_label"] == label
    assert item["label_source"] == "model"
    assert item["predicted_probability"] == expected.spam_probability
    assert item["model_name"] == expected.model_name
    assert item["prediction_explanation"] == expected.explanation

    corrected = "normal" if label == "spam" else "spam"
    response = client.post(f"/api/v1/classification/messages/{message_id}/annotations", headers=headers(),
                           json={"label": corrected, "reason": "人工确认"})
    assert response.json()["code"] == 200
    item = client.get("/api/v1/classification/messages", headers=headers(), params={"category": corrected}).json()["data"]["list"][0]
    assert item["effective_label"] == corrected and item["label_source"] == "manual"
    assert (item["predicted_label"], item["predicted_probability"], item["model_name"], item["prediction_explanation"]) == original
    db.refresh(saved)
    assert saved.review_status == "pending"


@pytest.mark.parametrize("content", ["UniqueUnseenToken", "！！！", "\u200b"])
def test_no_features_is_saved_as_unclassified_pending_review(client, db, online_model, content):
    response = client.post("/api/v1/messages", headers=headers(1), json={"content": content})
    data = response.json()["data"]
    assert data["prediction_status"] == "no_features"
    saved = db.get(Message, data["id"])
    assert saved.predicted_label is saved.predicted_probability is None
    assert saved.model_name == "test_v1" and saved.prediction_explanation == []
    assert saved.review_status == "pending"
    item = client.get("/api/v1/classification/messages", headers=headers(), params={"category": "unclassified"}).json()["data"]["list"][0]
    assert item["id"] == saved.id and item["effective_label"] is None


@pytest.mark.parametrize("failure,status", [("missing", "no_model"), ("corrupt", "error"), ("runtime", "error")])
def test_prediction_failure_still_saves_pending_review(client, db, tmp_path, monkeypatch, failure, status):
    path = tmp_path / "bad.joblib"
    monkeypatch.setattr("backend.app.service.message.settings.MODEL_PATH", str(path))
    if failure == "corrupt":
        path.write_bytes(b"not a joblib file")
    elif failure == "runtime":
        def fail(*args, **kwargs):
            raise RuntimeError("预测计算失败")
        monkeypatch.setattr("backend.app.service.message.predict_text", fail)
    response = client.post("/api/v1/messages", headers=headers(1), json={"content": "学习"})
    assert response.status_code == 200
    saved = db.get(Message, response.json()["data"]["id"])
    assert saved.prediction_status == status and saved.review_status == "pending"
    assert saved.predicted_label is saved.predicted_probability is saved.model_name is saved.prediction_explanation is None
