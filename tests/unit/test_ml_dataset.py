"""验证 pandas CSV 读写保留文本、标签、来源和空数据。"""

import pytest

from backend.app.ml.dataset import normalize_content, read_csv, save_dataset


def test_read_csv_preserves_labels_and_uses_filename_for_missing_source(tmp_path):
    path = tmp_path / "samples.csv"
    path.write_text("content,label\n正常留言,0\n垃圾留言,1\n", encoding="utf-8-sig")
    assert read_csv(path) == [
        {"content": "正常留言", "label": "0", "source": "samples"},
        {"content": "垃圾留言", "label": "1", "source": "samples"},
    ]


def test_normalizes_format_without_removing_meaningful_text():
    assert normalize_content("\ufeff  ＡＢＣ\u200b\t学习\n  １２３！  ") == "ABC 学习 123!"
    assert normalize_content("不要刷单！联系 https://example.com?a=1，电话13812345678") == (
        "不要刷单!联系 https://example.com?a=1,电话13812345678"
    )


def test_csv_round_trip_preserves_quotes_newlines_and_numeric_looking_text(tmp_path):
    samples = [
        {"content": '带有逗号,引号"和\n换行的正文', "label": "0", "source": "campus"},
        {"content": "000123", "label": "1", "source": "NA"},
        {"content": "NULL", "label": "0", "source": "nan"},
    ]
    path = tmp_path / "split/train.csv"
    save_dataset(samples, path)
    assert read_csv(path) == samples


def test_empty_source_falls_back_to_filename_and_extra_columns_are_ignored(tmp_path):
    path = tmp_path / "samples.csv"
    path.write_text("content,label,source,extra\n正文,0,,unused\n", encoding="utf-8")
    assert read_csv(path) == [{"content": "正文", "label": "0", "source": "samples"}]


@pytest.mark.parametrize("empty_file", [False, True])
def test_empty_csv_can_be_read(tmp_path, empty_file):
    path = tmp_path / "empty.csv"
    if empty_file:
        path.write_text("", encoding="utf-8")
    else:
        save_dataset([], path)
    assert read_csv(path) == []


def test_csv_writer_keeps_integer_labels_and_ignores_extra_fields(tmp_path):
    path = tmp_path / "labels.csv"
    save_dataset([{"content": "正文", "label": 0, "source": "campus", "extra": "ignored"}], path)
    assert read_csv(path) == [{"content": "正文", "label": "0", "source": "campus"}]
