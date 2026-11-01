"""验证跨来源去重和冲突排除不会悄悄改变训练标签。"""

import csv
from copy import deepcopy

import pytest

from backend.app.ml.dataset import (
    clean_dataset,
    normalize_content,
    read_csv,
    save_dataset,
    split_dataset,
)


def test_reading_and_cleaning_keep_original_numeric_labels(tmp_path):
    path = tmp_path / "samples.csv"
    path.write_text("content,label\n正常留言,0\n垃圾留言,1\n", encoding="utf-8-sig")
    samples = read_csv(path)
    assert [sample["label"] for sample in samples] == ["0", "1"]
    cleaned, report = clean_dataset(samples)
    assert cleaned == samples
    assert report["label_counts_after"] == {"0": 1, "1": 1}


def test_normalizes_format_without_removing_meaningful_text():
    assert normalize_content("\ufeff  ＡＢＣ\u200b\t学习\n  １２３！  ") == "ABC 学习 123!"
    text = "不要刷单！联系 https://example.com?a=1，电话13812345678"
    assert normalize_content(text) == "不要刷单!联系 https://example.com?a=1,电话13812345678"


def test_deduplicates_across_sources_and_preserves_input():
    samples = [
        {"content": "  一起\n自习  ", "label": " 0 ", "source": "campus"},
        {"content": "一起 自习", "label": "0", "source": "other"},
        {"content": "兼职日结", "label": "1", "source": "iad"},
    ]
    original = deepcopy(samples)
    cleaned, report = clean_dataset(samples)
    assert samples == original
    assert cleaned == [
        {"content": "一起 自习", "label": "0", "source": "campus"},
        {"content": "兼职日结", "label": "1", "source": "iad"},
    ]
    assert report["removed_counts"] == {"duplicate": 1}
    assert report["removed_samples"] == [
        {"index": 2, "reason": "duplicate", "sample": samples[1]},
    ]
    assert report["label_counts_before"] == {"0": 2, "1": 1}
    assert report["label_counts_after"] == {"0": 1, "1": 1}
    assert report["input_count"] == 3
    assert report["output_count"] == 2


@pytest.mark.parametrize("labels", [
    ["0", "0", "1"],
    ["1", "0", "1"],
    ["0", "1", "0"],
])
def test_excludes_entire_conflicting_group_in_any_label_order(labels):
    samples = [
        {"content": "ＡＢＣ", "label": label, "source": str(index)}
        for index, label in enumerate(labels)
    ]
    samples.append({"content": "独立正文", "label": "0"})
    cleaned, report = clean_dataset(samples)
    assert cleaned == [samples[-1]]
    assert report["conflict_group_count"] == 1
    assert report["removed_counts"] == {"conflicting_label": 3}
    assert [item["sample"] for item in report["removed_samples"]] == samples[:3]


@pytest.mark.parametrize(("sample", "reason"), [
    ({"content": "\ufeff\u200b \n", "label": "0"}, "empty_content"),
    ({"label": "0"}, "empty_content"),
    ({"content": "正文", "label": "  "}, "empty_label"),
    ({"content": "正文"}, "empty_label"),
    ({"content": "正文", "label": "-1"}, "uncertain_label"),
    ({"content": "正文", "label": "2"}, "invalid_label"),
    ({"content": "正文", "label": "NORMAL"}, "invalid_label"),
    ({"content": "正文", "label": "normal"}, "invalid_label"),
    ({"content": "正文", "label": "spam"}, "invalid_label"),
])
def test_rejects_invalid_rows_with_original_data_and_reason(sample, reason):
    cleaned, report = clean_dataset([sample])
    assert cleaned == []
    assert report["removed_counts"] == {reason: 1}
    assert report["removed_samples"] == [
        {"index": 1, "reason": reason, "sample": sample},
    ]


def test_does_not_guess_labels_or_remove_similar_but_distinct_texts():
    samples = [
        {"content": "有人发刷单返利消息，是不是骗子？", "label": "0"},
        {"content": "联系电话13812345678", "label": "1"},
        {"content": "联系电话13812345679", "label": "1"},
    ]
    cleaned, report = clean_dataset(samples)
    assert len(cleaned) == 3
    assert cleaned[0]["label"] == "0"
    assert report["removed_samples"] == []


def test_cleaning_is_repeatable_and_counts_account_for_every_input():
    samples = [
        {"content": " 独立正文 ", "label": "0"},
        {"content": "独立正文", "label": "0"},
        {"content": "冲突", "label": "0"},
        {"content": "冲突", "label": "1"},
        {"content": "", "label": "0"},
    ]
    cleaned, report = clean_dataset(samples)
    assert report["input_count"] == report["output_count"] + len(report["removed_samples"])
    cleaned_again, second_report = clean_dataset(cleaned)
    assert cleaned_again == cleaned
    assert second_report["normalized_count"] == 0
    assert second_report["removed_samples"] == []


def test_empty_input_has_a_valid_empty_report():
    cleaned, report = clean_dataset([])
    assert cleaned == []
    assert report["input_count"] == report["output_count"] == 0
    assert report["label_counts_after"] == {}
    assert report["removed_samples"] == []


def make_split_samples(normal_count=80, spam_count=20):
    return [
        {"content": f"{label} 样本 {index}", "label": label, "source": "test"}
        for label, count in (("0", normal_count), ("1", spam_count))
        for index in range(count)
    ]


def test_split_preserves_class_ratios_and_separates_all_samples():
    samples = make_split_samples()
    original = deepcopy(samples)
    train, test = split_dataset(samples)
    assert len(train) == 80 and len(test) == 20
    assert sum(row["label"] == "0" for row in train) == 64
    assert sum(row["label"] == "0" for row in test) == 16
    train_texts = {row["content"] for row in train}
    test_texts = {row["content"] for row in test}
    assert train_texts.isdisjoint(test_texts)
    assert train_texts | test_texts == {row["content"] for row in samples}
    assert samples == original
    train[0]["content"] = "后续修改"
    assert samples == original


def test_split_is_reproducible_and_seed_controls_selection():
    samples = make_split_samples()
    assert split_dataset(samples) == split_dataset(samples, random_state=42)
    assert split_dataset(samples) != split_dataset(samples, random_state=7)


def test_split_supports_small_datasets_when_both_sides_can_have_two_classes():
    train, test = split_dataset(make_split_samples(2, 2), test_size=0.5)
    assert len(train) == len(test) == 2
    assert {row["label"] for row in train} == {"0", "1"}
    assert {row["label"] for row in test} == {"0", "1"}


def test_saved_splits_can_be_reloaded_without_changing_the_samples(tmp_path):
    samples = make_split_samples()
    samples[0]["content"] = '带有逗号,引号"和\n换行的正文'
    train, test = split_dataset(samples)
    for name, subset in (("train", train), ("test", test)):
        path = tmp_path / "split" / f"{name}.csv"
        save_dataset(subset, path)
        assert read_csv(path) == subset
        with path.open(encoding="utf-8-sig", newline="") as file:
            assert {row["label"] for row in csv.DictReader(file)} == {"0", "1"}
