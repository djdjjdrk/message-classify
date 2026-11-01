"""从校园树洞 JSONL 中提取、去重正文，生成无标签 CSV。"""

import argparse
import csv
import json
from pathlib import Path


def clean(input_path: Path, output_path: Path) -> None:
    seen: set[str] = set()
    texts: list[str] = []
    total = skipped = duplicates = 0

    with input_path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, 1):
            total += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {line_number} 行不是有效 JSON：{exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"第 {line_number} 行不是 JSON 对象")
            detail = record.get("detail")
            if not isinstance(detail, str) or not detail.strip():
                skipped += 1
                continue
            content = detail.strip()
            if content in seen:
                duplicates += 1
                continue
            seen.add(content)
            texts.append(content)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 独占创建，避免覆盖已有清洗结果或原始数据。
    with output_path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["content"])
        writer.writerows((text,) for text in texts)

    print(f"总记录数：{total}；空白或非文本：{skipped}；重复：{duplicates}；保留：{len(texts)}")
    print(f"输出：{output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="原始 JSONL 文件")
    parser.add_argument("output", type=Path, help="输出 CSV 文件（不能已存在）")
    args = parser.parse_args()
    clean(args.input, args.output)


if __name__ == "__main__":
    main()
