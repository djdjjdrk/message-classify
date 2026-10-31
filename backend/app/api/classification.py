from typing import Annotated, Literal

from fastapi import APIRouter, Query

from backend.app.common.response import PageResponse, Response
from backend.app.dependencies import AdminUser, DbSession
from backend.app.schemas.classification import ClassificationMessageResponse
from backend.app.service.classification import list_classification_messages

router = APIRouter(prefix="/classification", tags=["分类管理"])


@router.get("/messages", response_model=Response)
def get_classification_messages(
    user: AdminUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    category: Annotated[Literal["all", "unclassified", "normal", "spam"], Query()] = "all",
) -> Response:
    messages, total = list_classification_messages(
        db, page=page, page_size=page_size, category=category,
    )
    message_list = []
    for message in messages:
        effective_label = None
        label_source = "unclassified"
        if message.manual_label is not None:
            effective_label = message.manual_label
            label_source = "manual"
        elif message.prediction_status == "success":
            if message.predicted_label is not None:
                effective_label = message.predicted_label
                label_source = "model"

        message_data = ClassificationMessageResponse(
            id=message.id,
            content=message.content,
            author_nickname=message.author.nickname,
            created_at=message.created_at,
            predicted_label=message.predicted_label,#type: ignore
            prediction_status=message.prediction_status,#type: ignore
            manual_label=message.manual_label,#type: ignore
            effective_label=effective_label,#type: ignore
            label_source=label_source,
        )
        message_list.append(message_data)

    page_data = PageResponse(list=message_list, total=total)
    return Response.success(data=page_data)
