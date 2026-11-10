"""验证 Pipeline 训练、序列化和 backend 训练入口。"""

import json
import subprocess
import sys

import joblib
import numpy as np
import pytest
from sklearn.base import clone, is_classifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

from backend.app.ml import train
from backend.app.ml.dataset import PROJECT_ROOT, save_dataset
from backend.app.ml.naive_bayes import MultinomialNaiveBayes
from backend.app.ml.predict import predict_text


@pytest.fixture
def samples():
    return [
        {"content": "一起 自习", "label": "0", "source": "campus"},
        {"content": "图书馆 自习", "label": "0", "source": "campus"},
        {"content": "免费 领取 免费", "label": "1", "source": "ads"},
        {"content": "领取 免费", "label": "1", "source": "ads"},
    ]


def test_pipeline_uses_sklearn_features_and_handwritten_bayes(samples, monkeypatch):
    def forbidden_library_bayes(*args, **kwargs):
        raise AssertionError("贝叶斯核心必须由项目自己的分类器计算")

    monkeypatch.setattr("sklearn.naive_bayes.MultinomialNB.fit", forbidden_library_bayes)
    pipeline = train.fit_model(samples)
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline[0], TfidfVectorizer)
    assert isinstance(pipeline[-1], MultinomialNaiveBayes)
    assert is_classifier(pipeline)
    assert pipeline[-1].class_prior == (0.5, 0.5)
    assert pipeline.training_sample_count_ == 4
    assert {"campus", "ads"}.isdisjoint(pipeline[0].vocabulary_)
    np.testing.assert_array_equal(pipeline.predict(["自习", "免费 领取"]), [0, 1])


def test_pipeline_supports_sklearn_clone_and_parameter_management(samples):
    pipeline = train.fit_model(samples, alpha=2.0)
    copied = clone(pipeline)
    assert copied.get_params()["multinomialnaivebayes__alpha"] == 2.0
    copied.fit([row["content"] for row in samples], [int(row["label"]) for row in samples])
    np.testing.assert_allclose(copied.predict_proba(["自习"]), pipeline.predict_proba(["自习"]))


def test_saved_pipeline_reload_preserves_predictions_and_metadata(samples, tmp_path):
    pipeline = train.fit_model(samples)
    path = tmp_path / "pipeline.joblib"
    train.save_model(pipeline, path, model_name="toy_pipeline", threshold=0.36)
    loaded = joblib.load(path)
    assert isinstance(loaded, Pipeline)
    assert loaded.model_name_ == "toy_pipeline"
    assert loaded[-1].threshold == 0.36
    np.testing.assert_allclose(
        loaded.predict_proba(["自习", "免费 领取"]),
        pipeline.predict_proba(["自习", "免费 领取"]),
    )
    probabilities = loaded.predict_proba(["自习", "免费 领取"])
    np.testing.assert_array_equal(loaded.predict(["自习", "免费 领取"]), probabilities[:, 1] >= 0.36)
    explanation = predict_text("免费 免费 领取", path).explanation
    assert next(item for item in explanation if item["word"] == "免费")["count"] == 2


def test_run_reads_csv_and_saves_pipeline_with_evaluation(samples, tmp_path, monkeypatch):
    split_dir, data_dir = tmp_path / "split", tmp_path / "processed"
    save_dataset(samples, split_dir / "train.csv")
    save_dataset([], data_dir / "weak_spam.csv")
    for name in ("test.csv", "source_holdout.csv"):
        save_dataset([samples[0], samples[2]], split_dir / name)
    monkeypatch.setattr(train, "DEFAULT_SPLIT_DIR", split_dir)
    monkeypatch.setattr(train, "DEFAULT_DATA_DIR", data_dir)
    monkeypatch.setattr(train, "select_threshold", lambda samples: (0.36, {"validation_count": 2}))
    result = train.run(tmp_path / "model")
    assert isinstance(joblib.load(result["model_path"]), Pipeline)
    assert result["same"]["sample_count"] == result["source"]["sample_count"] == 2
    summary = json.loads((tmp_path / "model/training.json").read_text(encoding="utf-8"))
    assert summary["threshold"] == 0.36 and summary["weak_sample_count"] == 0


def test_validation_score_prefers_precision_qualified_candidates():
    qualified = train.validation_score([0, 0, 1, 1], [0, 0, 1, 0])
    unqualified = train.validation_score([0, 0, 1, 1], [0, 1, 1, 1])
    assert qualified > unqualified
    assert unqualified < 0


def test_backend_cli_exposes_the_pipeline_training_entry():
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "backend.app.ml.train", "--help"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert "Pipeline" in result.stdout and "--output-dir" in result.stdout
