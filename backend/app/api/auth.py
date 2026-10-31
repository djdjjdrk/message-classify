from fastapi import APIRouter, HTTPException

from backend.app.config import settings
from backend.app.dependencies import CurrentUser, DbSession
from backend.app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from backend.app.service.auth import authenticate_user, register_user
from backend.app.utils.jwt import create_access_token
from backend.app.common.response import Response

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=Response)
def register(data: RegisterRequest, db: DbSession) -> Response:
    user = register_user(db, data.username, data.password, data.nickname)
    return Response.success(message="注册成功，请登录", data=UserResponse.model_validate(user))


@router.post("/login", response_model=Response)
def login(data: LoginRequest, db: DbSession) -> Response:
    user = authenticate_user(db, data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=401, detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = LoginResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user=UserResponse.model_validate(user),
    )
    return Response.success(message="登录成功", data=result)


@router.get("/me", response_model=Response)
def me(user: CurrentUser) -> Response:
    return Response.success(data=UserResponse.model_validate(user))
