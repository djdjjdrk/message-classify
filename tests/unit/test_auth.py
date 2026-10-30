from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.app.utils.jwt import create_access_token
from backend.app.utils.password import verify_password
from backend.app.config import settings
from backend.app.models import User


def test_password_hash(password_hash):
    assert password_hash.startswith("$argon2id$")
    assert verify_password("test-password-123", password_hash)
    assert not verify_password("wrong", password_hash)
    assert not verify_password("anything", "invalid-hash")


def test_login_and_me(client):
    response = client.post("/api/v1/auth/login", json={"username": " student ", "password": "test-password-123"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"code", "message", "data"}
    assert body["code"] == 200
    assert body["message"] == "登录成功"
    data = body["data"]
    assert data["expires_in"] == 7200
    assert data["token_type"] == "bearer"
    assert {k: data["user"][k] for k in ("id", "username", "nickname", "role")} == {
        "id": 1, "username": "student", "nickname": "学生", "role": "student",
    }
    assert data["user"]["created_at"]
    assert data["user"]["updated_at"]
    claims = jwt.decode(data["access_token"], settings.JWT_SECRET_KEY, algorithms=["HS256"])
    assert claims["sub"] == "1"
    assert claims["exp"] - claims["iat"] == 7200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.json() == {"code": 200, "message": "请求成功", "data": data["user"]}
    assert "password_hash" not in str(data)


@pytest.mark.parametrize("username,password", [("student", "wrong-password"), ("unknown", "test-password-123")])
def test_bad_credentials_share_error(client, username, password):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"code": 401, "message": "用户名或密码错误", "data": None}


@pytest.mark.parametrize("data", [
    {}, {"username": " ", "password": "password123"}, {"username": "ab", "password": "password123"},
    {"username": "a" * 21, "password": "password123"},
    {"username": "student", "password": "p" * 7}, {"username": "student", "password": "p" * 33},
])
def test_login_validation(client, data):
    assert client.post("/api/v1/auth/login", json=data).status_code == 422


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer bad-token"])
def test_missing_or_invalid_token(client, header):
    headers = {"Authorization": header} if header else {}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", ["expired", "wrong-key", "missing-exp", "bad-sub", "huge-sub", "nonexistent"])
def test_reject_invalid_claims(client, kind):
    now = datetime.now(timezone.utc)
    claims = {"sub": "1", "iat": now, "exp": now + timedelta(hours=1)}
    key = settings.JWT_SECRET_KEY
    if kind == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif kind == "wrong-key":
        key = "different-test-key-at-least-32-characters"
    elif kind == "missing-exp":
        del claims["exp"]
    elif kind == "bad-sub":
        claims["sub"] = "not-an-id"
    elif kind == "huge-sub":
        claims["sub"] = str(2**64)
    else:
        claims["sub"] = "999"
    token = jwt.encode(claims, key, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_permission_uses_database_role(client, db):
    token = create_access_token(1)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/admin-only", headers=headers).status_code == 403
    user = db.get(User, 1)
    user.role = "admin"
    db.commit()
    assert client.get("/admin-only", headers=headers).status_code == 200
    user.role = "student"
    db.commit()
    assert client.get("/admin-only", headers=headers).status_code == 403
    assert client.get("/admin-only", headers={"Authorization": f"Bearer {create_access_token(2)}"}).status_code == 200


def test_forged_role_is_ignored(client):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + timedelta(hours=1), "role": "admin"},
        settings.JWT_SECRET_KEY, algorithm="HS256",
    )
    assert client.get("/admin-only", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_deleted_user_cannot_use_token(client, db):
    token = create_access_token(1)
    db.delete(db.get(User, 1))
    db.commit()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
