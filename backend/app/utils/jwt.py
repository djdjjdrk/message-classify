from datetime import datetime, timedelta, timezone

import jwt

from backend.app.config import settings


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    """校验签名、时效及用户 ID；无效时抛出 InvalidTokenError 或 ValueError。"""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )
    subject = payload["sub"]
    if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
        raise ValueError("Invalid subject")
    user_id = int(subject)
    if not 0 < user_id <= 2**63 - 1:
        raise ValueError("Invalid user id")
    return user_id
