"""读取、清洗样本，按 8:2 划分训练集和测试集。"""

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.model_selection import train_test_split


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_SPLIT_DIR = DEFAULT_DATA_DIR / "split"
DATA_FILES = ("campus_posts.csv", "iad_spam.csv", "chineseharm_spam.csv")


def read_csv(file_path):
    """读取正文、0/1 标签和来源。"""
    file_path = Path(file_path)
    samples = []
    with file_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            samples.append({
                "content": row["content"],
                "label": row["label"],
                "source": row.get("source") or file_path.stem,
            })
    return samples


def load_dataset(data_dir=DEFAULT_DATA_DIR):
    samples = []
    for name in DATA_FILES:
        samples.extend(read_csv(Path(data_dir) / name))
    return samples


def normalize_content(content):
    """统一全半角、不可见字符和连续空白。"""
    content = unicodedata.normalize("NFKC", content)
    characters = []
    for char in content:
        if unicodedata.category(char) != "Cf":
            characters.append(char)
    return re.sub(r"\s+", " ", "".join(characters)).strip()


def clean_dataset(samples):
    """清理空正文、非法标签和重复，标签冲突的正文整组排除。"""
    groups = defaultdict(list)
    removed = []
    before_counts = Counter()
    normalized_count = 0

    for index, sample in enumerate(samples, start=1):
        content = normalize_content(sample.get("content", ""))
        label = sample.get("label", "").strip()
        before_counts[label] += 1
        if content != sample.get("content", ""):
            normalized_count += 1

        reason = None
        if not content:
            reason = "empty_content"
        elif not label:
            reason = "empty_label"
        elif label == "-1":
            reason = "uncertain_label"
        elif label not in {"0", "1"}:
            reason = "invalid_label"
        if reason:
            removed.append({"index": index, "reason": reason, "sample": sample.copy()})
            continue

        cleaned = sample.copy()
        cleaned["content"] = content
        cleaned["label"] = label
        groups[content].append((index, sample, cleaned))

    cleaned_samples = []
    conflict_count = 0
    for group in groups.values():
        labels = set()
        for index, original, cleaned in group:
            labels.add(cleaned["label"])
        if len(labels) > 1:
            conflict_count += 1
            rejected = group
            reason = "conflicting_label"
        else:
            cleaned_samples.append(group[0][2])
            rejected = group[1:]
            reason = "duplicate"
        for index, original, cleaned in rejected:
            removed.append({"index": index, "reason": reason, "sample": original.copy()})

    removed.sort(key=lambda row: row["index"])
    report = {
        "input_count": len(samples),
        "output_count": len(cleaned_samples),
        "normalized_count": normalized_count,
        "label_counts_before": dict(before_counts),
        "label_counts_after": dict(Counter(row["label"] for row in cleaned_samples)),
        "removed_counts": dict(Counter(row["reason"] for row in removed)),
        "conflict_group_count": conflict_count,
        "removed_samples": removed,
    }
    return cleaned_samples, report


def split_dataset(samples, test_size=0.2, random_state=42):
    """清洗后按标签分层划分，固定种子以复现结果。"""
    labels = [sample["label"] for sample in samples]
    train, test = train_test_split(samples, test_size=test_size, random_state=random_state, stratify=labels)
    return [row.copy() for row in train], [row.copy() for row in test]


def save_dataset(samples, file_path):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["content", "label", "source"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(samples)


if __name__ == "__main__":
    samples, report = clean_dataset(load_dataset())
    train, test = split_dataset(samples)
    save_dataset(train, DEFAULT_SPLIT_DIR / "train.csv")
    save_dataset(test, DEFAULT_SPLIT_DIR / "test.csv")
    print(f"清洗前：{report['input_count']} 条；清洗后：{len(samples)} 条")
    print(f"正文格式调整：{report['normalized_count']} 条；排除统计：{report['removed_counts']}")
    print("标签：0=正常，1=垃圾；划分比例 8:2，随机种子 42")
    for name, subset in (("训练集", train), ("测试集", test)):
        print(f"{name}：{len(subset)} 条，类别统计：{dict(Counter(row['label'] for row in subset))}")
    print(f"保存位置：{DEFAULT_SPLIT_DIR}")
