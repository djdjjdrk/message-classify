"""待审核留言和人工审核请求。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value

    @model_validator(mode="after")
    def check_rejection_reason(self):
        if self.decision == "rejected" and self.comment is None:
            raise ValueError("驳回时请填写原因")
        return self


class PendingMessageResponse(BaseModel):
    id: int
    content: str
    author_nickname: str
    created_at: datetime
    predicted_label: Literal["normal", "spam"] | None
    prediction_status: Literal["pending", "success", "no_features", "no_model", "error"]
    predicted_probability: float | None
    model_name: str | None
    prediction_explanation: list[dict[str, Any]] | None
    manual_label: Literal["normal", "spam"] | None
    effective_label: Literal["normal", "spam"] | None
    label_source: Literal["manual", "model", "unclassified"]


class ReviewResponse(BaseModel):
    message_id: int
    review_status: Literal["approved", "rejected"]


class ReviewRecordResponse(BaseModel):
    id: int
    message_id: int
    content: str
    reviewer_nickname: str | None
    reviewer_username: str | None
    review_source: Literal["manual", "automatic"]
    previous_status: Literal["pending", "approved", "rejected"]
    decision: Literal["approved", "rejected"]
    label_snapshot: Literal["normal", "spam"] | None
    model_name_snapshot: str | None
    spam_probability_snapshot: float | None
    normal_threshold_snapshot: float | None
    comment: str | None
    created_at: datetime
