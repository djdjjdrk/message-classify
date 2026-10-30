"""请求级依赖的统一导出。"""

from backend.app.dependencies.auth import CurrentUser, get_current_user
from backend.app.dependencies.database import DbSession
from backend.app.dependencies.permissions import AdminUser, require_admin

__all__ = [
    "DbSession",
    "CurrentUser",
    "AdminUser",
    "get_current_user",
    "require_admin",
]
