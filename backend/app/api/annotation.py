from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.common.response import PageResponse, Response
from backend.app.dependencies import AdminUser, DbSession
from backend.app.schemas.annotation import (
    AnnotationRecordResponse, AnnotationRequest, AnnotationSaveResponse,
)
from backend.app.service.annotation import annotate_message, list_annotation_records

router = APIRouter(prefix="/classification", tags=["人工标注"])


@router.post("/messages/{message_id}/annotations", response_model=Response)
def create_annotation(
    message_id: Annotated[int, Path(ge=1)],
    payload: AnnotationRequest,
    user: AdminUser,
    db: DbSession,
) -> Response:
    changed = annotate_message(
        db, message_id=message_id, annotator_id=user.id,
        label=payload.label, reason=payload.reason,
    )
    data = AnnotationSaveResponse(
        message_id=message_id, manual_label=payload.label, changed=changed,
    )
    if changed:
        message = "人工标注已保存"
    else:
        message = "人工标签未变化，无需重复保存"
    return Response.success(data=data, message=message)


@router.get("/messages/{message_id}/annotations", response_model=Response)
def get_annotation_records(
    message_id: Annotated[int, Path(ge=1)],
    user: AdminUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> Response:
    records, total = list_annotation_records(
        db, message_id=message_id, page=page, page_size=page_size,
    )
    record_list = []
    for record in records:
        record_data = AnnotationRecordResponse(
            id=record.id,
            message_id=record.message_id,
            annotator_id=record.annotator_id,
            annotator_username=record.annotator.username,
            annotator_nickname=record.annotator.nickname,
            previous_label=record.previous_label,#type: ignore
            new_label=record.new_label,#type: ignore
            reason=record.reason,
            created_at=record.created_at,
        )
        record_list.append(record_data)
    return Response.success(data=PageResponse(list=record_list, total=total))
