import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.common.exceptions import BusinessException
from backend.app.config import BASE_DIR, settings
from backend.app.database import utc_now
from backend.app.ml.predict import predict_text
from backend.app.models import Message, User
from backend.app.service.review import auto_approve_message

logger = logging.getLogger(__name__)


def create_message(db: Session, *, author_id: int, content: str) -> Message:
    if not isinstance(content, str) or not content.strip():
        raise BusinessException("留言内容不能为空", code=422)
    message = Message(author_id=author_id, content=content, review_status="pending")
    model_path = Path(settings.MODEL_PATH)
    if not model_path.is_absolute():
        model_path = BASE_DIR / model_path
    try:
        prediction = predict_text(content, model_path=model_path)
        message.prediction_status = prediction.status
        message.predicted_label = {0: "normal", 1: "spam"}.get(prediction.label)
        message.predicted_probability = prediction.spam_probability
        message.model_name = prediction.model_name
        message.prediction_explanation = prediction.explanation
    except FileNotFoundError:
        message.prediction_status = "no_model"
        logger.warning("预测模型不存在：%s", model_path)
    except Exception:
        # 模型加载、转换或计算失败都不阻止发布；仍交给人工审核。
        message.prediction_status = "error"
        logger.exception("留言预测失败")
    db.add(message)
    try:
        auto_approve_message(db, message=message, spam_threshold=settings.AUTO_APPROVE_SPAM_THRESHOLD)
        # 留言、自动审核状态与审核历史一起提交，失败时一起回滚。
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(message)
    return message


def delete_message(db: Session, *, message_id: int, user: User) -> None:
    message = db.get(Message, message_id)
    if message is None:
        raise BusinessException("留言不存在或已删除", code=404)

    # 身份来自后端登录校验，不接收客户端指定的作者或角色。
    if user.role != "admin":
        if message.author_id != user.id:
            raise BusinessException("只能删除自己发布的留言", code=403)

    if message.deleted_at is not None:
        raise BusinessException("留言不存在或已删除", code=404)

    # 只记录删除时间，保留原文和关联的标注、审核记录。
    message.deleted_at = utc_now()
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def list_my_messages(
    db: Session, *, author_id: int, page: int, page_size: int, keyword: str = "",
) -> tuple[list[Message], int]:
    # 查询本人未删除的留言。
    query = select(Message)
    query = query.where(Message.author_id == author_id)
    query = query.where(Message.deleted_at.is_(None))

    # 统计总数，条件与留言查询保持一致。
    count_query = select(func.count()).select_from(Message)
    count_query = count_query.where(Message.author_id == author_id)
    count_query = count_query.where(Message.deleted_at.is_(None))

    keyword = keyword.strip()
    if keyword != "":
        # 填了关键词才增加正文匹配；特殊符号按普通字符搜索。
        query = query.where(Message.content.contains(keyword, autoescape=True))
        count_query = count_query.where(Message.content.contains(keyword, autoescape=True))

    total = db.scalar(count_query)
    if total is None:
        total = 0

    # 最新的排在前面，再取当前页的数据。
    query = query.order_by(Message.created_at.desc(), Message.id.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset)
    query = query.limit(page_size)
    messages = db.scalars(query).all()
    return list(messages), total


def list_public_messages(
    db: Session, *, page: int, page_size: int, keyword: str = "",
) -> tuple[list[Message], int]:
    # 查询审核通过且未删除的留言，同时查询作者以显示昵称。
    query = select(Message)
    query = query.options(joinedload(Message.author))
    query = query.where(Message.review_status == "approved")
    query = query.where(Message.deleted_at.is_(None))

    count_query = select(func.count()).select_from(Message)
    count_query = count_query.where(Message.review_status == "approved")
    count_query = count_query.where(Message.deleted_at.is_(None))

    keyword = keyword.strip()
    if keyword != "":
        query = query.where(Message.content.contains(keyword, autoescape=True))
        count_query = count_query.where(Message.content.contains(keyword, autoescape=True))

    total = db.scalar(count_query)
    if total is None:
        total = 0

    query = query.order_by(Message.created_at.desc(), Message.id.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset)
    query = query.limit(page_size)
    messages = db.scalars(query).all()
    return list(messages), total
