from typing import Any, List, Self

from pydantic import BaseModel, Field


class Response(BaseModel):
    """统一封装的返回格式"""

    code: int
    message: str
    data: Any = None

    @classmethod
    def success(cls, message: str = "请求成功", data: Any = None) -> Self:
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int = 500, message: str = "请求失败") -> Self:
        return cls(code=code, message=message)


class PageResponse(BaseModel):
    """分页结果放入 Response.data，列表字段统一为 list。"""

    list: List[Any] = Field(default_factory=list)
    total: int = 0
