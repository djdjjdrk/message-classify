from typing import Annotated

from fastapi import Depends, HTTPException

from backend.app.dependencies.auth import CurrentUser
from backend.app.models import User


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
