from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    API_BASE_URL: str = "http://127.0.0.1:8000/api/v1"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = FrontendSettings()


class ApiError(Exception):
    def __init__(
        self, message: str, status_code: int | None = None,
        *, code: int | None = None, data: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.data = data


def request(method: str, path: str, *, token: str | None = None, **kwargs: Any) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.request(
            method,
            f"{settings.API_BASE_URL.rstrip('/')}/{path.lstrip('/')}",
            headers=headers,
            timeout=10.0,
            **kwargs,
        )
    except httpx.RequestError:
        raise ApiError("无法连接后端服务，请确认后端已启动后重试。") from None

    try:
        payload = response.json()
    except ValueError:
        payload = None

    valid = (
        isinstance(payload, dict)
        and type(payload.get("code")) is int
        and isinstance(payload.get("message"), str)
        and "data" in payload
    )
    if response.is_error or (valid and payload["code"] != 200):
        fallback = {
            401: "用户名或密码错误" if path == "/auth/login" else "登录已失效，请重新登录",
            403: "没有执行此操作的权限",
            422: "输入格式不正确，请检查后重试",
        }.get(response.status_code, "服务暂时不可用，请稍后重试")
        raise ApiError(
            payload["message"] if valid and payload["code"] != 200 else fallback,
            response.status_code,
            code=payload["code"] if valid else None,
            data=payload["data"] if valid else None,
        )
    if not valid:
        raise ApiError("后端返回格式异常，请稍后重试", response.status_code)
    return payload["data"]


def login(username: str, password: str) -> dict[str, Any]:
    return request("POST", "/auth/login", json={"username": username, "password": password})


def register(username: str, password: str, nickname: str | None = None) -> dict[str, Any]:
    return request("POST", "/auth/register", json={"username": username, "password": password, "nickname": nickname})


def get_current_user(token: str) -> dict[str, Any]:
    return request("GET", "/auth/me", token=token)
