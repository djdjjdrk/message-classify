"""验证 Pipeline 评估、指标、零特征及 CSV 导出。"""

import csv
import json

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.ml.dataset import read_csv, save_dataset
from backend.app.ml.evaluate import calculate_metrics, evaluate_model
from backend.app.ml.naive_bayes import MultinomialNaiveBayes
from backend.app.ml.train import fit_model, save_model


def test_metrics_match_hand_calculation():
    metrics = calculate_metrics([0, 0, 1, 1, 1], [0, 1, 1, 0, 1])
    assert metrics["sample_count"] == 5
    assert metrics["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 2}
    assert metrics["accuracy"] == pytest.approx(3 / 5)
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == pytest.approx(2 / 3)


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
    pipeline = fit_model([
        {"content": "一起 自习", "label": "0"},
        {"content": "图书馆 自习", "label": "0"},
        {"content": "免费 领取 免费", "label": "1"},
        {"content": "领取 免费", "label": "1"},
    ])
    model_path = tmp_path / "pipeline.joblib"
    save_model(pipeline, model_path)
    samples = [
        {"content": "一起 自习", "label": "0", "source": "normal"},
        {"content": "免费 领取", "label": "1", "source": "spam"},
        {"content": "免费 免费", "label": "0", "source": "false_positive"},
        {"content": "自习 自习", "label": "1", "source": "false_negative"},
        {"content": "OOVTokenOnly", "label": "1", "source": "unknown"},
    ]
    test_csv = tmp_path / "test.csv"
    save_dataset(samples, test_csv)
    return model_path, test_csv


def test_evaluation_counts_every_sample_and_exports_errors(evaluation_files, tmp_path, monkeypatch):
    model_path, test_csv = evaluation_files
    originals = {path: path.read_bytes() for path in (model_path, test_csv)}

    def forbidden_fit(*args, **kwargs):
        raise AssertionError("评估期间禁止训练")

    monkeypatch.setattr(MultinomialNaiveBayes, "fit", forbidden_fit)
    monkeypatch.setattr(TfidfVectorizer, "fit", forbidden_fit)
    monkeypatch.setattr(TfidfVectorizer, "fit_transform", forbidden_fit)
    output_dir = tmp_path / "report"
    report = evaluate_model(model_path, test_csv, output_dir)
    assert report["sample_count"] == 5 and report["zero_feature_count"] == 1
    assert report["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 2}
    assert report["misclassified_count"] == 2
    assert report["offline_zero_feature_policy"] == "predict_from_class_prior"
    assert report["online_zero_feature_policy"] == "no_features_manual_annotation"
    assert json.loads((output_dir / "metrics.json").read_text(encoding="utf-8")) == report
    with (output_dir / "predictions.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["predicted_label"] for row in rows] == ["0", "1", "1", "0", "1"]
    assert rows[-1]["no_known_features"] == "1"
    with (output_dir / "errors.csv").open(encoding="utf-8-sig", newline="") as file:
        errors = list(csv.DictReader(file))
    assert [row["sample_index"] for row in errors] == ["3", "4"]
    assert (output_dir / "report.txt").is_file()
    assert all(path.read_bytes() == original for path, original in originals.items())


def test_evaluation_uses_current_csv_order(evaluation_files, tmp_path):
    model_path, test_csv = evaluation_files
    samples = list(reversed(read_csv(test_csv)))
    save_dataset(samples, test_csv)
    output_dir = tmp_path / "reordered"
    report = evaluate_model(model_path, test_csv, output_dir)
    assert report["sample_count"] == len(samples)
    with (output_dir / "predictions.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["content"] for row in rows] == [row["content"] for row in samples]


def test_empty_test_set_is_rejected(evaluation_files, tmp_path):
    model_path, test_csv = evaluation_files
    save_dataset([], test_csv)
    with pytest.raises(ValueError, match="测试集不能为空"):
        evaluate_model(model_path, test_csv, tmp_path / "report")


def test_error_export_keeps_column_headers_when_all_predictions_are_correct(evaluation_files, tmp_path):
    model_path, test_csv = evaluation_files
    save_dataset(read_csv(test_csv)[:2], test_csv)
    output_dir = tmp_path / "correct"
    report = evaluate_model(model_path, test_csv, output_dir)
    assert report["misclassified_count"] == 0
    with (output_dir / "errors.csv").open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        assert "spam_probability" in reader.fieldnames
        assert list(reader) == []


def test_balanced_accuracy_exposes_majority_class_shortcut():
    metrics = calculate_metrics([0] * 90 + [1] * 10, [0] * 100)
    assert metrics["accuracy"] == 0.9
    assert metrics["majority_baseline_accuracy"] == 0.9
    assert metrics["balanced_accuracy"] == 0.5
    assert metrics["recall"] == 0
    assert calculate_metrics([1, 1], [1, 0])["balanced_accuracy"] is None
