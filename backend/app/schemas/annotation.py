"""人工标注的提交参数和历史记录字段。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnnotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Literal["normal", "spam"]
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if value == "":
            return None
        return value


class AnnotationSaveResponse(BaseModel):
    message_id: int
    manual_label: Literal["normal", "spam"]
    changed: bool


class AnnotationRecordResponse(BaseModel):
    id: int
    message_id: int
    annotator_id: int
    annotator_username: str
    annotator_nickname: str
    previous_label: Literal["normal", "spam"] | None
    new_label: Literal["normal", "spam"]
    reason: str | None
    created_at: datetime
