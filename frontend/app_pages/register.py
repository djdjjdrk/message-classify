import re

import streamlit as st

from frontend.api_client import ApiError, register

st.title("注册")
st.caption("创建普通用户账号，参与校园留言。")

with st.container(width=420, border=True):
    with st.form("register", clear_on_submit=True):
        username = st.text_input(
            "用户名", max_chars=64,
            help="3～64 个字符，可使用中文、字母、数字、下划线或连字符；admin 为保留用户名。",
        )
        password = st.text_input("密码", type="password", max_chars=128, help="8～128 个字符，不能全部为空白。")
        confirm_password = st.text_input("确认密码", type="password", max_chars=128)
        submitted = st.form_submit_button("注册", type="primary", width="stretch")

    if submitted:
        username = username.strip()
        if not 3 <= len(username) <= 64 or not re.fullmatch(r"[\w-]+", username):
            st.error("用户名须为 3～64 个字符，仅支持中文、字母、数字、下划线或连字符")
        elif username.casefold() == "admin":
            st.error("该用户名保留给系统管理员，请使用其他用户名")
        elif not 8 <= len(password) <= 128 or not password.strip():
            st.error("密码须为 8～128 个字符，不能全部为空白")
        elif password != confirm_password:
            st.error("两次输入的密码不一致")
        else:
            try:
                register(username, password)
            except ApiError as error:
                st.error(str(error))
            else:
                st.session_state.registration_success = True
                st.switch_page("app_pages/login.py")

    if st.button("返回登录", width="stretch"):
        st.switch_page("app_pages/login.py")
