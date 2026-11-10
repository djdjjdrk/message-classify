"""防止模板变体、传递近似重复或来源留出样本进入训练侧。"""

from backend.app.ml.grouping import build_template_groups, grouped_holdout_indices


def test_contact_and_price_variants_stay_together_across_labels_and_sources():
    samples = [
        {"content": "专业补单刷销量，微信: abc12345，10元一单", "label": "1", "source": "ads"},
        {"content": "专业补单刷销量，微信: xyz98765，20元一单", "label": "0", "source": "campus"},
        {"content": "今天图书馆几点关门", "label": "0", "source": "campus"},
    ]
    groups, _ = build_template_groups(samples)
    assert groups[0] == groups[1] != groups[2]
    assert samples[0]["content"].endswith("10元一单")
    assert samples[1]["label"] == "0"


def test_near_duplicate_groups_include_transitive_connections():
    # A 与 C 的序列相似度低于 .90，仍通过 B 连在同一组。
    texts = [
        "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉",
        "新乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉",
        "新乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申末",
    ]
    # 长度 20 的两处差异仍恰为 .90；提高到 .94 使 A-C 只经由 B 连通。
    groups, report = build_template_groups([{"content": text} for text in texts], sequence_threshold=.94)
    assert len(set(groups)) == 1
    assert report["largest_group"] == 3
    assert all(edge["method"] == "near_duplicate" for edge in report["edges"])


def test_fixed_fold_keeps_whole_groups_and_is_repeatable():
    samples = [{"label": str(label)} for label in (0, 1) for _ in range(20)]
    groups = [f"{label}-{i//2}" for label in (0, 1) for i in range(20)]
    train, test = grouped_holdout_indices(samples, groups)
    again_train, again_test = grouped_holdout_indices(samples, groups)
    assert train.tolist() == again_train.tolist()
    assert test.tolist() == again_test.tolist()
    assert {groups[i] for i in train}.isdisjoint(groups[i] for i in test)
    assert set(train) | set(test) == set(range(len(samples)))
