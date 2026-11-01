"""人工纠正 → 离线重训 → 同一测试集对比。

流程：
1. 从数据库读取未删除且有人工标签的留言，normal/spam 转成 0/1；
2. 按规范化正文去重，原训练集中已有的正文更新标签，新增正文补进训练集；
3. 排除与固定测试集重合的正文，保存纠正训练快照；
4. 用纠正后的训练集拟合新词表并训练同款手写朴素贝叶斯，保存独立模型目录；
5. 用同一份固定测试集分别评估原模型和新模型，输出准确率、精确率、召回率和 F1 对照。

测试集和原模型保持不变；模型预测不作为真实标签。指标持平或下降也如实输出。

用法：
    uv run python -m scripts.retrain_from_annotations
    uv run python -m scripts.retrain_from_annotations --output-dir artifacts/models/retrained_v2
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.ml.dataset import DEFAULT_SPLIT_DIR, PROJECT_ROOT, normalize_content, read_csv, save_dataset
from backend.app.ml.evaluate import calculate_metrics
from backend.app.ml.features import fit_training_features, transform_test_features
from backend.app.ml.naive_bayes import MultinomialNaiveBayes
from backend.app.ml.train import DEFAULT_MODEL_PATH
from backend.app.models import Message

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "models" / "retrained"
CORRECTED_TRAIN_PATH = DEFAULT_SPLIT_DIR / "train_corrected.csv"
SOURCE_TAG = "manual_annotation"
LABEL_MAP = {"normal": 0, "spam": 1}


def load_corrections():
    """读取人工标签，按规范化正文去重；同一正文保留最近更新的一条。"""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(Message.content, Message.manual_label, Message.updated_at)
            .where(Message.manual_label.is_not(None))
            .where(Message.deleted_at.is_(None))
            .order_by(Message.updated_at.asc(), Message.id.asc())
        ).all()
    finally:
        session.close()

    corrections = {}
    skipped = 0
    for content, manual_label, _updated_at in rows:
        label = LABEL_MAP.get(manual_label)
        normalized = normalize_content(content or "")
        if label is None or not normalized:
            skipped += 1
            continue
        # 后写入的覆盖先写入的，保证同一正文只有一个人工结论。
        corrections[normalized] = label
    return corrections, len(rows), skipped


def build_corrected_training(corrections, train_samples, test_samples):
    """更新/补充纠正样本，排除与测试集重合的正文，返回训练快照和统计。"""
    test_texts = {normalize_content(row["content"]) for row in test_samples}
    train_by_text = {}
    for row in train_samples:
        train_by_text[normalize_content(row["content"])] = row

    stats = {"annotated_total": len(corrections), "updated": 0, "added": 0, "excluded_test_overlap": 0, "label_changed": 0}
    for text, label in corrections.items():
        if text in test_texts:
            stats["excluded_test_overlap"] += 1
            continue
        if text in train_by_text:
            row = train_by_text[text]
            if int(row["label"]) != label:
                stats["label_changed"] += 1
            row["label"] = str(label)
            stats["updated"] += 1
        else:
            row = {"content": text, "label": str(label), "source": SOURCE_TAG}
            train_by_text[text] = row
            stats["added"] += 1

    samples = list(train_by_text.values())
    return samples, stats


def train_from_samples(samples, model_path, model_name, alpha=1.0, overwrite=False):
    """用纠正后的训练集拟合词表并训练同一手写算法。"""
    model_path = Path(model_path)
    if model_path.exists() and not overwrite:
        raise FileExistsError(f"模型文件已存在，请为新版本指定其他目录或加 --overwrite：{model_path}")

    vectorizer, X_train, y_train = fit_training_features(samples)
    model = MultinomialNaiveBayes(alpha=alpha).fit(X_train, y_train)
    artifact = {
        "format_version": 1,
        "model_name": model_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "vectorizer": vectorizer,
        "training_sample_count": X_train.shape[0],
        "vocabulary_size": len(vectorizer.get_feature_names_out()),
        "alpha": model.alpha,
        "classes": model.classes_.tolist(),
        "threshold": 0.5,
        "trained_from": SOURCE_TAG,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as output:
        joblib.dump(artifact, output, compress=3)
    return artifact


def evaluate_on_test(model_path, test_samples):
    """每个模型用自己的训练词表转换同一份测试正文。"""
    artifact = joblib.load(model_path)
    X_test, y_test = transform_test_features(artifact["vectorizer"], test_samples)
    probabilities = artifact["model"].predict_proba(X_test)
    predictions = (probabilities[:, 1] >= artifact["threshold"]).astype(int)
    report = calculate_metrics(y_test, predictions)
    report.update({
        "model_name": artifact["model_name"],
        "model_path": str(Path(model_path).resolve()),
        "model_sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
        "training_sample_count": artifact["training_sample_count"],
        "vocabulary_size": artifact["vocabulary_size"],
        "zero_feature_count": int((X_test.getnnz(axis=1) == 0).sum()),
    })
    return report


def format_report(comparison):
    baseline = comparison["baseline"]
    retrained = comparison["retrained"]
    delta = comparison["delta"]
    lines = [
        "| 指标 | 原模型 " + baseline["model_name"] + " | 重训模型 " + retrained["model_name"] + " | 变化 |",
        "| --- | ---: | ---: | ---: |",
    ]
    names = (("准确率", "accuracy"), ("垃圾类精确率", "precision"), ("垃圾类召回率", "recall"), ("垃圾类 F1", "f1"))
    for label, key in names:
        lines.append(
            f"| {label} | {baseline[key]:.2%} | {retrained[key]:.2%} | {delta[key]:+.2%} |"
        )
    lines.append(f"| 误判数 | {baseline['misclassified_count']} | {retrained['misclassified_count']} | {delta['misclassified_count']:+d} |")
    return "\n".join(lines)


def run(output_dir=DEFAULT_OUTPUT_DIR, baseline_path=DEFAULT_MODEL_PATH, model_name=None, overwrite=False):
    output_dir = Path(output_dir)
    train_samples = read_csv(DEFAULT_SPLIT_DIR / "train.csv")
    test_samples = read_csv(DEFAULT_SPLIT_DIR / "test.csv")

    corrections, annotated_rows, skipped = load_corrections()
    if not corrections:
        raise SystemExit("数据库中没有可用的人工标签，请先在分类标注页纠正若干条留言后再重训。")

    corrected_samples, correction_stats = build_corrected_training(corrections, train_samples, test_samples)
    correction_stats["annotated_rows"] = annotated_rows
    correction_stats["skipped_invalid"] = skipped
    correction_stats["training_before"] = len(train_samples)
    correction_stats["training_after"] = len(corrected_samples)

    save_dataset(corrected_samples, CORRECTED_TRAIN_PATH)
    model_name = model_name or f"{output_dir.name}_{datetime.now().strftime('%Y%m%d%H%M')}"
    model_path = output_dir / "pipeline.joblib"
    train_from_samples(corrected_samples, model_path, model_name, overwrite=overwrite)

    baseline = evaluate_on_test(baseline_path, test_samples)
    retrained = evaluate_on_test(model_path, test_samples)
    baseline["misclassified_count"] = baseline["confusion_matrix"]["fp"] + baseline["confusion_matrix"]["fn"]
    retrained["misclassified_count"] = retrained["confusion_matrix"]["fp"] + retrained["confusion_matrix"]["fn"]
    delta = {key: retrained[key] - baseline[key] for key in ("accuracy", "precision", "recall", "f1")}
    delta["misclassified_count"] = retrained["misclassified_count"] - baseline["misclassified_count"]

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_csv": str((DEFAULT_SPLIT_DIR / "test.csv").resolve()),
        "test_csv_sha256": hashlib.sha256((DEFAULT_SPLIT_DIR / "test.csv").read_bytes()).hexdigest(),
        "corrected_train_csv": str(CORRECTED_TRAIN_PATH.resolve()),
        "corrections": correction_stats,
        "baseline": baseline,
        "retrained": retrained,
        "delta": delta,
        "note": "两个模型使用同一份固定测试集与标签；测试文本分别用各自训练词表转换。指标下降也如实记录。",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "comparison.json").open("w", encoding="utf-8") as file:
        json.dump(comparison, file, ensure_ascii=False, indent=2)
    table = format_report(comparison)
    (output_dir / "comparison.md").write_text(
        f"# 人工纠正后重训效果对比\n\n生成时间：{comparison['generated_at']}\n\n"
        f"人工标签 {correction_stats['annotated_total']} 条，其中更新训练样本 {correction_stats['updated']} 条"
        f"（标签变更 {correction_stats['label_changed']} 条）、新增 {correction_stats['added']} 条，"
        f"与固定测试集重合排除 {correction_stats['excluded_test_overlap']} 条。\n\n{table}\n",
        encoding="utf-8",
    )
    return comparison, model_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="人工纠正后重训并与原模型对比")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--baseline-model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--model-name")
    parser.add_argument("--overwrite", action="store_true", help="重训目录下已有模型时覆盖")
    args = parser.parse_args()
    comparison, model_path = run(args.output_dir, args.baseline_model, args.model_name, args.overwrite)
    corrections = comparison["corrections"]
    print(
        f"人工标签 {corrections['annotated_total']} 条：更新 {corrections['updated']} 条"
        f"（变更 {corrections['label_changed']} 条）、新增 {corrections['added']} 条，"
        f"排除测试集重合 {corrections['excluded_test_overlap']} 条"
    )
    print(format_report(comparison))
    print(f"纠正训练快照：{CORRECTED_TRAIN_PATH}")
    print(f"新模型：{model_path}")
