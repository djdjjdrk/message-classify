"""保护 ML/业务层协作中的概率语义、数据隔离和落库格式。"""

import pytest
from pydantic import ValidationError

from backend.app.ml import ModelMetrics, PredictionResult, TrainRequest
from backend.app.models.message import Message


@pytest.mark.parametrize(
    ("probability", "label"), [(0.1, "normal"), (0.5, "spam"), (0.9, "spam")]
)
def test_prediction_can_be_written_to_message(probability, label):
    result = PredictionResult(
        prediction_status="success",
        predicted_probability=probability,
        predicted_label=label,
        model_name="baseline_v1",
        prediction_explanation=[{"feature": "返现", "weight": 0.71}],
    )
    fields = result.model_dump(mode="json")
    assert set(fields) <= set(Message.__table__.columns.keys())
    message = Message(**fields)
    assert message.predicted_probability == probability
    assert message.prediction_explanation == [{"feature": "返现", "weight": 0.71}]


def test_probability_is_spam_probability_even_for_normal_predictions():
    with pytest.raises(ValidationError):
        PredictionResult(
            prediction_status="success",
            predicted_probability=0.9,
            predicted_label="normal",
            model_name="baseline_v1",
        )


@pytest.mark.parametrize("status", ["no_features", "no_model", "error"])
def test_failed_prediction_cannot_silently_become_normal(status):
    result = PredictionResult(prediction_status=status)
    assert result.predicted_label is None
    assert result.predicted_probability is None
    with pytest.raises(ValidationError):
        PredictionResult(prediction_status=status, predicted_label="normal")


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.1, 1.1])
def test_prediction_rejects_non_probability_values(probability):
    with pytest.raises(ValidationError):
        PredictionResult(
            prediction_status="success", predicted_label="spam",
            predicted_probability=probability, model_name="baseline_v1",
        )


def train_request_data():
    return {
        "model_name": "baseline_v1",
        "model_path": "artifacts/models/baseline/pipeline.joblib",
        "training_samples": [
            {"content": "今晚一起自习", "label": "normal"},
            {"content": "刷单返现联系我", "label": "spam"},
        ],
        "evaluation_samples": [
            {"content": "寻找丢失的校园卡", "label": "normal"},
            {"content": "兼职高薪日结加群", "label": "spam"},
        ],
    }


def test_training_contract_round_trips_as_json():
    request = TrainRequest(**train_request_data())
    assert TrainRequest.model_validate_json(request.model_dump_json()) == request
    assert request.random_state == 42


def test_training_rejects_leakage_even_with_conflicting_labels():
    data = train_request_data()
    data["evaluation_samples"][1]["content"] = " 今晚一起自习 "
    with pytest.raises(ValidationError, match="训练集与评估集"):
        TrainRequest(**data)


def test_metrics_cannot_drop_evaluated_samples():
    with pytest.raises(ValidationError, match="评估样本数"):
        ModelMetrics(
            accuracy=0.9, precision=0.9, recall=0.9, f1=0.9,
            sample_count=100,
            confusion_matrix={"tn": 45, "fp": 5, "fn": 5, "tp": 44},
        )
