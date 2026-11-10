"""筛选 ChineseHarm-Bench 广告类垃圾候选；不读取或覆盖正常留言数据。"""

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from backend.app.ml.grouping import URL, template_key


CATEGORIES = (
    ("黑产广告", "black_market_ads"),
    ("欺诈", "fraud"),
    ("博彩", "gambling"),
    ("低俗色情", "sexual_content"),
)
RULE_VERSION = "chineseharm-spam-v1"
INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")
NEGATIVE = re.compile(
    r"^(?:别信|不要信|别加|不要加|警惕|曝光|举报|避雷|我被|被诈骗|被坑|不做|不想做|不接)"
    r"|.{0,15}(?:骗人的|这骗子|那些骗子|这些骗子|收费的狗|收门槛的滚)"
)
CONTACT = re.compile(r"私[信聊我]|联系|加我|[+➕]|[微薇威][信星]|[vV][xX]|[qQ]{1,2}|企鹅|滴滴|斯我|丝我|来人|有意|报名")
PRICE = re.compile(r"\d+(?:\.\d+)?\s*(?:元|米|块|刀|r\b|R\b)|[一二三四五六七八九十百千]+(?:元|米|块)|一[单天次].{0,5}\d+")
BLACK_SERVICE = re.compile(
    r"代[发放]|代fa|[抄炒超吵钞]小说|补[单丹]|刷[单丹手子粉赞评量]|涨[粉赞]|买[赞粉]|"
    r"互刷好评|水军|出评|改销量|改好评|删除差评|处理差评|体验分|动销|粉丝|点[赞关]|"
    r"发[文视图]|发作品|评论[单赚]|抖音|斗音|都音|小红[书薯]|红薯|闲鱼|咸鱼|"
    r"快手|dy|卡网|数据号|代刷|[打哒]字|兼职|拼多多业务|看广.{0,2}告|看广告", re.I
)
BLACK_ACTION = re.compile(r"代[发放]|代fa|补[单丹]|刷[单丹粉赞评]|涨粉|买[粉赞]|承接|专业|招|接单|日结|结账|赚|挣|有偿|一单|发[文视图]|[抄炒超吵钞]小说", re.I)
MONEY = re.compile(r"赚|挣|收益|返利|返现|充值|回本|提现|投资|日入|月入|日赚|兼职|零花|工资|高薪|日结|分红|资产|账户|账号|转账|红包|奖金|注册|实名|万亿|一[次单天].{0,5}\d+")
MONEY_CLAIM = re.compile(r"[零0O]投资|无需.{0,5}(?:押金|费用|投资)|不.{0,3}投.{0,3}资|稳赚|轻松|月入|日赚|日入|高薪|日结|返利|返现|分红|提现|注册.{0,5}送|签到.{0,5}(?:钱|元|资产)|手把手|带你.{0,4}[赚挣]|拉新|免费.{0,4}[赚挣]")
GAMBLE = re.compile(r"博彩|彩票|六合彩|快三|时时彩|赌|包赢|返[利佣]|回[水血]|充值|首充|出款|上分|下分|投注|开奖|娱乐|平台|开业|体育|棋牌|捕鱼|北京赛车|龙虎|彩金|包赔|盈利|长龙|跟单|牛牛|金花|三公|招代理|鸿宝")
GAMBLE_ACTION = re.compile(r"注册|开户|充值|首[充存]|充.{0,5}送|送.{0,5}(?:红|金|元|\d)|返|佣金|招代理|提现|上下分|包赢|包赔|秒下|出款|合作|邀请码|加入|下载|需要.{0,5}(?:联系|私)")
SEX_PRODUCT = re.compile(r"原味|原位|丝袜|色情|黄片|黄[群网]|资源|福利|裸|上门按摩|包夜|援交|看片|片子|小电影|写真|福利姬|色[群图]|私拍|成人|黄[片图]|楼凤|18禁|🔞|h片", re.I)
SEX_SALE = re.compile(r"出售|售卖|卖|价[格目]|门槛|买|出手|送|领取|中介|介绍费|[收付]费|一元|[一二三四五六七八九十百]+元|\d+\s*(?:元|米|块|r\b|yoi|koi)|视频.{0,4}\d+|\d+.{0,3}视频|\d+上门", re.I)
DEMAND = re.compile(r"^(?:求|有没有|有无|谁有|我想做|想做|你代发|你做).{0,50}(?:渠道|介绍|拉我|哪里|多少钱|怎么|有吗|卖不卖)")
RECRUIT = re.compile(r"招|做吗|做不|想做|想[赚挣钱]|感兴趣|了解|来[几人]|一起|兄弟|姐妹|报名|回复|无需|注册|只要|带[你人]|需求|项目|软件|平台|加入|学会|分享|邀请|团队")
DISCUSSION = re.compile(r"^(?:请问|我觉得|我认为|大家觉得|你们觉得|听说|建议|怎么|为什么|是不是|靠谱的平台多的是)")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", INVISIBLE.sub("", unicodedata.normalize("NFKC", text))).strip()


def eligible(content: str, category: str) -> tuple[bool, str]:
    if len(content) < 6:
        return False, "短文本，缺少足够广告语境"
    if NEGATIVE.search(content):
        return False, "疑似反诈提醒、拒绝或抱怨，不直接映射为垃圾"
    if DISCUSSION.search(content):
        return False, "疑似讨论、评价或询问，保守排除"
    if DEMAND.search(content):
        return False, "更像个人询问或需求，无法确认广告推广意图"
    contact = bool(CONTACT.search(content) or URL.search(content))
    price = bool(PRICE.search(content))
    if category == "黑产广告":
        if re.search(r"(?:有吗|有没有|谁有|怎么做|多少钱|是什么|能做吗|代发吗)[?？!！ ]*$", content) and not (contact or price):
            return False, "更像个人询问而非服务推广"
        ok = BLACK_SERVICE.search(content) and (BLACK_ACTION.search(content) or contact or price)
        reason = "明确刷量、代发、补单或相关营销服务线索"
    elif category == "欺诈":
        ok = MONEY.search(content) and (contact or (MONEY_CLAIM.search(content) and RECRUIT.search(content)))
        reason = "收益或兼职招揽，伴联系、引流或诱导获利线索"
    elif category == "博彩":
        ok = GAMBLE.search(content) and (contact or URL.search(content) or GAMBLE_ACTION.search(content))
        reason = "博彩或娱乐平台招揽，伴注册、充值、返佣或联系线索"
    elif category == "低俗色情":
        # 不能仅凭约会、性取向、色情词或个人聊天邀请判为垃圾。
        ok = (SEX_PRODUCT.search(content) and SEX_SALE.search(content)
              and (contact or price or re.search(r"出售|售卖|出手|卖.{0,6}视频|视频.{0,6}元", content))
              and not re.search(r"卖不卖|收门槛的滚|谁教你的", content))
        reason = "明确资源或服务售卖、赠送引流等商业招揽线索"
    else:
        return False, "非本任务允许的来源类别"
    return (True, reason) if ok else (False, "未检出足够明确的广告、诈骗推广或商业引流组合")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=fields, dtype=object).to_csv(path, index=False, encoding="utf-8-sig", mode="x")


def prepare(input_dir: Path, output_dir: Path, target: int = 1500, seed: int = 20261101,
            cosine_threshold: float = .70, sequence_threshold: float = .90) -> dict:
    if target <= 0 or not (0 < cosine_threshold <= 1 and 0 < sequence_threshold <= 1):
        raise ValueError("目标数量及相似度阈值无效")
    targets = {"samples": output_dir / "spam_samples.csv", "json": output_dir / "statistics.json",
               "md": output_dir / "statistics.md", "audit": output_dir / "audit/decisions.csv",
               "near": output_dir / "audit/near_duplicates.csv"}
    if any(path.exists() for path in targets.values()):
        raise FileExistsError("输出已存在，使用新的输出目录以免覆盖人工修改")
    stats = {}; files = []; records = []; candidates = []; global_exact = {}
    for category, slug in CATEGORIES:
        path = input_dir / f"{slug}.json"
        if not path.is_file():
            path = input_dir / f"{category}.json"
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError(f"{path.name} 须为 JSON 列表")
        files.append({"category": category, "file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        counts = Counter(raw=len(raw)); stats[category] = counts; seen = {}
        for number, item in enumerate(raw, 1):
            row = {"id": f"{slug}:{number}", "source": f"chineseharm_bench/{category}", "category": category,
                   "content": "", "stage": "", "reason": "", "duplicate_of": "", "similarity": "", "selected": 0}
            records.append(row)
            if not isinstance(item, dict) or not isinstance(item.get("文本"), str):
                counts["empty_or_invalid"] += 1; row.update(stage="invalid", reason="缺失或非字符串文本"); continue
            text = normalize(item["文本"]); row["content"] = text
            if not text:
                counts["empty_or_invalid"] += 1; row.update(stage="invalid", reason="标准化后为空"); continue
            if text in seen:
                counts["within_exact_duplicates"] += 1
                row.update(stage="within_exact_duplicate", reason="本类别标准化正文完全重复", duplicate_of=seen[text]); continue
            seen[text] = row["id"]
            ok, reason = eligible(text, category)
            if not ok:
                counts["policy_excluded"] += 1; row.update(stage="policy_excluded", reason=reason); continue
            counts["eligible"] += 1
            if text in global_exact:
                counts["cross_exact_duplicates"] += 1
                row.update(stage="cross_exact_duplicate", reason="与更优先类别正文完全重复", duplicate_of=global_exact[text]); continue
            global_exact[text] = row["id"]
            row.update(stage="candidate", reason=reason, key=template_key(text))
            candidates.append(row)

    # 优先保留黑产广告；同类优先保留语境较完整的版本，避免短片段占据模板代表。
    priority = {name: i for i, (name, _) in enumerate(CATEGORIES)}
    candidates.sort(key=lambda row: (priority[row["category"]], -len(row["content"]), row["id"]))
    keyed = {}; unique = []; near_pairs = []
    for row in candidates:
        if row["key"] in keyed:
            other = keyed[row["key"]]
            row.update(stage="template_duplicate", reason="移除格式噪声并归一化链接、账号、数字和常见平台别称后模板相同", duplicate_of=other["id"], similarity=1.0)
            stats[row["category"]]["template_duplicates"] += 1
            near_pairs.append({"id": row["id"], "content": row["content"], "source": row["source"],
                               "duplicate_of": other["id"], "matched_content": other["content"], "method": "template_key", "cosine": 1.0, "sequence_ratio": 1.0})
        else:
            keyed[row["key"]] = row; unique.append(row)
    graph = None
    if len(unique) > 1:
        matrix = TfidfVectorizer(analyzer="char", ngram_range=(2, 4)).fit_transform(row["key"] for row in unique)
        graph = NearestNeighbors(metric="cosine", algorithm="brute", radius=1-cosine_threshold).fit(matrix).radius_neighbors_graph(matrix, mode="distance")
    retained = {}; pool = []
    for i, row in enumerate(unique):
        match = None
        if graph is not None:
            start, end = graph.indptr[i], graph.indptr[i+1]
            for j, distance in sorted(zip(graph.indices[start:end], graph.data[start:end]), key=lambda item: item[0]):
                if j not in retained:
                    continue
                ratio = SequenceMatcher(None, row["key"], unique[j]["key"], autojunk=False).ratio()
                if ratio >= sequence_threshold:
                    match = (unique[j], 1-float(distance), ratio); break
        if match:
            other, cosine, ratio = match
            row.update(stage="near_duplicate", reason="字符 TF-IDF 余弦和序列相似度同时超过阈值", duplicate_of=other["id"], similarity=round(ratio, 6))
            stats[row["category"]]["near_duplicates"] += 1
            near_pairs.append({"id": row["id"], "content": row["content"], "source": row["source"],
                               "duplicate_of": other["id"], "matched_content": other["content"], "method": "char_similarity", "cosine": round(cosine, 6), "sequence_ratio": round(ratio, 6)})
        else:
            retained[i] = row; pool.append(row); stats[row["category"]]["pool"] += 1
    rng = random.Random(seed)
    preferred = [row for row in pool if row["category"] == "黑产广告"]
    others = [row for row in pool if row["category"] != "黑产广告"]
    if len(preferred) >= target:
        selected = rng.sample(preferred, target)
    else:
        selected = preferred + rng.sample(others, min(target-len(preferred), len(others)))
    rng.shuffle(selected)
    for row in selected:
        row["selected"] = 1; stats[row["category"]]["selected"] += 1
    for row in pool:
        row["stage"] = "selected" if row["selected"] else "not_sampled"
    fields = ("raw", "empty_or_invalid", "within_exact_duplicates", "policy_excluded", "eligible", "cross_exact_duplicates", "template_duplicates", "near_duplicates", "pool", "selected")
    category_stats = {name: {field: counts[field] for field in fields} for name, counts in stats.items()}
    for counts in category_stats.values():
        assert counts["raw"] == counts["empty_or_invalid"] + counts["within_exact_duplicates"] + counts["policy_excluded"] + counts["eligible"]
        assert counts["eligible"] == counts["cross_exact_duplicates"] + counts["template_duplicates"] + counts["near_duplicates"] + counts["pool"]
    assert len({row["content"] for row in selected}) == len(selected)
    report = {"source": "https://github.com/zjunlp/ChineseHarm-bench", "rule_version": RULE_VERSION,
              "target": target, "seed": seed, "normalization": "NFKC、不可见格式字符移除、连续空白合并",
              "near_duplicate_thresholds": {"cosine": cosine_threshold, "sequence_ratio": sequence_threshold},
              "files": files, "categories": category_stats,
              "totals": {field: sum(counts[field] for counts in category_stats.values()) for field in fields},
              "shortfall": max(0, target-len(selected)),
              "method": "保守规则筛选、候选抽查、模板和近似去重后固定种子抽样，优先黑产广告",
              "limitations": ["并非全部样本逐条人工确认，规则可能遗漏隐晦推广或误收边界内容。",
                              "近似去重受算法和阈值限制，未保证消除全部语义改写。",
                              "未读取谩骂引战或不违规类别；未合并、改写或覆盖正常校园留言数据。",
                              "未拆分训练验证测试集，未训练模型或计算准确率。"],
              "license": "上游 README 声明数据为 CC BY-NC 4.0；仓库 LICENSE 的 MIT 声明针对软件，二者分开记录。"}
    write_csv(targets["samples"], ["content", "label", "source"], [{**row, "label": 1} for row in selected])
    write_csv(targets["audit"], ["id", "content", "source", "stage", "reason", "duplicate_of", "similarity", "selected"], records)
    write_csv(targets["near"], ["id", "content", "source", "duplicate_of", "matched_content", "method", "cosine", "sequence_ratio"], near_pairs)
    targets["json"].write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = ["# ChineseHarm-Bench 垃圾候选整理报告", "", f"目标 {target} 条，实际保留 {len(selected)} 条，不足 {report['shortfall']} 条。随机种子：`{seed}`。", "",
             "CSV 字段为 `content,label,source`。仅提取原始 JSON 的 `文本`；`label=1` 为本项目辅助映射，`source` 为 `chineseharm_bench/原始类别`，未将来源类别整体当成垃圾。", "",
             "| 原始类别 | 原始数 | 空值/异常 | 类内完全重复 | 规则排除 | 有效候选 | 跨类完全重复 | 模板重复 | 近似重复 | 去重池 | 最终数 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, counts in category_stats.items():
        lines.append("| "+name+" | "+" | ".join(str(counts[field]) for field in fields)+" |")
    lines += ["", "## 统计口径", "", "原始数 = 空值/异常 + 类内完全重复 + 规则排除 + 有效候选。有效候选 = 跨类完全重复 + 模板重复 + 近似重复 + 去重池。最终数是从去重池抽取的数量。", "",
              "标准化采用 NFKC、移除零宽/方向格式字符并合并空白。模板查重另外归一化网址、账号、数字、金额、常见平台别称和抄小说等谐音、移除格式噪声；这些替换不应用到输出正文。", "",
              f"近似查重在模板键上使用字符 2–4 gram TF-IDF，余弦相似度 ≥ {cosine_threshold} 且 SequenceMatcher 比值 ≥ {sequence_threshold} 时移除一条。同类优先保留较完整的版本；跨类优先黑产广告。匹配对见 `audit/near_duplicates.csv`。", "",
              "优先从黑产广告去重池抽取，不够时从其他合格类别随机补充；总数不足时保留全部去重候选并随机打乱顺序，不复制、不合成。逐条处理状态见 `audit/decisions.csv`。", "",
              "## 来源与限制", "", report["source"], "", report["license"], ""]
    lines += ["- "+note for note in report["limitations"]]
    lines += ["", "## 复现", "", "在项目根目录运行，使用新的输出目录：", "", "```powershell",
              f"uv run --project backend python -m backend.app.commands.prepare_chineseharm backend/data/raw/chineseharm/benchmark backend/data/processed/chineseharm_reproduced --target {target} --seed {seed}",
              "```", "", "输入仅为四个指定类别；原文件名与本地英文文件名、校验值见 `backend/data/raw/chineseharm/manifest.json`。"]
    targets["md"].write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"totals": report["totals"], "categories": category_stats, "shortfall": report["shortfall"]}, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="仅含四个指定类别的 benchmark 文件目录")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--target", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=20261101)
    args = parser.parse_args()
    prepare(args.input_dir, args.output_dir, args.target, args.seed)


if __name__ == "__main__":
    main()
