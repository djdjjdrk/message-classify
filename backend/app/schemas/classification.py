"""管理员查看留言分类时使用的响应字段。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ClassificationMessageResponse(BaseModel):
    id: int
    content: str
    author_nickname: str
    created_at: datetime
    predicted_label: Literal["normal", "spam"] | None
    prediction_status: Literal["pending", "success", "no_features", "no_model", "error"]
    manual_label: Literal["normal", "spam"] | None
    effective_label: Literal["normal", "spam"] | None
    label_source: Literal["manual", "model", "unclassified"]
