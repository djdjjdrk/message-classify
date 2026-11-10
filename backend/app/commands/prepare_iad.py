"""提取 IAD Part 1 广告正文，去重后与现有校园标注表合并。"""

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter
from contextlib import closing
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


PREFIX = re.compile(r"^违法内容\s*[:：]\s*")
UNCLEAR_REVIEWS = {
    "我一开始以为老师只是理论派的。谁知道人家的实操那么牛，我也沾了光，哈哈，老师简直就是活神仙啊",
    "是朋友一直说用着很好，所以就来买了一个试一下，感觉非常不错。用完皮肤水润润的，皮肤一下子变亮堂了，不是以前皮肤那么干了，总之宝贝非常好建议买",
}


def read_descriptions(path: Path) -> tuple[str, list[str]]:
    """只读取明确命名为“广告内容描述”的列，不拼接名称、法律条款或 URL。"""
    with closing(load_workbook(path, read_only=True, data_only=False, keep_links=False)) as book:
        matches = []
        for sheet in book.worksheets:
            rows = sheet.iter_rows()
            columns = [
                index for index, cell in enumerate(next(rows, ()))
                if str(cell.value or "").strip() == "广告内容描述"
            ]
            if not columns:
                continue
            if len(columns) != 1:
                raise ValueError("广告内容描述列不唯一")
            descriptions = []
            for row in rows:
                cell = row[columns[0]]
                if cell.data_type == "f":
                    raise ValueError("广告正文列不接受公式单元格")
                descriptions.append("" if cell.value is None else str(cell.value))
            matches.append((sheet.title, descriptions))
    if len(matches) != 1:
        raise ValueError("须且仅须有一个包含广告内容描述列的工作表")
    return matches[0]


def clean_description(raw: str) -> tuple[str, str | None]:
    content = PREFIX.sub("", raw.strip()).strip()
    if not content:
        return content, "空正文"
    if content in {"无风险提示", "缺少风险提示", "广告含有淫秽的内容", "卖假表"}:
        return content, "审核说明，不是广告原文"
    if "缺少风险提示" in content or content.startswith(("使用前领导人形象", "违法国内")):
        return content, "广告与审核说明混杂，无法可靠分离"
    if content in {"仅亏一天", "仅限今天", "只敢卖1天"}:
        return content, "缺少广告主体及语境的片段"
    if content in UNCLEAR_REVIEWS:
        return content, "仅评价或赞美，无法仅凭正文确认营销目的"
    return content, None


def read_campus(path: Path) -> list[dict]:
    result = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames not in (["content", "label"], ["content", "label", "source"]):
            raise ValueError("校园标注表须含 content,label 或 content,label,source 列")
        for row in reader:
            if None in row or not row["content"] or row["label"] not in {"0", "1"}:
                raise ValueError("校园标注表含空正文、未确认标签或异常列")
            if row["content"] in seen:
                raise ValueError("校园标注表存在重复正文")
            seen.add(row["content"])
            result.append({**row, "source": (row.get("source") or "").strip() or "ruc_tree_hole"})
    return result


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=fields, dtype=object).to_csv(path, index=False, encoding="utf-8-sig", mode="x")


def prepare(input_path: Path, campus_path: Path, output_root: Path, limit: int = 1000, seed: int = 20261101) -> dict:
    if limit <= 0:
        raise ValueError("抽取上限须为正整数")
    targets = {
        "spam": output_root / "iad/spam_posts_part1.csv",
        "review": output_root / "iad/audit/description_review.csv",
        "report": output_root / "iad/cleaning_report.json",
        "combined": output_root / "combined/labeled_posts.csv",
        "sources": output_root / "combined/labeled_posts_with_source.csv",
    }
    for path in targets.values():
        if path.exists():
            raise FileExistsError(f"输出已存在，不覆盖：{path}")
    sheet, raw_descriptions = read_descriptions(input_path)
    campus = read_campus(campus_path)
    campus_labels = {row["content"]: row["label"] for row in campus}
    frequencies = Counter(raw.strip() for raw in raw_descriptions)
    seen = set()
    candidates = []
    review = []
    removal_counts = Counter()
    for raw, occurrences in frequencies.items():
        content, reason = clean_description(raw)
        if reason:
            status = "excluded"
            removal_counts[reason] += occurrences
        elif content in seen:
            status, reason = "duplicate", "去除说明前缀后正文重复"
            removal_counts[reason] += occurrences
        elif content in campus_labels:
            status = "excluded"
            reason = "与校园标注正文重复" if campus_labels[content] == "1" else "与校园正常标签冲突，排除待核查"
            removal_counts[reason] += occurrences
        else:
            seen.add(content)
            status, reason = "candidate", "按 IAD 违法广告来源映射为垃圾候选；保留首次出现的正文"
            candidates.append({"content": content, "label": "1", "source": "iad_part1"})
            removal_counts["同一原始描述重复"] += occurrences - 1
        review.append({"raw_description": raw, "content": content, "occurrences": occurrences,
                       "status": status, "reason": reason})
    selected = candidates
    if len(candidates) > limit:
        selected = [candidates[i] for i in sorted(random.Random(seed).sample(range(len(candidates)), limit))]
    merged = campus + selected
    report = {
        "source": "https://github.com/socknice/IAD-dataset",
        "original_file": input_path.name,
        "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "campus_sha256": hashlib.sha256(campus_path.read_bytes()).hexdigest(),
        "sheet": sheet,
        "text_column": "广告内容描述",
        "raw_records": len(raw_descriptions),
        "empty_records": frequencies.get("", 0),
        "raw_unique_nonempty_descriptions": len(frequencies) - int("" in frequencies),
        "raw_nonempty_duplicate_records": sum(count - 1 for raw, count in frequencies.items() if raw),
        "removal_counts": dict(removal_counts),
        "valid_unique_candidates": len(candidates),
        "requested_limit": limit,
        "sampling_seed": seed,
        "selected_iad_records": len(selected),
        "campus_records": len(campus),
        "combined_records": len(merged),
        "combined_label_counts": dict(Counter(row["label"] for row in merged)),
        "notes": ["仅做精确去重，仍可能存在相似模板；尚未划分训练集和测试集。",
                  "IAD 标签由来源用途映射，不代表模型预测或已完成用户人工复核。",
                  "未通过重复采样或合成文本补足抽取目标；尚未完成个人敏感信息脱敏。"],
    }
    assert sum(removal_counts.values()) + len(candidates) == len(raw_descriptions)
    assert len({row["content"] for row in merged}) == len(merged)
    write_csv(targets["spam"], ["content", "label", "source"], selected)
    write_csv(targets["review"], ["raw_description", "content", "occurrences", "status", "reason"], review)
    write_csv(targets["combined"], ["content", "label", "source"], merged)
    write_csv(targets["sources"], ["content", "label", "source"], merged)
    targets["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="原始 data_p1.xlsx")
    parser.add_argument("campus", type=Path, help="现有校园 content,label CSV")
    parser.add_argument("output_root", type=Path, help="输出根目录，不覆盖已有输出文件")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261101)
    args = parser.parse_args()
    prepare(args.input, args.campus, args.output_root, args.limit, args.seed)


if __name__ == "__main__":
    main()
