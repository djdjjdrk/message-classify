import pytest
from datetime import datetime
from sqlalchemy import func, select

from backend.app.models import User
from backend.app.utils.password import verify_password


def test_register_then_login(client, db):
    response = client.post("/api/v1/auth/register", json={"username": " 校园用户 ", "password": "my-password-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "注册成功，请登录"
    assert body["data"]["username"] == "校园用户"
    assert body["data"]["role"] == "student"
    assert set(body["data"]) == {"id", "username", "nickname", "role", "created_at", "updated_at"}
    assert body["data"]["nickname"] == "校园用户"
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
    {"username": "a" * 21, "password": "password123"},
    {"username": "   ", "password": "password123"},
    {"username": "bad name", "password": "password123"},
    {"username": "bad\nname", "password": "password123"},
    {"username": "admin", "password": "password123"},
    {"username": "AdMiN", "password": "password123"},
    {"username": "newuser", "password": "short"},
    {"username": "newuser", "password": "x" * 33},
    {"username": "newuser", "password": "x" * 7},
    {"username": "newuser", "password": "password123", "nickname": "昵" * 21},
    {"username": "newuser", "password": " " * 8},
    {"username": "newuser", "password": "password123", "role": "admin"},
])
def test_registration_validation_cannot_write_users(client, db, data):
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["data"] is None
    assert db.scalar(select(func.count()).select_from(User)) == 2


@pytest.mark.parametrize("username_length,password_length", [(3, 8), (20, 32)])
def test_register_accepts_length_boundaries(client, username_length, password_length):
    response = client.post("/api/v1/auth/register", json={
        "username": "u" * username_length, "password": "p" * password_length, "nickname": "昵" * 20,
    })
    assert response.json()["code"] == 200
    login = client.post("/api/v1/auth/login", json={
        "username": "u" * username_length, "password": "p" * password_length,
    })
    assert login.json()["code"] == 200


def test_nickname_is_display_name_and_username_is_login_name(client, db):
    response = client.post("/api/v1/auth/register", json={
        "username": "campus-user", "password": "password123", "nickname": "  校园小王  ",
    })
    data = response.json()["data"]
    assert data["username"] == "campus-user"
    assert data["nickname"] == "校园小王"
    assert client.post("/api/v1/auth/login", json={"username": "校园小王", "password": "password123"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "campus-user", "password": "password123"}).json()["code"] == 200

    user = db.get(User, data["id"])
    created_at = user.created_at
    user.updated_at = datetime(2000, 1, 1)
    db.commit()
    user.nickname = "新昵称"
    db.commit()
    db.refresh(user)
    assert user.updated_at > datetime(2000, 1, 1)
    assert user.created_at == created_at


@pytest.mark.parametrize("nickname", [None, "", "   "])
def test_blank_nickname_defaults_to_username(client, nickname):
    response = client.post("/api/v1/auth/register", json={
        "username": "new-user", "password": "password123", "nickname": nickname,
    })
    assert response.json()["data"]["nickname"] == "new-user"
