"""验证广告正文提取、重复处理与来源合并，避免把法律说明混入样本。"""

import csv

import pytest
from openpyxl import Workbook

from scripts.prepare_iad import prepare, read_descriptions


def make_xlsx(path, descriptions, header="广告内容描述"):
    book = Workbook()
    sheet = book.active
    sheet.title = "Sheet1"
    # 正文故意放在 C 列，确保按列名定位而非固定读取 B 列。
    sheet.append(("广告名称", "违法条文", header))
    for text in descriptions:
        sheet.append(("名称不能作为正文", "法律条款不能作为正文", text))
    book.save(path)
    book.close()


def campus_csv(path, texts):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["content", "label"])
        writer.writerows((text, 0) for text in texts)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def test_reads_only_named_advertising_column(tmp_path):
    source = tmp_path / "source.xlsx"
    make_xlsx(source, [' 广告正文，含"引号"\n换行 ', None])
    assert read_descriptions(source) == ("Sheet1", [' 广告正文，含"引号"\n换行 ', ""])


def test_filters_notes_duplicates_and_cross_source_conflicts(tmp_path):
    source = tmp_path / "source.xlsx"
    campus = tmp_path / "campus.csv"
    make_xlsx(source, [" 低门槛高收益 ", "违法内容：低门槛高收益", None,
                       "违法内容：无风险提示", "食堂今天吃什么", "投资高额回报"])
    campus_csv(campus, ["食堂今天吃什么"])
    result = prepare(source, campus, tmp_path / "out")
    assert result["raw_records"] == 6
    assert result["selected_iad_records"] == 2
    assert result["combined_label_counts"] == {"0": 1, "1": 2}
    assert read_csv(tmp_path / "out/combined/labeled_posts.csv") == [
        {"content": "食堂今天吃什么", "label": "0"},
        {"content": "低门槛高收益", "label": "1"},
        {"content": "投资高额回报", "label": "1"},
    ]
    sources = read_csv(tmp_path / "out/combined/labeled_posts_with_source.csv")
    assert [row["source"] for row in sources] == ["ruc_tree_hole", "iad_part1", "iad_part1"]


def test_sampling_is_reproducible_without_repeating_samples(tmp_path):
    source = tmp_path / "source.xlsx"
    campus = tmp_path / "campus.csv"
    make_xlsx(source, [f"广告样本{i}" for i in range(10)])
    campus_csv(campus, ["校园讨论"])
    for name in ("first", "second"):
        result = prepare(source, campus, tmp_path / name, limit=3, seed=7)
        assert result["selected_iad_records"] == 3
    first = tmp_path / "first/iad/spam_posts_part1.csv"
    second = tmp_path / "second/iad/spam_posts_part1.csv"
    assert first.read_bytes() == second.read_bytes()
    assert len({row["content"] for row in read_csv(first)}) == 3
    before = first.read_bytes()
    with pytest.raises(FileExistsError):
        prepare(source, campus, tmp_path / "first")
    assert first.read_bytes() == before


def test_missing_advertising_column_fails_instead_of_guessing(tmp_path):
    source = tmp_path / "source.xlsx"
    make_xlsx(source, ["法律内容"], header="法律说明")
    with pytest.raises(ValueError, match="广告内容描述"):
        read_descriptions(source)


def test_rejects_formulas_in_advertising_column(tmp_path):
    source = tmp_path / "source.xlsx"
    make_xlsx(source, ['=CONCAT("广告", "正文")'])
    with pytest.raises(ValueError, match="不接受公式"):
        read_descriptions(source)


@pytest.mark.parametrize("duplicate", ["column", "sheet"])
def test_rejects_ambiguous_advertising_columns(tmp_path, duplicate):
    source = tmp_path / "source.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append(["广告内容描述"])
    sheet.append(["广告正文"])
    if duplicate == "column":
        sheet.cell(1, 2, "广告内容描述")
    else:
        book.copy_worksheet(sheet)
    book.save(source)
    book.close()
    with pytest.raises(ValueError, match="广告内容描述"):
        read_descriptions(source)
