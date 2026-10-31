"""留言发布请求、个人留言与公共列表响应。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageCreate(BaseModel):
    # 作者和审核状态由后端确定，不接受客户端指定。
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("留言内容不能为空")
        return content


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    content: str
    review_status: Literal["pending", "approved", "rejected"]
    prediction_status: Literal["pending", "success", "no_features", "no_model", "error"]
    created_at: datetime
    updated_at: datetime


class PublicMessageResponse(BaseModel):
    id: int
    content: str
    author_nickname: str
    created_at: datetime
    can_delete: bool
