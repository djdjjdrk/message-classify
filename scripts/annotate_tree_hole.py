"""对正文 CSV 做保守规则辅助初标；0 正常、1 垃圾、-1 待人工核查。"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


RULE_VERSION = "campus-v1"

# 风险词只用于送人工核查，不能直接证明是垃圾。
REVIEW = re.compile(
    r"刷单|返利|返现|日赚|稳赚|博彩|赌博|网赌|贷款|借贷|兼职|招募|招聘|推广|"
    r"引流|代理|优惠|领券|扫码|二维码|链接|https?://|代刷|代写|代做|代抄|"
    r"代考|代课|代签|接单|包过|保过|高分稳过|家教|中介|渠道|免费送|长期接|"
    r"拉人|赚钱|试卷答案|编程题答案|题答案|答案.{0,8}\d+\s*[r元块]|"
    r"出.{0,12}(?:资料|真题|习题|笔记)|出出|批量|订购|下单|招商|福利卡",
    re.IGNORECASE,
)
TRADE = re.compile(
    r"(?:^|[\n，。！! ])(?:出|收|售|转|租)|有偿|带价|价格|\d+\s*[rR元块]|"
    r"私信|私聊|加[微VvQq]|联系方式|联系我|出租|转让|代取|代拿|带饭"
)
ACADEMIC = re.compile(
    r"期末|考试|复习|课程|上课|老师|学分|选课|重修|挂科|挂不|成绩|给分|"
    r"高数|线代|微观|宏观|大物|财会|计量|英语|六级|四级|通识|论文|作业|"
    r"考研|保研|实习|毕业|大一|大二|大三|大四|学长|学姐|辅导员|奖学金"
)
CAMPUS = re.compile(
    r"宿舍|舍友|室友|食堂|图书馆|自习|教室|校区|校内|学校|校园|校医院|"
    r"学生卡|学生证|澡堂|澡房|空调|洗衣|快递|外卖|打印|寝室|寝|楼道|"
    r"主教|南路|沙河|良乡|丰台|海淀|紫操|操场|体育|球场|门禁|保卫处|"
    r"停车|自行车|班车|地铁|公交|拼车|打车|火车|高铁|机场|南站|西站"
)
SOCIAL = re.compile(
    r"好累|心累|焦虑|失眠|睡不着|想家|好想|好饿|饿了|好困|不想学|不想活|"
    r"学不|学完|背不|背完|考不|考试|复习|压力|崩溃|难受|开心|快乐|幸福|"
    r"难过|伤心|孤独|寂寞|恋爱|女朋友|男朋友|分手|脱单|对象|喜欢的人|"
    r"暗恋|喝酒|吃饭|吃什么|好吃|打球|跑步|健身|打游戏|玩游戏|演唱会|"
    r"电视剧|电影|舍友|室友|朋友|同学"
)
def sample_id(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def suggest(content: str) -> tuple[int, str]:
    if REVIEW.search(content):
        return -1, "含推广、招募、链接或代办等信息，须结合语境核查"
    if TRADE.search(content):
        return -1, "交易或有偿服务，需核查是否普通校园互助或商业推广"
    if len(content) < 8:
        return -1, "正文较短，语境不足"
    if len(content) > 200:
        return -1, "长文本，需人工阅读全文确认用途"
    if ACADEMIC.search(content):
        return 0, "课程、学习或学业交流；未检出预设推广及交易线索"
    if CAMPUS.search(content):
        return 0, "校园生活或出行交流；未检出预设推广及交易线索"
    if SOCIAL.search(content):
        return 0, "日常情绪或人际交流；未检出预设推广及交易线索"
    # 提问本身不足以证明内容正常，不将未匹配的记录默认为正常。
    return -1, "现有保守规则无法明确判断，需人工核查"


def annotate(
    input_path: Path,
    output_path: Path,
    decisions_path: Path | None = None,
    audit_path: Path | None = None,
    exclude_uncertain: bool = False,
) -> None:
    decisions = {}
    if decisions_path is not None:
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    output_rows = []
    seen = set()
    with input_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["content"]:
            raise ValueError("输入须为仅含 content 列的清洗 CSV")
        for number, row in enumerate(reader, 2):
            content = row["content"]
            if None in row or not content or content != content.strip():
                raise ValueError(f"第 {number} 行格式或正文无效")
            identifier = sample_id(content)
            if identifier in seen:
                raise ValueError(f"第 {number} 行正文重复，请先清洗")
            seen.add(identifier)
            label, reason = suggest(content)
            method = f"rule:{RULE_VERSION}"
            if identifier in decisions:
                decision = decisions[identifier]
                label, reason = decision["label"], decision["reason"]
                method = "assistant_review"
            if type(label) is not int or label not in (-1, 0, 1) or not reason:
                raise ValueError(f"第 {number} 行标注决定无效")
            output_rows.append({"sample_id": identifier, "content": content, "label": label,
                                "reason": reason, "method": method})
    unknown = set(decisions) - seen
    if unknown:
        raise ValueError("逐条核查记录中有不属于当前输入的样本")
    included_rows = [row for row in output_rows if not exclude_uncertain or row["label"] != -1]
    counts = Counter(row["label"] for row in included_rows)
    if audit_path is not None and output_path.resolve() == audit_path.resolve():
        raise ValueError("复核文件与详细记录不能使用同一路径")
    for path in (output_path, audit_path):
        if path is not None and path.exists():
            raise FileExistsError(f"输出文件已存在：{path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["content", "label"])
        writer.writeheader()
        # 待确认的在最前面，其次为垃圾候选；同类内保留原始顺序。
        priority = {-1: 0, 1: 1, 0: 2}
        for row in sorted(included_rows, key=lambda row: priority[row["label"]]):
            writer.writerow({"content": row["content"], "label": row["label"]})
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("x", encoding="utf-8-sig", newline="") as audit:
            writer = csv.DictWriter(audit, fieldnames=["sample_id", "content", "label", "reason", "method"])
            writer.writeheader()
            writer.writerows(output_rows)
    print(json.dumps({"total": len(included_rows), "normal": counts[0], "spam": counts[1],
                      "pending": counts[-1], "excluded_uncertain": len(output_rows) - len(included_rows),
                      "reviewed_by_assistant": len(decisions)}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, help="新输出 CSV，不能已存在")
    parser.add_argument("--decisions", type=Path, help="按正文 SHA-256 索引的逐条核查 JSON")
    parser.add_argument("--audit", type=Path, help="可选：另存详细判定记录 CSV")
    parser.add_argument("--exclude-uncertain", action="store_true", help="从输出标注表中排除 label=-1 的样本")
    args = parser.parse_args()
    annotate(args.input, args.output, args.decisions, args.audit, args.exclude_uncertain)


if __name__ == "__main__":
    main()
