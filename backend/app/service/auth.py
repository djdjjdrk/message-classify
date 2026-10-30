from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import User
from backend.app.utils.password import hash_password, verify_password
from backend.app.common.exceptions import BusinessException

# 未知用户名也执行一次哈希校验，避免直接跳过耗时操作。
_dummy_hash = hash_password("dummy-password-for-timing-only")


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    valid = verify_password(password, user.password_hash if user else _dummy_hash)
    return user if user is not None and valid else None


def register_user(db: Session, username: str, password: str, nickname: str | None = None) -> User:
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise BusinessException("用户名已存在，请使用其他用户名", code=409)

    user = User(
        username=username, nickname=nickname or username,
        password_hash=hash_password(password), role="student",
    )
    try:
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        # 唯一约束兜住并发注册；其他完整性错误仍交给全局异常处理器。
        if db.scalar(select(User.id).where(User.username == username)) is not None:
            raise BusinessException("用户名已存在，请使用其他用户名", code=409) from None
        raise
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(user)
    return user
