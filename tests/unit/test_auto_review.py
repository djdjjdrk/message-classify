"""自动通过阈值、公开展示和审核历史的业务检查。"""

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.ml.predict import PredictionResult
from backend.app.models import Message, ReviewRecord
from backend.app.service.message import create_message
from backend.app.utils.jwt import create_access_token


def headers(user_id=2):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def set_prediction(monkeypatch):
    def configure(probability, label=0, status="success"):
        result = PredictionResult(
            status=status, label=label, spam_probability=probability, model_name="auto_test",
        )
        monkeypatch.setattr("backend.app.service.message.predict_text", lambda *args, **kwargs: result)
    return configure


@pytest.mark.parametrize("probability,expected", [
    (0.0, "approved"), (0.009, "approved"), (0.01, "approved"),
    (0.010001, "pending"), (0.49, "pending"),
])
def test_normal_prediction_threshold_controls_visibility_and_history(client, db, set_prediction, probability, expected):
    set_prediction(probability)
    response = client.post("/api/v1/messages", headers=headers(1), json={"content": "校园交流"})
    body = response.json()
    assert body["code"] == 200 and body["data"]["review_status"] == expected
    message_id = body["data"]["id"]
    public = client.get("/api/v1/messages/public", headers=headers(1)).json()["data"]
    pending = client.get("/api/v1/reviews/pending", headers=headers()).json()["data"]
    classification = client.get("/api/v1/classification/messages", headers=headers()).json()["data"]["list"][0]
    assert classification["review_status"] == expected
    assert public["total"] == (1 if expected == "approved" else 0)
    assert pending["total"] == (1 if expected == "pending" else 0)
    record = db.scalar(select(ReviewRecord))
    if expected == "approved":
        assert "已自动通过审核" in body["message"]
        assert record.reviewer_id is None
        assert (record.review_source, record.previous_status, record.decision) == ("automatic", "pending", "approved")
        assert record.message_id == message_id and record.label_snapshot == "normal"
        assert record.model_name_snapshot == "auto_test"
        assert record.spam_probability_snapshot == probability and record.normal_threshold_snapshot == 0.01
        history = client.get("/api/v1/reviews/history", headers=headers()).json()["data"]["list"][0]
        assert history["review_source"] == "automatic" and history["reviewer_username"] is None
        assert history["spam_probability_snapshot"] == probability
    else:
        assert record is None
        assert pending["list"][0]["predicted_probability"] == probability


@pytest.mark.parametrize("label,probability,status", [(1, 0.001, "success"), (None, None, "no_features")])
def test_only_successful_normal_predictions_can_auto_pass(client, db, set_prediction, label, probability, status):
    set_prediction(probability, label, status)
    response = client.post("/api/v1/messages", headers=headers(1), json={"content": "测试留言"})
    assert response.json()["data"]["review_status"] == "pending"
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 0


def test_auto_review_respects_configured_threshold(client, set_prediction, monkeypatch):
    monkeypatch.setattr("backend.app.service.message.settings.AUTO_APPROVE_SPAM_THRESHOLD", 0.05)
    set_prediction(0.04)
    response = client.post("/api/v1/messages", headers=headers(1), json={"content": "校园交流"})
    assert response.json()["data"]["review_status"] == "approved"


def test_auto_review_history_failure_rolls_back_message_and_status(db, set_prediction):
    set_prediction(0.001)

    def fail_record(*args):
        raise SQLAlchemyError("模拟自动审核历史写入失败")

    event.listen(ReviewRecord, "before_insert", fail_record)
    try:
        with pytest.raises(SQLAlchemyError):
            create_message(db, author_id=1, content="校园交流")
    finally:
        event.remove(ReviewRecord, "before_insert", fail_record)
    assert db.scalar(select(func.count()).select_from(Message)) == 0
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 0
