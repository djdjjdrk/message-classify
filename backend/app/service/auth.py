from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import User
from backend.app.utils.password import hash_password, verify_password
from backend.app.common.exceptions import BusinessException

# 未知用户名也执行一次哈希校验，避免直接跳过耗时操作。
_dummy_hash = hash_password("dummy-password-for-timing-only")


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    query = select(User)
    query = query.where(User.username == username)
    user = db.scalar(query)

    if user is None:
        verify_password(password, _dummy_hash)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def register_user(db: Session, username: str, password: str, nickname: str | None = None) -> User:
    query = select(User.id)
    query = query.where(User.username == username)
    existing_user_id = db.scalar(query)
    if existing_user_id is not None:
        raise BusinessException("用户名已存在，请使用其他用户名", code=409)

    if not nickname:
        nickname = username
    password_hash = hash_password(password)
    user = User(
        username=username, nickname=nickname,
        password_hash=password_hash, role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
