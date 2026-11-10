"""辅助标注需保留正文，且不得把疑难内容直接作为已确认训练标签。"""

import csv
import json

import pytest

from backend.app.commands.annotate_tree_hole import annotate, sample_id, suggest
from backend.app.commands.clean_tree_hole import clean


@pytest.mark.parametrize("records,expected", [
    ([], []),
    ([{"detail": 123}, {"detail": None}, {}], []),
    ([{"detail": " 0001 "}, {"detail": 123}, {"detail": "0001"},
      {"detail": '带有逗号,换行\n和"引号"'}, {"detail": " NA "}],
     ["0001", '带有逗号,换行\n和"引号"', "NA"]),
])
def test_pandas_cleaning_preserves_text_and_removes_invalid_or_duplicate_rows(tmp_path, records, expected):
    source, output = tmp_path / "raw.jsonl", tmp_path / "content.csv"
    source.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8-sig")
    clean(source, output)
    with output.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["content"] for row in rows] == expected
    assert all(row["source"] == "campus_posts" for row in rows)


def write_content(path, texts):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["content"])
        writer.writerows((text,) for text in texts)


def test_risk_keywords_require_context_instead_of_becoming_spam():
    label, _ = suggest("学校有人发刷单返利消息，是不是骗子？")
    assert label == -1
    assert suggest("食堂今天有什么好吃的？")[0] == 0
    assert suggest("这是什么")[0] == -1


def test_preserves_text_and_uses_content_ids_for_review_overrides(tmp_path):
    source = tmp_path / "content.csv"
    output = tmp_path / "annotations.csv"
    audit = tmp_path / "audit.csv"
    decisions = tmp_path / "decisions.json"
    texts = ['食堂今天有什么好吃的？\n我想吃"面条"', "一段需要核查的营销正文", "谁来"]
    write_content(source, texts)
    decisions.write_text(json.dumps({sample_id(texts[1]): {
        "label": 1, "reason": "测试用逐条核查决定",
    }}), encoding="utf-8")
    annotate(source, output, decisions, audit)
    with output.open(encoding="utf-8-sig", newline="") as result:
        rows = list(csv.DictReader(result))
    assert list(rows[0]) == ["content", "label", "source"]
    assert {row["source"] for row in rows} == {"campus_posts"}
    assert [row["content"] for row in rows] == list(reversed(texts))
    assert [row["label"] for row in rows] == ["-1", "1", "0"]
    with audit.open(encoding="utf-8-sig", newline="") as result:
        details = list(csv.DictReader(result))
    assert [row["content"] for row in details] == texts
    assert details[1]["method"] == "assistant_review"
    assert details[0]["method"].startswith("rule:")
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        annotate(source, output, decisions)
    assert output.read_bytes() == original


@pytest.mark.parametrize("case", ["duplicate", "unknown_id", "invalid_label"])
def test_rejects_inconsistent_input_without_writing_output(tmp_path, case):
    source = tmp_path / "content.csv"
    output = tmp_path / "annotations.csv"
    decisions = tmp_path / "decisions.json"
    text = "食堂今天有什么好吃的？"
    write_content(source, [text, text] if case == "duplicate" else [text])
    overrides = {}
    if case == "unknown_id":
        overrides[sample_id("不存在的正文")] = {"label": 0, "reason": "测试"}
    elif case == "invalid_label":
        overrides[sample_id(text)] = {"label": 2, "reason": "测试"}
    decisions.write_text(json.dumps(overrides), encoding="utf-8")
    with pytest.raises(ValueError):
        annotate(source, output, decisions)
    assert not output.exists()


def test_excludes_uncertain_rows_and_keeps_original_audit(tmp_path):
    source = tmp_path / "content.csv"
    output = tmp_path / "annotations.csv"
    audit = tmp_path / "audit.csv"
    texts = ["食堂今天有什么好吃的？", "谁来"]
    write_content(source, texts)
    annotate(source, output, audit_path=audit, exclude_uncertain=True)
    with output.open(encoding="utf-8-sig", newline="") as result:
        assert list(csv.DictReader(result)) == [{"content": texts[0], "label": "0", "source": "campus_posts"}]
    with audit.open(encoding="utf-8-sig", newline="") as result:
        assert [row["label"] for row in csv.DictReader(result)] == ["0", "-1"]
