"""在训练集建立词表，使用同一词表生成训练和测试词频矩阵。"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import CountVectorizer

from backend.app.ml.dataset import DEFAULT_DATA_DIR, DEFAULT_SPLIT_DIR, read_csv
from backend.app.ml.preprocessing import TextPreprocessor


DEFAULT_FEATURE_DIR = DEFAULT_DATA_DIR / "features"
_preprocessor = TextPreprocessor()


def tokenize(content):
    """保留旧函数路径，兼容已保存向量器中的 tokenizer 引用。"""
    return _preprocessor.tokenize(content)


def _create_vectorizer(vocabulary=None):
    return CountVectorizer(
        tokenizer=tokenize, token_pattern=None, lowercase=False,
        dtype=np.int64, vocabulary=vocabulary,
    )


def fit_training_features(samples):
    """只在训练正文上建立词表；标签保持整数 0/1。"""
    contents = [row["content"] for row in samples]
    labels = np.array([int(row["label"]) for row in samples], dtype=np.int64)
    vectorizer = _create_vectorizer()
    matrix = vectorizer.fit_transform(contents)
    return vectorizer, matrix, labels


def load_training_vectorizer(vocabulary_path=DEFAULT_FEATURE_DIR / "vocabulary.json"):
    with Path(vocabulary_path).open(encoding="utf-8") as file:
        vocabulary = json.load(file)
    return _create_vectorizer(vocabulary)


def transform_test_features(vectorizer, samples):
    """沿用训练词表，不新增词、不丢弃全零特征样本。"""
    contents = [row["content"] for row in samples]
    labels = np.array([int(row["label"]) for row in samples], dtype=np.int64)
    return vectorizer.transform(contents), labels


def save_training_features(vectorizer, X_train, y_train, output_dir=DEFAULT_FEATURE_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    words = vectorizer.get_feature_names_out()
    vocabulary = {word: index for index, word in enumerate(words)}
    with (output_dir / "vocabulary.json").open("w", encoding="utf-8") as file:
        json.dump(vocabulary, file, ensure_ascii=False, indent=2)
    save_npz(output_dir / "X_train.npz", X_train)
    np.save(output_dir / "y_train.npy", y_train, allow_pickle=False)


def save_test_features(X_test, y_test, output_dir=DEFAULT_FEATURE_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_npz(output_dir / "X_test.npz", X_test)
    np.save(output_dir / "y_test.npy", y_test, allow_pickle=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成词频特征")
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    if not args.test_only:
        samples = read_csv(DEFAULT_SPLIT_DIR / "train.csv")
        vectorizer, X_train, y_train = fit_training_features(samples)
        save_training_features(vectorizer, X_train, y_train)
        print(f"训练词频矩阵：{X_train.shape}，正常={sum(y_train == 0)}，垃圾={sum(y_train == 1)}")

    vectorizer = load_training_vectorizer()
    samples = read_csv(DEFAULT_SPLIT_DIR / "test.csv")
    X_test, y_test = transform_test_features(vectorizer, samples)
    save_test_features(X_test, y_test)
    print(f"测试词频矩阵：{X_test.shape}，正常={sum(y_test == 0)}，垃圾={sum(y_test == 1)}")
    print(f"全零特征样本：{sum(X_test.getnnz(axis=1) == 0)}；保存位置：{DEFAULT_FEATURE_DIR}")
