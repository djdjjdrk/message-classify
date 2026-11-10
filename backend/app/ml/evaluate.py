"""sklearn 计算评估指标，pandas 整理预测明细并导出 CSV。"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix

from backend.app.ml.dataset import DEFAULT_MODEL_PATH, DEFAULT_SPLIT_DIR, read_csv


def calculate_metrics(y_true, y_pred):
    """以 1（垃圾）为正类，直接读取 sklearn 的指标计算结果。"""
    if len(y_true) == 0:
        raise ValueError("测试集不能为空")
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel().tolist()
    classes = classification_report(y_true, y_pred, labels=[0, 1], output_dict=True, zero_division=0)
    normal, spam = classes["0"], classes["1"]
    both_classes = tn + fp > 0 and fn + tp > 0
    return {
        "sample_count": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": spam["precision"],
        "recall": spam["recall"],
        "f1": spam["f1-score"],
        "normal_precision": normal["precision"],
        "normal_recall": normal["recall"],
        "normal_f1": normal["f1-score"],
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)) if both_classes else None,
        "macro_f1": classes["macro avg"]["f1-score"],
        "majority_baseline_accuracy": max(tn + fp, fn + tp) / len(y_true),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def evaluate_model(model_path=DEFAULT_MODEL_PATH, test_csv=DEFAULT_SPLIT_DIR / "test.csv", output_dir=None):
    model_path, test_csv = Path(model_path), Path(test_csv)
    output_dir = Path(output_dir) if output_dir is not None else model_path.parent / "evaluation"
    pipeline = joblib.load(model_path)
    data = pd.DataFrame(read_csv(test_csv))
    if data.empty:
        raise ValueError("测试集不能为空")
    contents = data["content"].tolist()
    labels = data["label"].astype(int).to_numpy()
    probabilities = pipeline.predict_proba(contents)[:, 1]
    predictions = (probabilities >= pipeline[-1].threshold).astype(int)
    zero_features = pipeline[0].transform(contents).getnnz(axis=1) == 0
    details = pd.DataFrame({
        "sample_index": range(1, len(data) + 1),
        "content": data["content"],
        "source": data["source"],
        "true_label": labels,
        "predicted_label": predictions,
        "spam_probability": probabilities,
        "is_correct": (labels == predictions).astype(int),
        "no_known_features": zero_features.astype(int),
        "error_type": "",
    })
    details.loc[(labels == 0) & (predictions == 1), "error_type"] = "正常误判为垃圾"
    details.loc[(labels == 1) & (predictions == 0), "error_type"] = "垃圾漏判为正常"
    report = calculate_metrics(labels, predictions)
    matrix = report["confusion_matrix"]
    report.update({
        "model_name": pipeline.model_name_,
        "model_path": str(model_path.resolve()),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "test_csv_sha256": hashlib.sha256(test_csv.read_bytes()).hexdigest(),
        "threshold": pipeline[-1].threshold,
        "label_counts": {"0": matrix["tn"] + matrix["fp"], "1": matrix["fn"] + matrix["tp"]},
        "zero_feature_count": int(zero_features.sum()),
        "offline_zero_feature_policy": "predict_from_class_prior",
        "online_zero_feature_policy": "no_features_manual_annotation",
        "misclassified_count": matrix["fp"] + matrix["fn"],
        "evaluation_input": "raw_csv_transformed_by_saved_model_vectorizer",
        "source_label_counts": {},
        "per_source": {},
    })
    for source, group in details.groupby("source", sort=True):
        report["source_label_counts"][source] = data.loc[group.index, "label"].value_counts(sort=False).to_dict()
        report["per_source"][source] = calculate_metrics(group["true_label"], group["predicted_label"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "report.txt").write_text(
        classification_report(labels, predictions, labels=[0, 1], target_names=["正常", "垃圾"], zero_division=0),
        encoding="utf-8",
    )
    details.to_csv(output_dir / "predictions.csv", index=False, encoding="utf-8-sig")
    details.loc[details["is_correct"] == 0].to_csv(output_dir / "errors.csv", index=False, encoding="utf-8-sig")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="评估朴素贝叶斯")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--test-csv", type=Path, default=DEFAULT_SPLIT_DIR / "test.csv")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir or args.model_path.parent / "evaluation"
    evaluate_model(args.model_path, args.test_csv, output_dir)
    print((output_dir / "report.txt").read_text(encoding="utf-8"))
