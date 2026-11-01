"""使用临时的小样本特征检查训练入口和模型保存加载。"""

import subprocess
import sys

import joblib
import numpy as np
import pytest

from backend.app.ml.dataset import PROJECT_ROOT
from backend.app.ml.features import fit_training_features, save_training_features
from backend.app.ml.train import train_model


@pytest.fixture
def training_features(tmp_path):
    vectorizer, matrix, labels = fit_training_features([
        {"content": "一起 自习", "label": "0"},
        {"content": "图书馆 自习", "label": "0"},
        {"content": "免费 领取 免费", "label": "1"},
        {"content": "领取 免费", "label": "1"},
    ])
    feature_dir = tmp_path / "features"
    save_training_features(vectorizer, matrix, labels, feature_dir)
    return feature_dir, vectorizer, matrix, labels


def test_trains_only_from_training_files_and_reload_preserves_predictions(training_features, tmp_path):
    feature_dir, vectorizer, matrix, labels = training_features
    original_files = {path: path.read_bytes() for path in feature_dir.iterdir()}
    model_path = tmp_path / "models" / "toy.joblib"
    artifact = train_model(feature_dir, model_path, alpha=2.0, model_name="toy_v1")
    restored = joblib.load(model_path)

    assert artifact["training_sample_count"] == len(labels)
    assert restored["model_name"] == "toy_v1"
    assert restored["alpha"] == restored["model"].alpha == 2.0
    assert restored["classes"] == [0, 1]
    assert restored["threshold"] == 0.5
    assert restored["vocabulary_size"] == matrix.shape[1]
    assert restored["vectorizer"].vocabulary_ == vectorizer.vocabulary_
    np.testing.assert_allclose(
        restored["model"].predict_proba(matrix),
        artifact["model"].predict_proba(matrix),
    )
    queries = restored["vectorizer"].transform(["一起 自习", "免费 领取"])
    np.testing.assert_array_equal(restored["model"].predict(queries), [0, 1])
    for path, content in original_files.items():
        assert path.read_bytes() == content


def test_existing_model_is_never_overwritten(training_features, tmp_path):
    feature_dir, _, _, _ = training_features
    model_path = tmp_path / "existing.joblib"
    model_path.write_bytes(b"existing-model")
    with pytest.raises(FileExistsError, match="已存在"):
        train_model(feature_dir, model_path)
    assert model_path.read_bytes() == b"existing-model"


def test_save_failure_cleans_up_partial_model(training_features, tmp_path, monkeypatch):
    feature_dir, _, _, _ = training_features
    model_path = tmp_path / "failed.joblib"

    def failed_dump(artifact, output, **kwargs):
        output.write(b"partial-model")
        raise OSError("模拟保存失败")

    monkeypatch.setattr("backend.app.ml.train.joblib.dump", failed_dump)
    with pytest.raises(OSError, match="保存失败"):
        train_model(feature_dir, model_path)
    assert not model_path.exists()


def test_cli_saves_a_model_loadable_from_another_process(training_features, tmp_path):
    feature_dir, _, _, _ = training_features
    model_path = tmp_path / "cli.joblib"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "backend.app.ml.train",
         "--feature-dir", str(feature_dir), "--model-path", str(model_path),
         "--model-name", "cli_v1"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert "cli_v1" in result.stdout
    restored = joblib.load(model_path)
    queries = restored["vectorizer"].transform(["免费 领取"])
    np.testing.assert_array_equal(restored["model"].predict(queries), [1])
