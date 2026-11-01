"""检查中文词频、词表列号、训练标签顺序和保存结果。"""

import json
from collections import Counter
from copy import deepcopy

import numpy as np
import pytest
from scipy.sparse import issparse, load_npz

from backend.app.ml.features import (
    fit_training_features,
    load_training_vectorizer,
    save_test_features,
    save_training_features,
    tokenize,
    transform_test_features,
)


def test_tokenization_keeps_single_characters_numbers_and_english():
    assert tokenize("\ufeff 不，钱！Ａ１ １２３\n") == ["不", "钱", "A1", "123"]
    assert tokenize("，。！？ \n\u200b") == []


def test_counts_repeated_words_and_keeps_labels_aligned_without_changing_input():
    samples = [
        {"content": "一起 自习 自习", "label": "0", "source": "source_only"},
        {"content": "免费 领取 免费", "label": "1", "source": "source_only"},
    ]
    original = deepcopy(samples)
    vectorizer, matrix, labels = fit_training_features(samples)
    vocabulary = vectorizer.vocabulary_
    assert set(vocabulary) == {"一起", "自习", "免费", "领取"}
    assert issparse(matrix)
    assert matrix.shape == (2, 4)
    assert matrix[0, vocabulary["自习"]] == 2
    assert matrix[1, vocabulary["免费"]] == 2
    assert matrix[0, vocabulary["领取"]] == 0
    assert labels.tolist() == [0, 1]
    assert labels.dtype == np.int64
    assert samples == original
    for index, sample in enumerate(samples):
        actual = {
            word: int(matrix[index, column]) for word, column in vocabulary.items()
            if matrix[index, column]
        }
        assert actual == Counter(tokenize(sample["content"]))


def test_fitting_uses_only_content_and_is_repeatable():
    samples = [{"content": "免费 学习", "label": "0", "source": "source_a"}]
    changed = [{**samples[0], "label": "1", "source": "source_b"}]
    first, matrix, labels = fit_training_features(samples)
    second, changed_matrix, changed_labels = fit_training_features(changed)
    assert first.vocabulary_ == second.vocabulary_
    assert (matrix != changed_matrix).nnz == 0
    assert labels.tolist() == [0] and changed_labels.tolist() == [1]


def test_punctuation_only_row_stays_aligned_as_zero_features():
    _, matrix, labels = fit_training_features([
        {"content": "免费 领取", "label": "1"},
        {"content": "！！！", "label": "0"},
    ])
    assert matrix.shape[0] == 2
    assert matrix.getrow(1).nnz == 0
    assert labels.tolist() == [1, 0]


def test_saved_vocabulary_matrix_and_labels_preserve_their_correspondence(tmp_path):
    vectorizer, matrix, labels = fit_training_features([
        {"content": "一起 自习", "label": "0"},
        {"content": "免费 领取 免费", "label": "1"},
    ])
    output_dir = tmp_path / "features"
    save_training_features(vectorizer, matrix, labels, output_dir)
    vocabulary = json.loads((output_dir / "vocabulary.json").read_text(encoding="utf-8"))
    assert vocabulary == vectorizer.vocabulary_
    assert (load_npz(output_dir / "X_train.npz") != matrix).nnz == 0
    assert np.array_equal(np.load(output_dir / "y_train.npy", allow_pickle=False), labels)


def test_test_conversion_uses_saved_columns_and_ignores_unknown_words(tmp_path, monkeypatch):
    vectorizer, matrix, labels = fit_training_features([
        {"content": "一起 自习", "label": "0"},
        {"content": "免费 领取", "label": "1"},
    ])
    save_training_features(vectorizer, matrix, labels, tmp_path)
    original_files = {path: path.read_bytes() for path in tmp_path.iterdir()}
    restored = load_training_vectorizer(tmp_path / "vocabulary.json")
    samples = [
        {"content": "BrandNewToken 免费 免费", "label": "1"},
        {"content": "BrandNewToken", "label": "0"},
        {"content": "！！！", "label": "0"},
    ]
    original_samples = deepcopy(samples)

    def fail_if_fitted(*args, **kwargs):
        raise AssertionError("测试集不得重新拟合词表")

    monkeypatch.setattr(type(restored), "fit", fail_if_fitted)
    monkeypatch.setattr(type(restored), "fit_transform", fail_if_fitted)
    test_matrix, test_labels = transform_test_features(restored, samples)

    assert restored.vocabulary_ == vectorizer.vocabulary_
    assert test_matrix.shape == (3, matrix.shape[1])
    assert test_matrix[0, vectorizer.vocabulary_["免费"]] == 2
    assert test_matrix.getrow(0).sum() == 2
    assert test_matrix.getrow(1).nnz == test_matrix.getrow(2).nnz == 0
    assert test_labels.tolist() == [1, 0, 0]
    assert test_labels.dtype == np.int64
    assert samples == original_samples

    save_test_features(test_matrix, test_labels, tmp_path)
    assert (load_npz(tmp_path / "X_test.npz") != test_matrix).nnz == 0
    assert np.array_equal(np.load(tmp_path / "y_test.npy", allow_pickle=False), test_labels)
    for path, content in original_files.items():
        assert path.read_bytes() == content


def test_loading_vocabulary_preserves_column_numbers_not_json_key_order(tmp_path):
    path = tmp_path / "vocabulary.json"
    path.write_text(json.dumps({"领取": 2, "免费": 0, "自习": 1}), encoding="utf-8")
    vectorizer = load_training_vectorizer(path)
    matrix, _ = transform_test_features(vectorizer, [
        {"content": "领取 免费 免费", "label": "1"},
    ])
    assert matrix.toarray().tolist() == [[2, 0, 1]]
