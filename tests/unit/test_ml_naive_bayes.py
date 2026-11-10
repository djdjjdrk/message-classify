"""仅用人工构造的小矩阵验证算法，不读取或训练项目数据。"""

import numpy as np
import pytest
from scipy.sparse import csr_array, csr_matrix

from backend.app.ml.naive_bayes import MultinomialNaiveBayes


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def toy_data(request):
    X = np.array([[2, 1, 0], [1, 1, 0], [0, 1, 2], [0, 0, 3]])
    return (csr_matrix(X) if request.param else X), np.array([0, 0, 1, 1])


def test_counts_and_smoothed_probabilities_match_hand_calculation(toy_data):
    X, y = toy_data
    model = MultinomialNaiveBayes()
    assert model.fit(X, y) is model
    np.testing.assert_array_equal(model.classes_, [0, 1])
    np.testing.assert_array_equal(model.class_count_, [2, 2])
    np.testing.assert_array_equal(model.feature_count_, [[3, 2, 0], [0, 1, 5]])
    np.testing.assert_allclose(np.exp(model.class_log_prior_), [0.5, 0.5])
    np.testing.assert_allclose(np.exp(model.feature_log_prob_), [
        [4 / 8, 3 / 8, 1 / 8],
        [1 / 9, 2 / 9, 6 / 9],
    ])


def test_predictions_match_hand_calculated_posteriors(toy_data):
    X, y = toy_data
    model = MultinomialNaiveBayes().fit(X, y)
    queries = csr_matrix([[1, 0, 0], [0, 0, 1]])
    np.testing.assert_allclose(model.predict_proba(queries), [
        [9 / 11, 2 / 11],
        [3 / 19, 16 / 19],
    ])
    np.testing.assert_array_equal(model.predict(queries), [0, 1])


@pytest.mark.parametrize("alpha", [0.25, 1.0, 2.0])
def test_matches_independent_sklearn_reference(toy_data, alpha):
    # 现成分类器只用于独立对照，不被业务算法导入或调用。
    from sklearn.naive_bayes import MultinomialNB

    X, y = toy_data
    own = MultinomialNaiveBayes(alpha=alpha).fit(X, y)
    reference = MultinomialNB(alpha=alpha).fit(X, y)
    queries = csr_matrix([[1, 0, 0], [0, 0, 1], [4, 2, 1], [0, 0, 0]])
    np.testing.assert_allclose(own.class_log_prior_, reference.class_log_prior_)
    np.testing.assert_allclose(own.feature_log_prob_, reference.feature_log_prob_)
    np.testing.assert_allclose(own.predict_proba(queries), reference.predict_proba(queries))
    np.testing.assert_allclose(own.predict_log_proba(queries), reference.predict_log_proba(queries))


def test_zero_feature_sample_uses_class_prior():
    model = MultinomialNaiveBayes().fit(
        np.array([[1, 0], [2, 0], [1, 0], [0, 1]]),
        np.array([0, 0, 0, 1]),
    )
    np.testing.assert_allclose(model.predict_proba(csr_matrix((1, 2))), [[0.75, 0.25]])
    np.testing.assert_array_equal(model.predict(csr_matrix((1, 2))), [0])


def test_custom_class_prior_overrides_training_frequency():
    model = MultinomialNaiveBayes(class_prior=(0.5, 0.5)).fit(
        np.array([[1, 0], [2, 0], [1, 0], [0, 1]]),
        np.array([0, 0, 0, 1]),
    )
    np.testing.assert_allclose(np.exp(model.class_log_prior_), [0.5, 0.5])
    np.testing.assert_allclose(model.predict_proba(csr_matrix((1, 2))), [[0.5, 0.5]])


def test_equal_probability_uses_spam_threshold():
    model = MultinomialNaiveBayes().fit(np.ones((2, 2)), np.array([0, 1]))
    np.testing.assert_allclose(model.predict_proba([[3, 2]]), [[0.5, 0.5]])
    np.testing.assert_array_equal(model.predict([[3, 2]]), [1])


def test_long_documents_have_finite_normalized_probabilities(toy_data):
    X, y = toy_data
    model = MultinomialNaiveBayes().fit(X, y)
    queries = csr_matrix([[10**6, 0, 0], [0, 0, 10**6]])
    probabilities = model.predict_proba(queries)
    assert np.isfinite(probabilities).all()
    assert np.isfinite(model.predict_log_proba(queries)).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), [1, 1])
    np.testing.assert_array_equal(model.predict(queries), [0, 1])


@pytest.mark.parametrize("matrix_type", [csr_matrix, csr_array])
def test_sparse_input_is_not_expanded_or_modified(monkeypatch, matrix_type):
    X = matrix_type([[2, 0, 1], [0, 3, 0]])
    original_data = X.data.copy()
    original_indices = X.indices.copy()

    def reject_dense_conversion(*args, **kwargs):
        raise AssertionError("不得将完整稀疏词频矩阵展开")

    monkeypatch.setattr(csr_matrix, "toarray", reject_dense_conversion)
    model = MultinomialNaiveBayes().fit(X, np.array([0, 1]))
    assert model.predict_proba(X).shape == (2, 2)
    np.testing.assert_array_equal(X.data, original_data)
    np.testing.assert_array_equal(X.indices, original_indices)
