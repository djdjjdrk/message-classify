from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from frontend import api_client

ENTRYPOINT = Path(__file__).resolve().parents[2] / "frontend" / "main.py"


@pytest.fixture
def app(client, monkeypatch):
    def transport(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, httpx.URL(url).raw_path.decode(), **kwargs)

    monkeypatch.setattr(api_client.httpx, "request", transport)
    return AppTest.from_file(str(ENTRYPOINT), default_timeout=10).run()


@pytest.mark.parametrize("username", ["student", "admin"])
def test_login_navigation_and_logout(app, username):
    assert not app.exception
    assert app.title[0].value == "登录"
    app.text_input[0].set_value(username)
    app.text_input[1].set_value("test-password-123")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert app.title[0].value == "留言管理"
    assert app.session_state["user"]["role"] == username
    if username == "admin":
        app.switch_page("app_pages/review.py").run()
        assert app.title[0].value == "标注审核"
    else:
        with pytest.raises(ValueError):
            app.switch_page("app_pages/review.py")
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert app.title[0].value == "登录"
    assert not app.session_state["access_token"]


def test_bad_password_and_expiry(app):
    app.text_input[0].set_value("student")
    app.text_input[1].set_value("wrong-password")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert app.error[0].value == "用户名或密码错误"
    app.session_state["access_token"] = "expired-token"
    app.run()
    assert not app.exception
    assert app.title[0].value == "登录"
    assert app.warning[0].value == "登录已失效，请重新登录"


def test_backend_unavailable(app, monkeypatch):
    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(api_client.httpx, "request", offline)
    app.text_input[0].set_value("student")
    app.text_input[1].set_value("test-password-123")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert "无法连接后端" in app.error[0].value


def test_registration_returns_to_login_and_new_account_can_sign_in(app):
    app.switch_page("app_pages/register.py").run()
    assert not app.exception
    assert app.title[0].value == "注册"
    app.text_input(key="register_username").set_value("campus-user")
    app.text_input(key="register_nickname").set_value("校园小王")
    app.text_input(key="register_password").set_value("my-password-123")
    app.text_input(key="register_confirm_password").set_value("my-password-123")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert app.title[0].value == "登录"
    assert app.success[0].value == "注册成功，请使用新账号登录"
    assert not app.session_state["access_token"]
    # 同步 AppTest 的显式页面目标，避免后续提交再次请求之前的注册页。
    app.switch_page("app_pages/login.py")
    app.text_input[0].set_value("campus-user")
    app.text_input[1].set_value("my-password-123")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert app.title[0].value == "留言管理"
    assert app.session_state["user"]["role"] == "student"
    assert app.session_state["user"]["nickname"] == "校园小王"
    assert app.sidebar.text[0].value == "校园小王"


def test_registration_password_confirmation_and_duplicate_error(app):
    app.switch_page("app_pages/register.py").run()
    app.text_input(key="register_username").set_value("student")
    app.text_input(key="register_password").set_value("my-password-123")
    app.text_input(key="register_confirm_password").set_value("different-password")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert app.error[0].value == "两次输入的密码不一致"
    app.text_input(key="register_username").set_value("student")
    app.text_input(key="register_password").set_value("my-password-123")
    app.text_input(key="register_confirm_password").set_value("my-password-123")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert app.error[0].value == "用户名已存在，请使用其他用户名"
    assert not app.session_state["access_token"]
    app.button[-1].click().run()
    assert not app.exception
    assert app.title[0].value == "登录"
