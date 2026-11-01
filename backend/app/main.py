from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from backend.app.api.annotation import router as annotation_router
from backend.app.api.auth import router as auth_router
from backend.app.api.classification import router as classification_router
from backend.app.api.messages import router as messages_router
from backend.app.api.review import router as review_router
from backend.app.api.statistics import router as statistics_router
from backend.app.common.exceptions import (
    BusinessException,
    business_exception_handler,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.app.common.response import Response

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
        401: {"model": Response, "description": "登录失效"},
        403: {"model": Response, "description": "权限不足"},
        404: {"model": Response, "description": "资源不存在"},
        405: {"model": Response, "description": "请求方法不允许"},
        422: {"model": Response, "description": "请求参数校验错误"},
        500: {"model": Response, "description": "服务器内部错误"},
    },
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(classification_router, prefix="/api/v1")
app.include_router(annotation_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
app.include_router(statistics_router, prefix="/api/v1")
