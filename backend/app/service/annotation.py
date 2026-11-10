from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.common.exceptions import BusinessException
from backend.app.models import AnnotationRecord, Message


def annotate_message(
    db: Session, message_id: int, annotator_id: int,
    label: str, reason: str | None,
) -> bool:
    query = select(Message)
    query = query.where(Message.id == message_id)
    query = query.where(Message.deleted_at.is_(None))
    try:
        message = db.scalar(query)
        if message is None:
            raise BusinessException("留言不存在或已删除", code=404)

        # 同一人工标签重复提交不重复写历史；首次确认模型结果仍会写入。
        if message.manual_label == label:
            db.commit()
            return False

        previous_label = message.manual_label
        if previous_label is None and message.prediction_status == "success":
            previous_label = message.predicted_label

        record = AnnotationRecord(
            message_id=message.id,
            annotator_id=annotator_id,
            previous_label=previous_label,
            new_label=label,
            reason=reason,
        )
        message.manual_label = label
        db.add(record)
        # 标签与历史一起提交，任一写入失败就一起回滚。
        db.commit()
    except (SQLAlchemyError, BusinessException):
        db.rollback()
        raise
    return True


def list_annotation_records(
    db: Session, message_id: int, page: int, page_size: int,
) -> tuple[list[AnnotationRecord], int]:
    query = select(Message)
    query = query.where(Message.id == message_id)
    query = query.where(Message.deleted_at.is_(None))
    message = db.scalar(query)
    if message is None:
        raise BusinessException("留言不存在或已删除", code=404)

    count_query = select(func.count()).select_from(AnnotationRecord)
    count_query = count_query.where(AnnotationRecord.message_id == message_id)
    total = db.scalar(count_query)

    query = select(AnnotationRecord)
    query = query.options(joinedload(AnnotationRecord.annotator))
    query = query.where(AnnotationRecord.message_id == message_id)
    query = query.order_by(AnnotationRecord.created_at.desc(), AnnotationRecord.id.desc())
    query = query.offset((page - 1) * page_size)
    query = query.limit(page_size)
    records = db.scalars(query).all()
    return list(records), total  # type: ignore
