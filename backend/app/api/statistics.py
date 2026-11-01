from fastapi import APIRouter

from backend.app.common.response import Response
from backend.app.dependencies import AdminUser, DbSession
from backend.app.service.statistics import get_message_statistics

router = APIRouter(prefix="/statistics", tags=["留言统计"])


@router.get("", response_model=Response)
def get_statistics(user: AdminUser, db: DbSession) -> Response:
    return Response.success(data=get_message_statistics(db))
