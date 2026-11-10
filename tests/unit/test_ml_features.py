"""检查中文分词、广告信号和 sklearn TF-IDF 配置。"""

import math

import numpy as np
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.ml.features import ad_signal_tokens, create_vectorizer, tokenize, tokenize_with_signals


def test_tokenization_keeps_single_characters_numbers_and_english():
    assert tokenize("\ufeff 不，钱！Ａ１ １２３\n") == ["不", "钱", "A1", "123"]
    assert tokenize("，。！？ \n\u200b") == []


def test_signal_tokens_preserve_normal_words_and_limit_repetitions():
    tokens = tokenize_with_signals("加微信，老师带你炒股，一周回本")
    assert {"加微信", "老师", "炒股"} <= set(tokens)
    assert "__ad_contact__" in tokens and "__ad_money__" in tokens
    assert ad_signal_tokens("微信" * 10).count("__ad_contact__") == 3
    assert tokenize_with_signals("，。！？") == []


def test_tfidf_uses_log_frequency_idf_normalization_and_minimum_document_count():
    vectorizer = create_vectorizer()
    assert isinstance(vectorizer, TfidfVectorizer)
    matrix = vectorizer.fit_transform([
        "common common normal RareToken", "common normal",
        "common spam spam", "common spam",
    ])
    vocabulary = vectorizer.vocabulary_
    assert "RareToken" not in vocabulary
    assert set(vocabulary) == {"common", "normal", "spam"}
    np.testing.assert_allclose(matrix.multiply(matrix).sum(axis=1), np.ones((4, 1)))
    common, normal = vocabulary["common"], vocabulary["normal"]
    expected = (1 + math.log(2)) * vectorizer.idf_[common] / vectorizer.idf_[normal]
    assert matrix[0, common] / matrix[0, normal] == pytest.approx(expected)


def test_transform_keeps_training_vocabulary_and_retains_zero_feature_rows():
    vectorizer = create_vectorizer()
    vectorizer.fit(["学习 自习", "学习 自习", "免费 领取", "免费 领取"])
    vocabulary = vectorizer.vocabulary_.copy()
    matrix = vectorizer.transform(["学习 UniqueUnseenToken", "UniqueUnseenToken", "！！！"])
    assert vectorizer.vocabulary_ == vocabulary
    assert matrix.getnnz(axis=1).tolist() == [1, 0, 0]
