import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.app.models import User
from backend.app.service.auth import register_user
from backend.app.utils.password import verify_password


def test_register_then_login(client, db):
    response = client.post("/api/v1/auth/register", json={"username": " 校园用户 ", "password": "my-password-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "注册成功，请登录"
    assert body["data"]["username"] == "校园用户"
    assert body["data"]["role"] == "student"
    assert set(body["data"]) == {"id", "username", "role"}
    user = db.scalar(select(User).where(User.username == "校园用户"))
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("my-password-123", user.password_hash)
    login = client.post("/api/v1/auth/login", json={"username": "校园用户", "password": "my-password-123"})
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["data"] == body["data"]
    assert client.get("/admin-only", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_duplicate_username_does_not_change_existing_user(client, db):
    original_hash = db.get(User, 1).password_hash
    response = client.post("/api/v1/auth/register", json={"username": " student ", "password": "different-password"})
    assert response.status_code == 200
    assert response.json() == {"code": 409, "message": "用户名已存在，请使用其他用户名", "data": None}
    assert db.scalar(select(func.count()).select_from(User)) == 2
    assert db.get(User, 1).password_hash == original_hash


@pytest.mark.parametrize("data", [
    {},
    {"username": "ab", "password": "password123"},
    {"username": "a" * 65, "password": "password123"},
    {"username": "   ", "password": "password123"},
    {"username": "bad name", "password": "password123"},
    {"username": "bad\nname", "password": "password123"},
    {"username": "admin", "password": "password123"},
    {"username": "AdMiN", "password": "password123"},
    {"username": "newuser", "password": "short"},
    {"username": "newuser", "password": "x" * 129},
    {"username": "newuser", "password": " " * 8},
    {"username": "newuser", "password": "password123", "role": "admin"},
])
def test_registration_validation_cannot_write_users(client, db, data):
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert response.json() == {"code": 422, "message": "请求参数校验错误", "data": None}
    assert db.scalar(select(func.count()).select_from(User)) == 2


def test_duplicate_race_rolls_back_and_returns_business_error(client, db, monkeypatch):
    original_scalar = db.scalar
    calls = 0

    def skip_initial_check(*args, **kwargs):
        nonlocal calls
        calls += 1
        return None if calls == 1 else original_scalar(*args, **kwargs)

    # 模拟预检查通过后，另一个请求已经插入同名账号。
    monkeypatch.setattr(db, "scalar", skip_initial_check)
    response = client.post("/api/v1/auth/register", json={"username": "student", "password": "different-password"})
    assert response.json()["code"] == 409
    assert db.is_active
    assert db.scalar(select(func.count()).select_from(User)) == 2
    assert verify_password("test-password-123", db.get(User, 1).password_hash)


def test_failed_commit_leaves_no_partial_account(db, monkeypatch):
    def unavailable():
        raise OperationalError("INSERT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "commit", unavailable)
    with pytest.raises(OperationalError):
        register_user(db, "newuser", "my-password-123")
    assert db.is_active
    assert db.scalar(select(User).where(User.username == "newuser")) is None
