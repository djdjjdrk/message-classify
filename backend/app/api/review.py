from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.common.response import PageResponse, Response
from backend.app.dependencies import AdminUser, DbSession
from backend.app.schemas.review import (
    PendingMessageResponse, ReviewRecordResponse, ReviewRequest, ReviewResponse,
)
from backend.app.service.review import (
    list_pending_reviews, list_review_records, review_message as save_review,
)

router = APIRouter(prefix="/reviews", tags=["留言审核"])


@router.get("/pending", response_model=Response)
def get_pending_messages(
    user: AdminUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> Response:
    messages, total = list_pending_reviews(db, page=page, page_size=page_size)
    message_list = []
    for message in messages:
        effective_label = None
        label_source = "unclassified"
        if message.manual_label is not None:
            effective_label = message.manual_label
            label_source = "manual"
        elif message.prediction_status == "success" and message.predicted_label is not None:
            effective_label = message.predicted_label
            label_source = "model"
        message_data = PendingMessageResponse(
            id=message.id,
            content=message.content,
            author_nickname=message.author.nickname,
            created_at=message.created_at,
            predicted_label=message.predicted_label,#type: ignore
            prediction_status=message.prediction_status,#type: ignore
            predicted_probability=message.predicted_probability,
            model_name=message.model_name,
            prediction_explanation=message.prediction_explanation,
            manual_label=message.manual_label,#type: ignore
            effective_label=effective_label,#type: ignore
            label_source=label_source,
        )
        message_list.append(message_data)
    return Response.success(data=PageResponse(list=message_list, total=total))


@router.get("/history", response_model=Response)
def get_review_history(
    user: AdminUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> Response:
    records, total = list_review_records(db, page=page, page_size=page_size)
    history = []
    for record in records:
        nickname = None
        username = None
        if record.reviewer is not None:
            nickname = record.reviewer.nickname
            username = record.reviewer.username
        history.append(ReviewRecordResponse(
            id=record.id,
            message_id=record.message_id,
            content=record.message.content,
            reviewer_nickname=nickname,
            reviewer_username=username,
            review_source=record.review_source,#type: ignore
            previous_status=record.previous_status,#type: ignore
            decision=record.decision,#type: ignore
            label_snapshot=record.label_snapshot,#type: ignore
            model_name_snapshot=record.model_name_snapshot,
            spam_probability_snapshot=record.spam_probability_snapshot,
            normal_threshold_snapshot=record.normal_threshold_snapshot,
            comment=record.comment,
            created_at=record.created_at,
        ))
    return Response.success(data=PageResponse(list=history, total=total))


@router.post("/messages/{message_id}", response_model=Response)
def review_message(
    message_id: Annotated[int, Path(ge=1)],
    payload: ReviewRequest,
    user: AdminUser,
    db: DbSession,
) -> Response:
    save_review(
        db, message_id=message_id, reviewer_id=user.id,
        decision=payload.decision, comment=payload.comment,
    )
    data = ReviewResponse(message_id=message_id, review_status=payload.decision)
    if payload.decision == "approved":
        message = "留言已通过审核"
    else:
        message = "留言已驳回"
    return Response.success(message=message, data=data)
