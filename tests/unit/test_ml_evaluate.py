"""验证指标定义、测试样本对齐、零特征计数以及评估不重新训练。"""

import csv
import json

import numpy as np
import pytest
from sklearn.feature_extraction.text import CountVectorizer

from backend.app.ml.dataset import save_dataset
from backend.app.ml.evaluate import calculate_metrics, evaluate_model
from backend.app.ml.features import (
    fit_training_features,
    save_test_features,
    save_training_features,
    transform_test_features,
)
from backend.app.ml.naive_bayes import MultinomialNaiveBayes
from backend.app.ml.train import train_model


def test_metrics_match_hand_calculation():
    metrics = calculate_metrics([0, 0, 1, 1, 1], [0, 1, 1, 0, 1])
    assert metrics["sample_count"] == 5
    assert metrics["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 2}
    assert metrics["accuracy"] == pytest.approx(3 / 5)
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["f1"] == pytest.approx(2 / 3)


@pytest.mark.parametrize(("true", "predicted", "accuracy"), [
    ([0, 0], [0, 0], 1),
    ([1, 1], [0, 0], 0),
    ([0, 0], [1, 1], 0),
])
def test_undefined_precision_or_recall_is_zero(true, predicted, accuracy):
    metrics = calculate_metrics(true, predicted)
    assert metrics["accuracy"] == accuracy
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == 0


@pytest.fixture
def evaluation_files(tmp_path):
    feature_dir = tmp_path / "features"
    vectorizer, matrix, labels = fit_training_features([
        {"content": "一起 自习", "label": "0"},
        {"content": "图书馆 自习", "label": "0"},
        {"content": "免费 领取 免费", "label": "1"},
        {"content": "领取 免费", "label": "1"},
    ])
    save_training_features(vectorizer, matrix, labels, feature_dir)
    model_path = tmp_path / "models" / "toy.joblib"
    train_model(feature_dir, model_path)
    samples = [
        {"content": "一起 自习", "label": "0", "source": "normal"},
        {"content": "免费 领取", "label": "1", "source": "spam"},
        {"content": "免费 免费", "label": "0", "source": "false_positive"},
        {"content": "自习 自习", "label": "1", "source": "false_negative"},
        {"content": "OOVTokenOnly", "label": "1", "source": "unknown"},
    ]
    test_matrix, test_labels = transform_test_features(vectorizer, samples)
    save_test_features(test_matrix, test_labels, feature_dir)
    test_csv = tmp_path / "test.csv"
    save_dataset(samples, test_csv)
    return model_path, feature_dir, test_csv


def test_evaluation_counts_every_sample_and_exports_correct_errors(evaluation_files, tmp_path, monkeypatch):
    model_path, feature_dir, test_csv = evaluation_files
    output_dir = tmp_path / "report"
    protected = [model_path, test_csv, *feature_dir.iterdir()]
    originals = {path: path.read_bytes() for path in protected}

    def forbidden_fit(*args, **kwargs):
        raise AssertionError("评估期间禁止训练模型或拟合词表")

    monkeypatch.setattr(MultinomialNaiveBayes, "fit", forbidden_fit)
    monkeypatch.setattr(CountVectorizer, "fit", forbidden_fit)
    monkeypatch.setattr(CountVectorizer, "fit_transform", forbidden_fit)
    report = evaluate_model(model_path, feature_dir, test_csv, output_dir)

    assert report["sample_count"] == 5
    assert report["zero_feature_count"] == 1
    assert report["offline_zero_feature_policy"] == "predict_from_class_prior"
    assert report["online_zero_feature_policy"] == "no_features_manual_annotation"
    assert report["misclassified_count"] == 2
    assert report["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 2}
    assert report["label_counts"] == {"0": 2, "1": 3}
    assert json.loads((output_dir / "metrics.json").read_text(encoding="utf-8")) == report
    with (output_dir / "predictions.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 5
    assert [row["predicted_label"] for row in rows] == ["0", "1", "1", "0", "1"]
    assert rows[-1]["no_known_features"] == "1"
    assert rows[0]["source"] == "normal"
    with (output_dir / "errors.csv").open(encoding="utf-8-sig", newline="") as file:
        errors = list(csv.DictReader(file))
    assert [row["sample_index"] for row in errors] == ["3", "4"]
    assert [row["error_type"] for row in errors] == ["正常误判为垃圾", "垃圾漏判为正常"]
    for path, original in originals.items():
        assert path.read_bytes() == original
