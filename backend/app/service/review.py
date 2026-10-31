from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.common.exceptions import BusinessException
from backend.app.models import Message, ReviewRecord


def list_pending_reviews(db: Session, *, page: int, page_size: int) -> tuple[list[Message], int]:
    count_query = select(func.count()).select_from(Message)
    count_query = count_query.where(Message.deleted_at.is_(None))
    count_query = count_query.where(Message.review_status == "pending")
    total = db.scalar(count_query)
    if total is None:
        total = 0

    query = select(Message)
    query = query.options(joinedload(Message.author))
    query = query.where(Message.deleted_at.is_(None))
    query = query.where(Message.review_status == "pending")
    query = query.order_by(Message.created_at.desc(), Message.id.desc())
    query = query.offset((page - 1) * page_size)
    query = query.limit(page_size)
    messages = db.scalars(query).all()
    return list(messages), total


def list_review_records(db: Session, *, page: int, page_size: int) -> tuple[list[ReviewRecord], int]:
    count_query = select(func.count()).select_from(ReviewRecord)
    count_query = count_query.join(ReviewRecord.message)
    count_query = count_query.where(Message.deleted_at.is_(None))
    total = db.scalar(count_query)
    if total is None:
        total = 0
    query = select(ReviewRecord)
    query = query.join(ReviewRecord.message)
    query = query.where(Message.deleted_at.is_(None))
    query = query.options(joinedload(ReviewRecord.message), joinedload(ReviewRecord.reviewer))
    query = query.order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
    query = query.offset((page - 1) * page_size)
    query = query.limit(page_size)
    records = db.scalars(query).all()
    return list(records), total


def review_message(
    db: Session, *, message_id: int, reviewer_id: int, decision: str, comment: str | None,
) -> None:
    if decision != "approved" and decision != "rejected":
        raise BusinessException("审核决定无效", code=422)
    if comment is not None:
        comment = comment.strip()
        if not comment:
            comment = None
    if decision == "rejected" and comment is None:
        raise BusinessException("驳回时请填写原因", code=422)
    if comment is not None and len(comment) > 500:
        raise BusinessException("审核说明不能超过 500 个字符", code=422)
    query = select(Message)
    query = query.where(Message.id == message_id)
    query = query.where(Message.deleted_at.is_(None))
    try:
        message = db.scalar(query)
        if message is None:
            raise BusinessException("留言不存在或已删除", code=404)
        if message.review_status != "pending":
            raise BusinessException("留言已审核，请刷新列表", code=409)

        label_snapshot = message.manual_label
        if label_snapshot is None:
            if message.prediction_status == "success":
                label_snapshot = message.predicted_label

        record = ReviewRecord(
            message_id=message.id,
            reviewer_id=reviewer_id,
            review_source="manual",
            previous_status=message.review_status,
            decision=decision,
            label_snapshot=label_snapshot,
            comment=comment,
        )
        message.review_status = decision
        db.add(record)
        # 审核状态与历史一起提交，失败时一起回滚。
        db.commit()
    except (SQLAlchemyError, BusinessException):
        db.rollback()
        raise
