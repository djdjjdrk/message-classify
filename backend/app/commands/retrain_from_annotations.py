"""读取人工标签，更新训练快照并复用 Pipeline 重训，输出固定测试集对照。

训练数据按正文去重，并排除与测试及来源留出集关联的模板、近似重复组。

用法：
    uv run --project backend python -m backend.app.commands.retrain_from_annotations
    uv run --project backend python -m backend.app.commands.retrain_from_annotations --output-dir backend/artifacts/models/retrained_v2
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.ml.dataset import (
    BACKEND_ROOT, DEFAULT_MODEL_PATH, DEFAULT_SPLIT_DIR,
    normalize_content, read_csv, save_dataset,
)
from backend.app.ml.evaluate import calculate_metrics
from backend.app.ml.grouping import build_template_groups
from backend.app.ml.train import fit_model, oversample_hard_negatives, save_model, select_threshold
from backend.app.models import Message

DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "artifacts" / "models" / "retrained"
SOURCE_TAG = "manual_annotation"
LABEL_MAP = {"normal": 0, "spam": 1}


def load_corrections():
    """读取人工标签，按规范化正文去重；同一正文保留最近更新的一条。"""
    with SessionLocal() as session:
        rows = session.execute(
            select(Message.content, Message.manual_label)
            .where(Message.manual_label.is_not(None))
            .where(Message.deleted_at.is_(None))
            .order_by(Message.updated_at.asc(), Message.id.asc())
        ).all()

    data = pd.DataFrame(rows, columns=["content", "label"])
    data["content"] = data["content"].fillna("").map(normalize_content)
    data["label"] = data["label"].map(LABEL_MAP)
    valid = data.loc[data["content"].ne("") & data["label"].notna()]
    latest = valid.groupby("content", sort=False)["label"].last()
    return latest.astype(int).to_dict(), len(data), len(data) - len(valid)


def build_corrected_training(corrections, train_samples, test_samples):
    """更新人工标签；精确、模板及近似重复组都不得跨越固定评估集。"""
    test_texts = {normalize_content(row["content"]) for row in test_samples}
    correction_rows = [{"content": text, "label": str(label)} for text, label in corrections.items()]
    combined = list(train_samples) + list(test_samples) + correction_rows
    groups, _ = build_template_groups(combined)
    start = len(train_samples)
    protected_groups = set(groups[start:start + len(test_samples)])
    correction_groups = groups[start + len(test_samples):]
    stats = {"annotated_total": len(corrections), "updated": 0, "added": 0, "excluded_test_overlap": 0, "label_changed": 0,
             "excluded_group_overlap": 0, "removed_training_overlap": 0}
    retained = [row for row, group in zip(train_samples, groups) if group not in protected_groups]
    stats["removed_training_overlap"] = len(train_samples) - len(retained)
    train_by_text = {normalize_content(row["content"]): row.copy() for row in retained}

    for (text, label), group in zip(corrections.items(), correction_groups):
        original_text = text
        text = normalize_content(text)
        if text in test_texts:
            stats["excluded_test_overlap"] += 1
            continue
        if group in protected_groups:
            stats["excluded_group_overlap"] += 1
            continue
        if text in train_by_text:
            row = train_by_text[text]
            if int(row["label"]) != label:
                stats["label_changed"] += 1
            row["label"] = str(label)
            stats["updated"] += 1
        else:
            row = {"content": original_text, "label": str(label), "source": SOURCE_TAG}
            train_by_text[text] = row
            stats["added"] += 1

    samples = list(train_by_text.values())
    return samples, stats


def train_from_samples(samples, model_path, model_name, alpha=1.0, overwrite=False, threshold=0.5):
    """人工纠正后复用同一套 Pipeline 训练。"""
    model_path = Path(model_path)
    if model_path.exists() and not overwrite:
        raise FileExistsError(f"模型文件已存在，请为新版本指定其他目录或加 --overwrite：{model_path}")

    pipeline = fit_model(oversample_hard_negatives(samples), alpha=alpha)
    return save_model(pipeline, model_path, model_name, threshold)


def evaluate_on_test(model_path, test_samples):
    """每个模型用自己的训练词表转换同一份测试正文。"""
    pipeline = joblib.load(model_path)
    contents = [row["content"] for row in test_samples]
    y_test = [int(row["label"]) for row in test_samples]
    probabilities = pipeline.predict_proba(contents)
    predictions = (probabilities[:, 1] >= pipeline[-1].threshold).astype(int)
    report = calculate_metrics(y_test, predictions)
    report.update({
        "model_name": pipeline.model_name_,
        "model_path": str(Path(model_path).resolve()),
        "model_sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
        "training_sample_count": pipeline.training_sample_count_,
        "vocabulary_size": len(pipeline[0].get_feature_names_out()),
        "zero_feature_count": int((pipeline[0].transform(contents).getnnz(axis=1) == 0).sum()),
        "misclassified_count": report["confusion_matrix"]["fp"] + report["confusion_matrix"]["fn"],
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
    train_samples += read_csv(BACKEND_ROOT / "data" / "processed" / "weak_spam.csv")
    test_samples = read_csv(DEFAULT_SPLIT_DIR / "test.csv")
    source_holdout = read_csv(DEFAULT_SPLIT_DIR / "source_holdout.csv")

    corrections, annotated_rows, skipped = load_corrections()
    if not corrections:
        raise SystemExit("数据库中没有可用的人工标签，请先在分类标注页纠正若干条留言后再重训。")

    corrected_samples, correction_stats = build_corrected_training(corrections, train_samples, test_samples + source_holdout)
    correction_stats["annotated_rows"] = annotated_rows
    correction_stats["skipped_invalid"] = skipped
    correction_stats["training_before"] = len(train_samples)
    correction_stats["training_after"] = len(corrected_samples)

    corrected_train_path = output_dir / "train_corrected.csv"
    model_name = model_name or f"{output_dir.name}_{datetime.now().strftime('%Y%m%d%H%M')}"
    model_path = output_dir / "pipeline.joblib"
    threshold, _ = select_threshold(corrected_samples)
    train_from_samples(corrected_samples, model_path, model_name, overwrite=overwrite, threshold=threshold)
    save_dataset(corrected_samples, corrected_train_path)

    baseline = evaluate_on_test(baseline_path, test_samples)
    retrained = evaluate_on_test(model_path, test_samples)
    delta = {key: retrained[key] - baseline[key] for key in ("accuracy", "precision", "recall", "f1")}
    delta["misclassified_count"] = retrained["misclassified_count"] - baseline["misclassified_count"]

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_csv": str((DEFAULT_SPLIT_DIR / "test.csv").resolve()),
        "test_csv_sha256": hashlib.sha256((DEFAULT_SPLIT_DIR / "test.csv").read_bytes()).hexdigest(),
        "corrected_train_csv": str(corrected_train_path.resolve()),
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
        f"与固定评估集正文重合排除 {correction_stats['excluded_test_overlap']} 条，"
        f"模板/近似重复组重合排除 {correction_stats['excluded_group_overlap']} 条，"
        f"原训练记录因关联受保护组移除 {correction_stats['removed_training_overlap']} 条。\n\n{table}\n",
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
    print((model_path.parent / "comparison.md").read_text(encoding="utf-8"))
    print(f"纠正训练快照：{comparison['corrected_train_csv']}")
    print(f"新模型：{model_path}")
