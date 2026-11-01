from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.models import Message
from backend.app.schemas.statistics import ClassificationCounts, ReviewCounts, StatisticsResponse


def get_message_statistics(db: Session) -> StatisticsResponse:
    # 人工标签优先；失败或尚未预测时遗留的模型标签不参与统计。
    effective_label = case(
        (Message.manual_label.is_not(None), Message.manual_label),
        (Message.prediction_status == "success", Message.predicted_label),
        else_=None,
    )
    # 一次聚合获得同一快照，避免分页、关联历史记录或并发写入影响合计。
    query = select(
        func.count().label("total"),
        func.count(case((effective_label == "normal", 1))).label("normal"),
        func.count(case((effective_label == "spam", 1))).label("spam"),
        func.count(case((effective_label.is_(None), 1))).label("unclassified"),
        func.count(case((Message.review_status == "pending", 1))).label("pending"),
        func.count(case((Message.review_status == "approved", 1))).label("approved"),
        func.count(case((Message.review_status == "rejected", 1))).label("rejected"),
    ).where(Message.deleted_at.is_(None))
    counts = db.execute(query).one()
    return StatisticsResponse(
        total=counts.total,
        classification=ClassificationCounts(
            normal=counts.normal, spam=counts.spam, unclassified=counts.unclassified,
        ),
        review=ReviewCounts(
            pending=counts.pending, approved=counts.approved, rejected=counts.rejected,
        ),
    )
