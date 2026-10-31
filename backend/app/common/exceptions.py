from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from backend.app.common.response import Response

class BusinessException(Exception):
    """自定义的业务异常。"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    """自定义业务异常处理器。"""
    return JSONResponse(
        status_code=200,
        content=Response.error(code=exc.code, message=exc.message).model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP 异常处理器。"""
    return JSONResponse(
        status_code=exc.status_code,
        content=Response.error(code=exc.status_code, message=exc.detail).model_dump(),
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数异常处理器。"""
    message = "请求参数校验错误"
    if request.url.path == "/api/v1/auth/register":
        messages = []
        for error in exc.errors():
            context = error.get("ctx", {})
            if error.get("type") == "value_error" and "error" in context:
                error_message = str(context["error"])
                messages.append(error_message)
        if messages:
            message = "；".join(messages)
    return JSONResponse(
        status_code=422,
        content=Response.error(code=422, message=message).model_dump(),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器。"""
    return JSONResponse(
        status_code=500,
        content=Response.error(code=500, message="服务器内部错误").model_dump(),
    )
