from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from backend.app.dependencies.database import DbSession
from backend.app.models import User
from backend.app.utils.jwt import decode_access_token
from backend.app.common.exceptions import AuthenticationError

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise AuthenticationError()
    try:
        user_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, ValueError):
        raise AuthenticationError() from None

    # 身份和角色始终读取数据库，不信任前端或令牌里附带的 role。
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
