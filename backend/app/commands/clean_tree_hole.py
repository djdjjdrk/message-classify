"""pandas 从校园树洞 JSONL 中提取、去重正文，生成无标签 CSV。"""

import argparse
from pathlib import Path

import pandas as pd


def clean(input_path: Path, output_path: Path) -> None:
    records = pd.read_json(input_path, lines=True, dtype=False, encoding="utf-8-sig")
    contents = records.get("detail", pd.Series("", index=records.index)).astype(object)
    contents = contents.where(contents.map(type).eq(str), "").str.strip()
    valid = contents.loc[contents != ""]
    unique = valid.drop_duplicates()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"content": unique, "source": "campus_posts"}).to_csv(
        output_path, index=False, encoding="utf-8-sig", mode="x",
    )
    print(f"总记录数：{len(records)}；空白或非文本：{len(records) - len(valid)}；重复：{len(valid) - len(unique)}；保留：{len(unique)}")
    print(f"输出：{output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="原始 JSONL 文件")
    parser.add_argument("output", type=Path, help="输出 CSV 文件（不能已存在）")
    args = parser.parse_args()
    clean(args.input, args.output)


if __name__ == "__main__":
    main()
