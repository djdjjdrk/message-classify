"""加载模型预测测试集，保存指标、预测结果和误判明细。"""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import load_npz
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from backend.app.ml.dataset import DEFAULT_SPLIT_DIR, read_csv
from backend.app.ml.features import DEFAULT_FEATURE_DIR
from backend.app.ml.train import DEFAULT_MODEL_PATH


def calculate_metrics(y_true, y_pred):
    """以 1（垃圾）为正类计算指标，分母为零时取 0。"""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel().tolist()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", pos_label=1, zero_division=0,
    )
    return {
        "sample_count": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def evaluate_model(model_path=DEFAULT_MODEL_PATH, feature_dir=DEFAULT_FEATURE_DIR,
                   test_csv=DEFAULT_SPLIT_DIR / "test.csv", output_dir=None):
    model_path = Path(model_path)
    feature_dir = Path(feature_dir)
    test_csv = Path(test_csv)
    if output_dir is None:
        output_dir = model_path.parent / "evaluation"
    output_dir = Path(output_dir)

    artifact = joblib.load(model_path)
    X_test = load_npz(feature_dir / "X_test.npz")
    y_test = np.load(feature_dir / "y_test.npy", allow_pickle=False)
    samples = read_csv(test_csv)
    probabilities = artifact["model"].predict_proba(X_test)
    predictions = (probabilities[:, 1] >= artifact["threshold"]).astype(int)
    report = calculate_metrics(y_test, predictions)
    zero_features = X_test.getnnz(axis=1) == 0
    matrix = report["confusion_matrix"]
    report.update({
        "model_name": artifact["model_name"],
        "model_path": str(model_path.resolve()),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "test_csv_sha256": hashlib.sha256(test_csv.read_bytes()).hexdigest(),
        "threshold": artifact["threshold"],
        "label_counts": {"0": matrix["tn"] + matrix["fp"], "1": matrix["fn"] + matrix["tp"]},
        "zero_feature_count": int(sum(zero_features)),
        "offline_zero_feature_policy": "predict_from_class_prior",
        "online_zero_feature_policy": "no_features_manual_annotation",
        "misclassified_count": matrix["fp"] + matrix["fn"],
    })

    rows = []
    errors = []
    for index, sample in enumerate(samples):
        true_label = int(y_test[index])
        predicted_label = int(predictions[index])
        error_type = ""
        if true_label == 0 and predicted_label == 1:
            error_type = "正常误判为垃圾"
        elif true_label == 1 and predicted_label == 0:
            error_type = "垃圾漏判为正常"
        row = {
            "sample_index": index + 1,
            "content": sample["content"],
            "source": sample["source"],
            "true_label": true_label,
            "predicted_label": predicted_label,
            "spam_probability": float(probabilities[index, 1]),
            "is_correct": int(true_label == predicted_label),
            "no_known_features": int(zero_features[index]),
            "error_type": error_type,
        }
        rows.append(row)
        if true_label != predicted_label:
            errors.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    for name, selected in (("predictions.csv", rows), ("errors.csv", errors)):
        with (output_dir / name).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(selected)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="评估朴素贝叶斯")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--feature-dir", type=Path, default=DEFAULT_FEATURE_DIR)
    parser.add_argument("--test-csv", type=Path, default=DEFAULT_SPLIT_DIR / "test.csv")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    report = evaluate_model(args.model_path, args.feature_dir, args.test_csv, args.output_dir)
    print(f"模型：{report['model_name']}；测试样本：{report['sample_count']}")
    for name, key in (("准确率", "accuracy"), ("精确率", "precision"), ("召回率", "recall"), ("F1", "f1")):
        print(f"{name}：{report[key]:.4%}")
    matrix = report["confusion_matrix"]
    print("混淆矩阵（行=真实，列=预测，顺序为 0、1）：")
    print(np.array([[matrix["tn"], matrix["fp"]], [matrix["fn"], matrix["tp"]]]))
    print(f"误判：{report['misclassified_count']} 条；全零特征：{report['zero_feature_count']} 条（计入评估）")
    print(f"保存位置：{args.output_dir or args.model_path.parent / 'evaluation'}")
