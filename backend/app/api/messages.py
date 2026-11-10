from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.common.response import PageResponse, Response
from backend.app.dependencies import CurrentUser, DbSession
from backend.app.schemas.message import MessageCreate, MessageResponse, PublicMessageResponse
from backend.app.service.message import create_message, delete_message, list_my_messages, list_public_messages

router = APIRouter(prefix="/messages", tags=["留言"])


@router.post("", response_model=Response)
def publish_message(data: MessageCreate, user: CurrentUser, db: DbSession) -> Response:
    message = create_message(db, author_id=user.id, content=data.content)
    return Response.success(
        message="留言发布成功，已自动通过审核" if message.review_status == "approved" else "留言发布成功，等待审核",
        data=MessageResponse.model_validate(message),
    )


@router.get("/mine", response_model=Response)
def get_my_messages(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keyword: Annotated[str, Query(max_length=200, description="按正文包含关键词检索，空白表示不筛选")] = "",
) -> Response:
    # 不接收客户端指定的作者；管理员的“我的留言”也只返回本人数据。
    messages, total = list_my_messages(
        db, author_id=user.id, page=page, page_size=page_size, keyword=keyword,
    )
    message_list = []
    for message in messages:
        message_data = MessageResponse.model_validate(message)
        message_list.append(message_data)

    page_data = PageResponse(list=message_list, total=total)
    return Response.success(data=page_data)


@router.get("/public", response_model=Response)
def get_public_messages(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keyword: Annotated[str, Query(max_length=200, description="按正文包含关键词检索，空白表示不筛选")] = "",
) -> Response:
    messages, total = list_public_messages(db, page=page, page_size=page_size, keyword=keyword)
    message_list = []
    for message in messages:
        can_delete = user.role == "admin" or message.author_id == user.id
        message_data = PublicMessageResponse(
            id=message.id,
            content=message.content,
            author_nickname=message.author.nickname,
            created_at=message.created_at,
            can_delete=can_delete,
        )
        message_list.append(message_data)

    page_data = PageResponse(list=message_list, total=total)
    return Response.success(data=page_data)


@router.delete("/{message_id}", response_model=Response)
def remove_message(
    message_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    user: CurrentUser,
    db: DbSession,
) -> Response:
    delete_message(db, message_id=message_id, user=user)
    return Response.success(message="留言已删除")
