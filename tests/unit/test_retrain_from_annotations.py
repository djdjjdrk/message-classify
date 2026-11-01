"""纠正训练集构造与对照表格式的单元测试（不连接数据库）。"""

from scripts.retrain_from_annotations import build_corrected_training, format_report


def test_updates_existing_sample_and_appends_new_one():
    train = [{"content": "食堂最近人很多", "label": "0", "source": "campus_posts"}]
    test = [{"content": "图书馆占座的问题", "label": "1", "source": "chineseharm_spam"}]
    corrections = {
        "食堂最近人很多": 1,
        "新公告：免费领取话费": 1,
        "图书馆占座的问题": 1,
    }

    samples, stats = build_corrected_training(corrections, train, test)

    assert stats["annotated_total"] == 3
    assert stats["updated"] == 1
    assert stats["label_changed"] == 1
    assert stats["added"] == 1
    assert stats["excluded_test_overlap"] == 1

    by_content = {row["content"]: row for row in samples}
    assert len(samples) == 2
    assert by_content["食堂最近人很多"]["label"] == "1"
    assert by_content["新公告：免费领取话费"] == {
        "content": "新公告：免费领取话费", "label": "1", "source": "manual_annotation",
    }


def test_matches_training_rows_after_normalization():
    train = [{"content": "ＡＢＣ 活动通知", "label": "0", "source": "campus_posts"}]
    corrections = {"ABC 活动通知": 0}

    samples, stats = build_corrected_training(corrections, train, [])

    assert stats["updated"] == 1
    assert stats["added"] == 0
    assert len(samples) == 1
    assert samples[0]["label"] == "0"


def test_same_label_does_not_count_as_change():
    train = [{"content": "今晚有人自习吗", "label": "1", "source": "campus_posts"}]
    samples, stats = build_corrected_training({"今晚有人自习吗": 1}, train, [])

    assert stats["updated"] == 1
    assert stats["label_changed"] == 0
    assert samples[0]["label"] == "1"


def test_comparison_table_reports_delta():
    comparison = {
        "baseline": {
            "model_name": "baseline_v1", "accuracy": 0.9833, "precision": 0.9781,
            "recall": 0.9781, "f1": 0.9781, "misclassified_count": 14,
        },
        "retrained": {
            "model_name": "retrained_v1", "accuracy": 0.9904, "precision": 0.9850,
            "recall": 0.9906, "f1": 0.9878, "misclassified_count": 8,
        },
        "delta": {
            "accuracy": 0.0071, "precision": 0.0069, "recall": 0.0125,
            "f1": 0.0097, "misclassified_count": -6,
        },
    }

    table = format_report(comparison)

    assert "| 指标 | 原模型 baseline_v1 | 重训模型 retrained_v1 | 变化 |" in table
    assert "| 准确率 | 98.33% | 99.04% | +0.71% |" in table
    assert "| 误判数 | 14 | 8 | -6 |" in table
