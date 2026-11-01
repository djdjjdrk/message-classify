"""管理员查看留言分类时使用的响应字段。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ClassificationMessageResponse(BaseModel):
    id: int
    content: str
    author_nickname: str
    created_at: datetime
    predicted_label: Literal["normal", "spam"] | None
    prediction_status: Literal["pending", "success", "no_features", "no_model", "error"]
    review_status: Literal["pending", "approved", "rejected"]
    predicted_probability: float | None
    model_name: str | None
    # 兼容历史 JSON；新预测写入 word/count/contribution/direction，不解释旧 weight 为贡献。
    prediction_explanation: list[dict[str, Any]] | None
    manual_label: Literal["normal", "spam"] | None
    effective_label: Literal["normal", "spam"] | None
    label_source: Literal["manual", "model", "unclassified"]
