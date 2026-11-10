"""防止将有害话题、情绪表达或普通询问直接变成垃圾标签。"""

import csv
import json

import pytest

from backend.app.commands.prepare_chineseharm import CATEGORIES, eligible, normalize, prepare, template_key


@pytest.mark.parametrize("text,category", [
    ("你这人真烦，天天吵架", "谩骂引战"),
    ("体育课上老师提醒我们不要参与赌博", "博彩"),
    ("举报这些骗子，不要给他们转账", "欺诈"),
    ("我每天轻松赚五百，今天心情很好", "欺诈"),
    ("有没有同城约会的，认识一下", "低俗色情"),
    ("求抖音代发渠道，有没有人介绍", "黑产广告"),
    ("q28t2典top", "博彩"),
    ("靠谱的平台多的是，尽量选大平台，平台返佣金自己谈", "博彩"),
])
def test_does_not_map_category_or_personal_discussion_to_spam(text, category):
    assert not eligible(normalize(text), category)[0]


@pytest.mark.parametrize("text,category", [
    ("专业补单刷销量，需要的私信我", "黑产广告"),
    ("零投资日赚五百，想做兼职的联系我", "欺诈"),
    ("博彩平台首充送红包，注册领取奖励", "博彩"),
    ("出售成人写真视频，十元一套，私聊联系", "低俗色情"),
])
def test_keeps_explicit_promotional_combinations(text, category):
    assert eligible(normalize(text), category)[0]


def test_normalizes_format_and_uses_contacts_only_in_duplicate_key():
    assert normalize(" ＡＢＣ\u200b\r\n  １２３ ") == "ABC 123"
    first = "专业补单刷销量，微信: abc12345，五元一单"
    second = "专业补单刷销量，微信: xyz98765，五元一单"
    assert template_key(first) == template_key(second)
    assert template_key("dy代发一单10元，联系我") == template_key("抖音代发一单20元，联系我")
    assert "请直接注册账户" in template_key("https://example.com/请直接注册账户")
    assert template_key("https://example.com/请直接注册账户") != template_key("http://another.com/涨粉链接")


def write_inputs(root):
    root.mkdir()
    data = {
        "黑产广告": ["专业补单刷销量兼职，微信: abc12345，五元一单", "专业补单刷销量兼职，微信: xyz98765，五元一单",
                   "专业补单刷销量兼职，微信: abc12345，五元一单", "\u200b", "专业抖音视频代发，需要的私聊联系我，长期合作每天结账"],
        "欺诈": ["专业补单刷销量兼职，微信: abc12345，五元一单", "零投资日赚五百，想做兼职的联系我"],
        "博彩": ["博彩平台首充送红包，注册领取奖励", "上体育课讨论为什么不能赌博"],
        "低俗色情": ["有没有同城约会的，认识一下", "出售成人写真视频，十元一套，私聊联系"],
    }
    for category, slug in CATEGORIES:
        (root/f"{slug}.json").write_text(json.dumps([{"文本": text, "标签": category} for text in data[category]], ensure_ascii=False), encoding="utf-8")


def test_pipeline_counts_priority_sampling_and_provenance(tmp_path):
    inputs = tmp_path/"inputs"
    write_inputs(inputs)
    report = prepare(inputs, tmp_path/"out", target=2)
    with (tmp_path/"out/spam_samples.csv").open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames == ["content", "label", "source"]
        samples = list(reader)
    assert len(samples) == 2 and all(row["source"].endswith("/黑产广告") for row in samples)
    assert all(row["label"] == "1" for row in samples)
    assert report["categories"]["黑产广告"]["within_exact_duplicates"] == 1
    assert report["categories"]["黑产广告"]["template_duplicates"] == 1
    assert report["categories"]["欺诈"]["cross_exact_duplicates"] == 1
    for counts in report["categories"].values():
        assert counts["raw"] == counts["empty_or_invalid"] + counts["within_exact_duplicates"] + counts["policy_excluded"] + counts["eligible"]
        assert counts["eligible"] == counts["cross_exact_duplicates"] + counts["template_duplicates"] + counts["near_duplicates"] + counts["pool"]
    prepare(inputs, tmp_path/"repeat", target=2)
    assert (tmp_path/"out/spam_samples.csv").read_bytes() == (tmp_path/"repeat/spam_samples.csv").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(inputs, tmp_path/"out")


def test_shortfall_is_reported_without_filling_or_relabeling(tmp_path):
    inputs = tmp_path/"inputs"
    write_inputs(inputs)
    report = prepare(inputs, tmp_path/"out", target=1500)
    assert report["totals"]["selected"] == report["totals"]["pool"]
    assert report["shortfall"] == 1500 - report["totals"]["selected"]


def test_removes_minor_rewrites_with_a_traceable_match(tmp_path):
    inputs = tmp_path/"inputs"
    inputs.mkdir()
    texts = ["专业抖音代发视频，长期招募兼职人员，零费用日结，提供素材，感兴趣的联系我，长期合作。",
             "专业抖音代发视频，长期招募兼职人员，零费用日结，提供素材，感兴趣的私信我，长期合作。"]
    for category, slug in CATEGORIES:
        rows = [{"文本": text} for text in texts] if category == "黑产广告" else []
        (inputs/f"{slug}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = prepare(inputs, tmp_path/"out")
    assert report["totals"]["near_duplicates"] == 1
    assert report["totals"]["selected"] == 1
    with (tmp_path/"out/audit/near_duplicates.csv").open(encoding="utf-8-sig", newline="") as file:
        pairs = list(csv.DictReader(file))
    assert len(pairs) == 1 and pairs[0]["duplicate_of"]
