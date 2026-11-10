from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.common.exceptions import BusinessException
from backend.app.models import Message, ReviewRecord


def auto_approve_message(db: Session, message: Message, spam_threshold: float) -> None:
    if (
        message.review_status != "pending"
        or message.prediction_status != "success"
        or message.predicted_label != "normal"
        or message.predicted_probability is None
        or message.predicted_probability > spam_threshold
    ):
        return

    record = ReviewRecord(
        message=message,
        reviewer_id=None,
        review_source="automatic",
        previous_status="pending",
        decision="approved",
        label_snapshot=message.predicted_label,
        model_name_snapshot=message.model_name,
        spam_probability_snapshot=message.predicted_probability,
        normal_threshold_snapshot=spam_threshold,
    )
    message.review_status = "approved"
    # 留言发布时统一提交留言和自动审核记录。
    db.add(record)


def list_pending_reviews(
    db: Session, page: int, page_size: int,
) -> tuple[list[Message], int]:
    count_query = select(func.count()).select_from(Message)
    count_query = count_query.where(Message.deleted_at.is_(None))
    count_query = count_query.where(Message.review_status == "pending")
    total = db.scalar(count_query)

    query = select(Message)
    query = query.options(joinedload(Message.author))
    query = query.where(Message.deleted_at.is_(None))
    query = query.where(Message.review_status == "pending")
    query = query.order_by(Message.created_at.desc(), Message.id.desc())
    query = query.offset((page - 1) * page_size)
    query = query.limit(page_size)
    messages = db.scalars(query).all()
    return list(messages), total  # type: ignore


def list_review_records(
    db: Session, page: int, page_size: int,
) -> tuple[list[ReviewRecord], int]:
    count_query = select(func.count()).select_from(ReviewRecord)
    count_query = count_query.join(ReviewRecord.message)
    count_query = count_query.where(Message.deleted_at.is_(None))
    total = db.scalar(count_query)

    query = select(ReviewRecord)
    query = query.options(joinedload(ReviewRecord.message), joinedload(ReviewRecord.reviewer))
    query = query.join(ReviewRecord.message)
    query = query.where(Message.deleted_at.is_(None))
    query = query.order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
    query = query.offset((page - 1) * page_size)
    query = query.limit(page_size)
    records = db.scalars(query).all()
    return list(records), total  # type: ignore


def review_message(
    db: Session, message_id: int, reviewer_id: int, decision: str, comment: str | None,
) -> None:
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
        if label_snapshot is None and message.prediction_status == "success":
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
