"""把候选正文发布到系统，作为人工标注的素材（不写任何人工标签）。

用途：在分类标注页积累足够的人工纠正样本，供 `scripts.retrain_from_annotations`
重训对比。脚本只做发布，标签一律由管理员在页面上人工选择。

默认取 `artifacts/models/baseline/extra_evaluation/errors.csv`，
即现模型在合成补充集上的误判样本——优先纠正这些更容易体现重训效果。

用法：
    uv run python -m scripts.seed_annotation_candidates --dry-run
    uv run python -m scripts.seed_annotation_candidates --limit 30
"""

import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.ml.dataset import PROJECT_ROOT, normalize_content
from backend.app.models import Message, User
from backend.app.service.message import create_message

DEFAULT_CSV = PROJECT_ROOT / "artifacts" / "models" / "baseline" / "extra_evaluation" / "errors.csv"


def load_candidates(csv_path=DEFAULT_CSV):
    """读取候选正文；坏行和重复正文直接跳过。"""
    rows = []
    seen = set()
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            content = (row.get("content") or "").strip()
            key = normalize_content(content)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({
                "content": content,
                "reference_label": row.get("true_label") or "",
                "predicted_label": row.get("predicted_label") or "",
                "reference_note": row.get("error_type") or "",
            })
    return rows


def existing_texts(session):
    """已存在的正文（含已删除），避免重复发布。"""
    rows = session.execute(select(Message.content)).all()
    return {normalize_content(content) for (content,) in rows}


def pick_author(session, username=None):
    if username:
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            raise SystemExit(f"用户不存在：{username}")
        return user
    user = session.scalar(select(User).where(User.role == "student").order_by(User.id))
    if user is None:
        raise SystemExit("没有 student 账号，请先运行 scripts.init_db --seed-users")
    return user


def run(csv_path=DEFAULT_CSV, limit=30, username=None, dry_run=False):
    candidates = load_candidates(csv_path)
    session = SessionLocal()
    try:
        known = existing_texts(session)
        author = pick_author(session, username)
        author_name = author.username
        pending = [row for row in candidates if normalize_content(row["content"]) not in known][:limit]
        if not pending:
            print("没有新的候选正文可发布（都已存在或已用完）。")
            return []

        if dry_run:
            print(f"[dry-run] 作者 {author_name}，将发布 {len(pending)} 条（不写入数据库）：")
            for index, row in enumerate(pending, start=1):
                print(f"{index:>2}. [参考标签 {row['reference_label'] or '?'}] {row['content'][:42]}")
            return pending

        posted = []
        for row in pending:
            message = create_message(session, author_id=author.id, content=row["content"])
            posted.append({
                "id": message.id,
                "content": message.content,
                "prediction_status": message.prediction_status,
                "predicted_label": message.predicted_label,
                "spam_probability": message.predicted_probability,
                "reference_label": row["reference_label"],
            })
    finally:
        session.close()

    print(f"已发布 {len(posted)} 条留言（作者 {author_name}）。下一步在「分类标注」页逐条选人工标签：")
    print(f"{'ID':>4}  {'模型预测':<8} {'垃圾概率':>8}  {'GPT参考':<6} 正文")
    for item in posted:
        probability = item["spam_probability"]
        shown = f"{probability:.1%}" if probability is not None else "-"
        print(f"{item['id']:>4}  {item['predicted_label'] or item['prediction_status']:<8} {shown:>8}  {item['reference_label']:<6} {item['content'][:36]}")
    print("\n提醒：GPT 生成数据的标签只是参考，请按自己的判断点选；标注完成后运行：")
    print("  uv run python -m scripts.retrain_from_annotations --overwrite")
    return posted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="发布待人工标注的候选留言")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--username", help="发布者账号，默认取第一个 student")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.csv, args.limit, args.username, args.dry_run)
