"""多项式朴素贝叶斯：0 为正常，1 为垃圾。"""

import math

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, ClassifierMixin


class MultinomialNaiveBayes(ClassifierMixin, BaseEstimator):
    def __init__(self, alpha=1.0, class_prior=None, threshold=0.5):
        self.alpha = alpha
        # 默认使用训练集类别比例；传入 (normal, spam) 可固定先验。
        self.class_prior = class_prior
        self.threshold = threshold

    def fit(self, X, y):
        """训练：统计类别数量，计算先验和拉普拉斯修正后的词概率。"""
        X = csr_matrix(X, dtype=float)
        y = np.asarray(y)
        sample_count, word_count = X.shape
        self.classes_ = np.array([0, 1])
        self.class_count_ = np.zeros(2, dtype=int)
        self.feature_count_ = np.zeros((2, word_count))
        self.class_log_prior_ = np.zeros(2)
        self.feature_log_prob_ = np.zeros((2, word_count))
        self.n_features_in_ = word_count

        for label in [0, 1]:
            # 取出这一类的全部留言。
            class_samples = X[y == label]
            class_count = class_samples.shape[0]
            self.class_count_[label] = class_count

            # 类别先验：默认用这一类的留言数 / 全部留言数。
            prior = (
                class_count / sample_count
                if self.class_prior is None
                else self.class_prior[label]
            )
            self.class_log_prior_[label] = math.log(prior)

            # 按列汇总这一类的特征权重，支持词频和 TF-IDF。
            counts = np.asarray(class_samples.sum(axis=0)).ravel()
            self.feature_count_[label] = counts
            total = counts.sum() + self.alpha * word_count

            # 词条件概率：(该词总次数 + alpha) / (全部词次数 + alpha * 词表大小)。
            # 保存对数，预测时把概率连乘改为对数相加。
            for word_index in range(word_count):
                numerator = counts[word_index] + self.alpha
                self.feature_log_prob_[label, word_index] = math.log(numerator) - math.log(total)
        return self

    def decision_function(self, X):
        """预测得分：先验对数 + 各词特征权重乘条件概率对数。"""
        X = csr_matrix(X, dtype=float)
        scores = np.zeros((X.shape[0], 2))
        for sample_index in range(X.shape[0]):
            row = X.getrow(sample_index)
            for label in [0, 1]:
                score = self.class_log_prior_[label]
                # indices 是出现过的词的列号，data 是对应的特征权重。
                for word_index, count in zip(row.indices, row.data):
                    score += count * self.feature_log_prob_[label, word_index]
                scores[sample_index, label] = score
        return scores

    def predict_log_proba(self, X):
        """将两类得分转成归一化概率的对数。"""
        scores = self.decision_function(X)
        for index in range(len(scores)):
            # 先减去最大得分，避免长文本的概率计算下溢。
            scores[index] = scores[index] - max(scores[index])
            total = math.exp(scores[index, 0]) + math.exp(scores[index, 1])
            scores[index, 0] -= math.log(total)
            scores[index, 1] -= math.log(total)
        return scores

    def predict_proba(self, X):
        """返回正常概率、垃圾概率。"""
        return np.exp(self.predict_log_proba(X))

    def predict(self, X):
        """预测多条留言，垃圾概率达到分类阈值时返回 1。"""
        probabilities = self.predict_proba(X)
        labels = np.zeros(len(probabilities), dtype=int)
        for index in range(len(probabilities)):
            if probabilities[index, 1] >= self.threshold:
                labels[index] = 1
        return labels
