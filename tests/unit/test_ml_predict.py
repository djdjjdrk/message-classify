"""核算在线预测、贡献排序和旧 tokenizer 兼容性；禁止拟合。"""

import math
from dataclasses import asdict

import joblib
import numpy as np
import pytest
from sklearn.feature_extraction.text import CountVectorizer

from backend.app.ml.features import tokenize
from backend.app.ml.naive_bayes import MultinomialNaiveBayes
from backend.app.ml.predict import predict_text
from backend.app.ml.preprocessing import TextPreprocessor


def test_preprocessor_keeps_existing_rules_and_legacy_entry():
    preprocessor = TextPreprocessor()
    raw = "\ufeff 不，钱！Ａ１ １２３\n\u200b"
    assert preprocessor.normalize(raw) == "不,钱!A1 123"
    assert preprocessor.tokenize(raw) == tokenize(raw) == ["不", "钱", "A1", "123"]
    assert preprocessor.tokenize("！？\u200b") == []


@pytest.mark.parametrize("content", ["", " \n\t\u3000 "])
def test_empty_input_is_parameter_error_before_loading(content, tmp_path):
    with pytest.raises(ValueError, match="不能为空"):
        predict_text(content, tmp_path / "missing.joblib")


def test_predict_uses_saved_transform_only_and_ignores_unknown_parts(prediction_artifact, monkeypatch):
    path, artifact = prediction_artifact
    original = path.read_bytes()

    def forbidden_fit(*args, **kwargs):
        raise AssertionError("在线禁止拟合词表或训练")

    monkeypatch.setattr(CountVectorizer, "fit", forbidden_fit)
    monkeypatch.setattr(CountVectorizer, "fit_transform", forbidden_fit)
    monkeypatch.setattr(MultinomialNaiveBayes, "fit", forbidden_fit)
    plain = predict_text("免费 免费 领取", path)
    mixed = predict_text("免费 免费 领取 UniqueUnseenToken", path)
    assert asdict(mixed) == asdict(plain)
    assert mixed.status == "success" and mixed.label == 1 and mixed.model_name == "test_v1"
    # 手算后验赔率 = 12.5^2 * (0.2 / 0.03)。
    odds = 12.5 ** 2 * (0.2 / 0.03)
    assert mixed.spam_probability == pytest.approx(odds / (1 + odds))
    assert mixed.explanation[0] == {
        "word": "免费", "count": 2, "contribution": pytest.approx(2 * math.log(12.5)), "direction": "spam",
    }
    assert path.read_bytes() == original
    assert artifact["vectorizer"].tokenizer is tokenize
    assert joblib.load(path)["vectorizer"].tokenizer is tokenize


@pytest.mark.parametrize("content", ["UniqueUnseenToken", "！！！", "\u200b\ufeff"])
def test_online_zero_features_abstains_but_offline_retains_prior(prediction_artifact, content, monkeypatch):
    path, artifact = prediction_artifact
    row = artifact["vectorizer"].transform([content])
    assert artifact["model"].predict_proba(row).tolist() == [[0.5, 0.5]]

    def forbidden_prediction(*args):
        raise AssertionError("在线全零特征不得当作成功预测")

    monkeypatch.setattr(MultinomialNaiveBayes, "predict_proba", forbidden_prediction)
    result = predict_text(content, path)
    assert result.status == "no_features" and result.model_name == "test_v1"
    assert result.label is result.spam_probability is None
    assert result.explanation == []


def test_ranks_contribution_not_frequency_and_limits_to_five(prediction_artifact):
    path, _ = prediction_artifact
    result = predict_text("共同 " * 20 + "学习 免费 领取 中奖 兼职 刷单 返利", path)
    assert result.label == 1
    assert len(result.explanation) == 5
    assert result.explanation[0]["word"] == "免费"
    assert all(item["direction"] == "spam" and item["contribution"] > 0 for item in result.explanation)
    assert "共同" not in [item["word"] for item in result.explanation]


def test_normal_support_is_first_even_if_opposing_term_has_larger_contribution(prediction_artifact):
    path, artifact = prediction_artifact
    artifact["model"].class_log_prior_ = np.log([0.999, 0.001])
    joblib.dump(artifact, path)
    result = predict_text("学习 免费 免费", path)
    assert result.label == 0
    assert [item["direction"] for item in result.explanation] == ["normal", "spam"]
    assert result.explanation[0]["contribution"] == pytest.approx(math.log(0.02 / 0.5))
    assert abs(result.explanation[1]["contribution"]) > abs(result.explanation[0]["contribution"])


def test_prior_can_win_without_any_supporting_terms(prediction_artifact):
    path, artifact = prediction_artifact
    artifact["model"].class_log_prior_ = np.log([0.999, 0.001])
    joblib.dump(artifact, path)
    result = predict_text("免费", path)
    assert result.label == 0 and result.status == "success"
    assert all(item["direction"] == "spam" for item in result.explanation)
    assert predict_text("共同", path).explanation == []


def test_threshold_comes_from_artifact(prediction_artifact):
    path, artifact = prediction_artifact
    artifact["threshold"] = 0.99
    joblib.dump(artifact, path)
    result = predict_text("免费", path)
    assert result.spam_probability > 0.5
    assert result.label == 0
