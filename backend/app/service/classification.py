from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.app.models import Message


def list_classification_messages(
    db: Session, *, page: int, page_size: int, category: str = "all",
) -> tuple[list[Message], int]:
    query = select(Message)
    query = query.options(joinedload(Message.author))
    query = query.where(Message.deleted_at.is_(None))

    count_query = select(func.count()).select_from(Message)
    count_query = count_query.where(Message.deleted_at.is_(None))

    if category == "unclassified":
        # 没有人工标签，且模型尚未成功预测或没有预测标签。
        query = query.where(Message.manual_label.is_(None))
        count_query = count_query.where(Message.manual_label.is_(None))
        missing_prediction = or_(
            Message.prediction_status != "success",
            Message.predicted_label.is_(None),
        )
        query = query.where(missing_prediction)
        count_query = count_query.where(missing_prediction)

    elif category == "normal" or category == "spam":
        # and_ 表示数据库里的“并且”，or_ 表示“或者”。
        # 有人工标签就使用人工标签；没有时，才使用成功的模型预测。
        manual_matches = Message.manual_label == category
        model_matches = and_(
            Message.manual_label.is_(None),
            Message.prediction_status == "success",
            Message.predicted_label == category,
        )
        category_matches = or_(manual_matches, model_matches)
        query = query.where(category_matches)
        count_query = count_query.where(category_matches)

    total = db.scalar(count_query)
    if total is None:
        total = 0

    query = query.order_by(Message.created_at.desc(), Message.id.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset)
    query = query.limit(page_size)
    messages = db.scalars(query).all()
    return list(messages), total
