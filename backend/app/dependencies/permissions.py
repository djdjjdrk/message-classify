from typing import Annotated

from fastapi import Depends

from backend.app.dependencies.auth import CurrentUser
from backend.app.models import User
from backend.common.exceptions import PermissionDeniedError


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise PermissionDeniedError()
    return user


AdminUser = Annotated[User, Depends(require_admin)]
