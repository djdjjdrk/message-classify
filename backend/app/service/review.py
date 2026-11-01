"""审核服务：自动通过、待审核查询、人工审核及审核历史。"""

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.common.exceptions import BusinessException
from backend.app.models import Message, ReviewRecord


class ReviewService:
    """审核业务服务类，持有数据库会话并封装审核相关规则。

    职责划分：``Message`` 负责数据结构，``MultinomialNaiveBayes`` 负责分类计算，
    ``TextPreprocessor`` 负责文本归一化，本类只处理审核流程本身。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- 自动通过 ----------
    def auto_approve(self, *, message: Message, spam_threshold: float) -> None:
        """发布时自动通过高置信度正常留言，随留言一起提交审核记录。"""
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
        self.db.add(record)

    # ---------- 查询 ----------
    def count_pending(self) -> int:
        query = select(func.count()).select_from(Message)
        query = query.where(Message.deleted_at.is_(None))
        query = query.where(Message.review_status == "pending")
        total = self.db.scalar(query)
        return total or 0

    def list_pending(self, *, page: int, page_size: int) -> tuple[list[Message], int]:
        """待审核留言及其总数。"""
        query = select(Message)
        query = query.options(joinedload(Message.author))
        query = query.where(Message.deleted_at.is_(None))
        query = query.where(Message.review_status == "pending")
        query = query.order_by(Message.created_at.desc(), Message.id.desc())
        query = query.offset((page - 1) * page_size)
        query = query.limit(page_size)
        messages = self.db.scalars(query).all()
        return list(messages), self.count_pending()

    def list_history(self, *, page: int, page_size: int) -> tuple[list[ReviewRecord], int]:
        """审核历史（含自动通过记录），已删除留言不计入。"""
        count_query = select(func.count()).select_from(ReviewRecord)
        count_query = count_query.join(ReviewRecord.message)
        count_query = count_query.where(Message.deleted_at.is_(None))
        total = self.db.scalar(count_query) or 0

        query = select(ReviewRecord)
        query = query.join(ReviewRecord.message)
        query = query.where(Message.deleted_at.is_(None))
        query = query.options(joinedload(ReviewRecord.message), joinedload(ReviewRecord.reviewer))
        query = query.order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
        query = query.offset((page - 1) * page_size)
        query = query.limit(page_size)
        records = self.db.scalars(query).all()
        return list(records), total

    # ---------- 人工审核 ----------
    def review(
        self, *, message_id: int, reviewer_id: int, decision: str, comment: str | None,
    ) -> None:
        """人工通过或驳回；驳回必须填写原因。"""
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
            message = self.db.scalar(query)
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
            self.db.add(record)
            # 审核状态与历史一起提交，失败时一起回滚。
            self.db.commit()
        except (SQLAlchemyError, BusinessException):
            self.db.rollback()
            raise


# ---------- 兼容旧调用入口 ----------
# 路由与既有测试仍按函数调用，内部统一委托给 ReviewService，避免重复实现业务规则。

def auto_approve_message(db: Session, *, message: Message, spam_threshold: float) -> None:
    ReviewService(db).auto_approve(message=message, spam_threshold=spam_threshold)


def list_pending_reviews(db: Session, *, page: int, page_size: int) -> tuple[list[Message], int]:
    return ReviewService(db).list_pending(page=page, page_size=page_size)


def list_review_records(db: Session, *, page: int, page_size: int) -> tuple[list[ReviewRecord], int]:
    return ReviewService(db).list_history(page=page, page_size=page_size)


def review_message(
    db: Session, *, message_id: int, reviewer_id: int, decision: str, comment: str | None,
) -> None:
    ReviewService(db).review(
        message_id=message_id, reviewer_id=reviewer_id, decision=decision, comment=comment,
    )
