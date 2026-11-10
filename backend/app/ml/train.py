"""sklearn Pipeline 训练文本模型，贝叶斯核心由 MultinomialNaiveBayes 实现。"""

import argparse
import json
import re
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import fbeta_score, make_scorer, precision_score, recall_score
from sklearn.model_selection import TunedThresholdClassifierCV
from sklearn.pipeline import make_pipeline

from backend.app.ml.dataset import DEFAULT_DATA_DIR, DEFAULT_MODEL_PATH, DEFAULT_SPLIT_DIR, read_csv
from backend.app.ml.evaluate import evaluate_model
from backend.app.ml.features import create_vectorizer
from backend.app.ml.grouping import build_template_groups, grouped_holdout_indices
from backend.app.ml.naive_bayes import MultinomialNaiveBayes


MODEL_NAME = "campus_spam_final_v1"
HARD_NEGATIVE_PATTERN = re.compile(
    r"出|收|拼|租|二手|闲置|元|块|微信|qq|QQ|原味|女性朋友|纯友谊|免费|老师|股票"
)
MIN_VALIDATION_PRECISION = 0.95


def oversample_hard_negatives(samples):
    """困难正常样本额外重复两次，增加它们在训练中的影响。"""
    hard_negatives = [
        row for row in samples
        if int(row["label"]) == 0 and HARD_NEGATIVE_PATTERN.search(row["content"])
    ]
    return samples + hard_negatives * 2


def fit_model(samples, alpha=1.0):
    """向量器和手写分类器组成 Pipeline，一次 fit 完成训练。"""
    pipeline = make_pipeline(
        create_vectorizer(),
        MultinomialNaiveBayes(alpha=alpha, class_prior=(0.5, 0.5)),
    )
    pipeline.fit([row["content"] for row in samples], [int(row["label"]) for row in samples])
    pipeline.training_sample_count_ = len(samples)
    return pipeline


def validation_score(y_true, y_pred):
    """精确率达标的候选优先，再比较 sklearn 计算的 F2。"""
    precision = precision_score(y_true, y_pred, zero_division=0)
    f2 = fbeta_score(y_true, y_pred, beta=2, zero_division=0)
    if precision >= MIN_VALIDATION_PRECISION:
        return f2
    return f2 - 1


def select_threshold(samples):
    groups, _ = build_template_groups(samples)
    train, validation = grouped_holdout_indices(samples, groups)
    pipeline = fit_model(oversample_hard_negatives([samples[i] for i in train]))
    texts = [samples[i]["content"] for i in validation]
    labels = [int(samples[i]["label"]) for i in validation]
    tuner = TunedThresholdClassifierCV(
        pipeline, scoring=make_scorer(validation_score), response_method="predict_proba",
        thresholds=np.arange(0.20, 0.61, 0.01), cv="prefit", refit=False,
    ).fit(texts, labels)
    predictions = tuner.predict(texts)
    return float(tuner.best_threshold_), {
        "train_count": len(train), "validation_count": len(validation),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f2": float(fbeta_score(labels, predictions, beta=2, zero_division=0)),
    }


def save_model(pipeline, model_path, model_name=MODEL_NAME, threshold=0.5):
    """保存完整 Pipeline 和业务所需的名称、分类阈值。"""
    pipeline.model_name_ = model_name
    pipeline[-1].set_params(threshold=threshold)
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path, compress=3)
    return pipeline


def run(output_dir=DEFAULT_MODEL_PATH.parent, overwrite=False):
    output_dir = Path(output_dir)
    model_path = output_dir / "pipeline.joblib"
    if model_path.exists() and not overwrite:
        raise FileExistsError(f"模型已存在，请加 --overwrite 或指定新目录：{model_path}")

    train = read_csv(DEFAULT_SPLIT_DIR / "train.csv")
    weak = read_csv(DEFAULT_DATA_DIR / "weak_spam.csv")
    samples = train + weak
    threshold, validation = select_threshold(samples)
    pipeline = fit_model(oversample_hard_negatives(samples))
    save_model(pipeline, model_path, threshold=threshold)

    same = evaluate_model(model_path, DEFAULT_SPLIT_DIR / "test.csv", output_dir / "evaluation")
    source = evaluate_model(model_path, DEFAULT_SPLIT_DIR / "source_holdout.csv", output_dir / "source_evaluation")
    summary = {
        "model_name": pipeline.model_name_, "threshold": threshold,
        "train_count": len(train), "weak_sample_count": len(weak),
        "training_sample_count": pipeline.training_sample_count_, "validation": validation,
        "test_accuracy": same["accuracy"], "source_recall": source["recall"],
    }
    (output_dir / "training.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return {"model_path": model_path, "threshold": threshold, "same": same, "source": source}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="训练 TF-IDF + 手写贝叶斯 Pipeline")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_PATH.parent)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run(args.output_dir, args.overwrite)
