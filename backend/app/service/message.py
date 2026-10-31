from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.app.common.exceptions import BusinessException
from backend.app.database import utc_now
from backend.app.models import Message, User


def create_message(db: Session, *, author_id: int, content: str) -> Message:
    message = Message(author_id=author_id, content=content)
    db.add(message)
    try:
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
