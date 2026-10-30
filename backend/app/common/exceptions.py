import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from backend.app.common.response import Response

logger = logging.getLogger(__name__)


class BusinessException(Exception):
    """业务失败通过 code 区分，HTTP 状态保持 200。message 应可向用户展示。"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthenticationError(HTTPException):
    def __init__(self, message: str = "登录已失效，请重新登录"):
        super().__init__(status_code=401, detail=message, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(HTTPException):
    def __init__(self, message: str = "需要管理员权限"):
        super().__init__(status_code=403, detail=message)


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=Response.error(code=exc.code, message=exc.message).model_dump(mode="json"),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return JSONResponse(
        status_code=exc.status_code,
        content=Response.error(code=exc.status_code, message=message).model_dump(mode="json"),
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # 不回传请求正文、密码等原始输入。
    return JSONResponse(
        status_code=422,
        content=Response.error(code=422, message="请求参数校验错误").model_dump(mode="json"),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception for %s %s", request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=Response.error(code=500, message="服务器内部错误").model_dump(mode="json"),
    )
