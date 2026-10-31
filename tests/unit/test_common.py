import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.common.exceptions import BusinessException
from backend.app.common.response import Response


@pytest.fixture
def error_client():
    test_app = FastAPI(exception_handlers=app.exception_handlers)

    @test_app.get("/business-error")
    def business_error():
        raise BusinessException("留言已被删除", code=400)

    @test_app.get("/http-error")
    def http_error():
        raise HTTPException(status_code=429, detail="请求过于频繁", headers={"Retry-After": "30"})

    @test_app.get("/unexpected-error")
    def unexpected_error():
        raise RuntimeError("internal-database-password-must-not-leak")

    @test_app.get("/bad-response", response_model=Response)
    def bad_response():
        return {"unexpected": "internal-data"}

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


def test_business_failure_keeps_http_200(error_client):
    response = error_client.get("/business-error")
    assert response.status_code == 200
    assert response.json() == {"code": 400, "message": "留言已被删除", "data": None}


def test_http_failure_preserves_status_and_headers(error_client):
    response = error_client.get("/http-error")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json() == {"code": 429, "message": "请求过于频繁", "data": None}


@pytest.mark.parametrize("path", ["/unexpected-error", "/bad-response"])
def test_internal_errors_are_hidden(error_client, path):
    response = error_client.get(path)
    assert response.status_code == 500
    assert response.json() == {"code": 500, "message": "服务器内部错误", "data": None}


def test_validation_does_not_echo_password(client):
    password = "secret-password-" * 100
    response = client.post("/api/v1/auth/login", json={"username": "student", "password": password})
    assert response.status_code == 422
    assert response.json() == {"code": 422, "message": "请求参数校验错误", "data": None}
    assert password not in response.text


def test_invalid_json_uses_unified_error(client):
    response = client.post("/api/v1/auth/login", content="{broken", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"code": 422, "message": "请求参数校验错误", "data": None}


@pytest.mark.parametrize("data,message", [
    ({"username": "admin", "password": "password123"}, "该用户名保留给系统管理员，请使用其他用户名"),
    ({"username": "newuser", "password": " " * 8}, "密码不能全部为空白字符"),
    ({"username": "admin", "password": " " * 8}, "该用户名保留给系统管理员，请使用其他用户名；密码不能全部为空白字符"),
])
def test_registration_validation_shows_custom_messages(client, data, message):
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert response.json() == {"code": 422, "message": message, "data": None}


def test_framework_errors_and_openapi():
    with TestClient(app) as client:
        missing = client.get("/not-found")
        assert missing.status_code == 404
        assert missing.json() == {"code": 404, "message": "Not Found", "data": None}
        method = client.get("/api/v1/auth/login")
        assert method.status_code == 405
        assert "POST" in method.headers["Allow"]
        assert method.json()["code"] == 405
        schema = client.get("/openapi.json").json()
        responses = schema["paths"]["/api/v1/auth/login"]["post"]["responses"]
        for status in ("200", "401", "422", "500"):
            assert responses[status]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Response"
