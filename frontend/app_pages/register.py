import re

import streamlit as st

from frontend.api_client import ApiError, register

st.title("注册")
st.caption("创建普通用户账号，参与校园留言。")

with st.container(width=420, border=True):
    with st.form("register", clear_on_submit=True):
        username = st.text_input(
            "用户名", max_chars=20, key="register_username",
            help="用于登录，3～20 个字符，可使用中文、字母、数字、下划线或连字符；admin 为保留用户名。",
        )
        nickname = st.text_input("昵称（选填）", max_chars=20, key="register_nickname", help="用于页面展示，最多 20 个字符；不填则使用用户名。")
        password = st.text_input("密码", type="password", max_chars=32, key="register_password", help="8～32 个字符，不能全部为空白。")
        confirm_password = st.text_input("确认密码", type="password", max_chars=32, key="register_confirm_password")
        submitted = st.form_submit_button("注册", type="primary", width="stretch")

    if submitted:
        username = username.strip()
        if not 3 <= len(username) <= 20 or not re.fullmatch(r"[\w-]+", username):
            st.error("用户名须为 3～20 个字符，仅支持中文、字母、数字、下划线或连字符")
        elif username.casefold() == "admin":
            st.error("该用户名保留给系统管理员，请使用其他用户名")
        elif len(nickname.strip()) > 20:
            st.error("昵称最多为 20 个字符")
        elif not 8 <= len(password) <= 32 or not password.strip():
            st.error("密码须为 8～32 个字符，不能全部为空白")
        elif password != confirm_password:
            st.error("两次输入的密码不一致")
        else:
            try:
                register(username, password, nickname.strip() or None)
            except ApiError as error:
                st.error(str(error))
            else:
                st.session_state.registration_success = True
                st.switch_page("app_pages/login.py")

    if st.button("返回登录", width="stretch"):
        st.switch_page("app_pages/login.py")
