"""注册、登录请求和认证响应。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=32)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class RegisterRequest(LoginRequest):
    # 注册请求不接收 role，防止通过额外字段创建管理员。
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=20, pattern=r"^[\w-]+$")
    nickname: str | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize_nickname(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None
        return value

    @field_validator("username")
    @classmethod
    def reject_reserved_username(cls, value: str) -> str:
        if value.casefold() == "admin":
            raise ValueError("该用户名保留给系统管理员，请使用其他用户名")
        return value

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("密码不能全部为空白字符")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    role: Literal["student", "admin"]
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
