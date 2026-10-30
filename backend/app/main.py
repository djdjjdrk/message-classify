from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from backend.app.api.auth import router as auth_router
from backend.common.exceptions import (
    BusinessException,
    business_exception_handler,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.common.response import Response

app = FastAPI(
    title="校园留言分类与垃圾信息识别系统",
    version="0.1.0",
    exception_handlers={
        BusinessException: business_exception_handler,
        HTTPException: http_exception_handler,
        RequestValidationError: validation_exception_handler,
        Exception: global_exception_handler,
    },
    responses={
        code: {"model": Response, "description": description}
        for code, description in {
            401: "登录失效",
            403: "权限不足",
            404: "资源不存在",
            405: "请求方法不允许",
            422: "请求参数校验错误",
            500: "服务器内部错误",
        }.items()
    },
)

app.include_router(auth_router, prefix="/api/v1")
