import streamlit as st

from frontend.api_client import ApiError, login
from frontend.auth import clear_session

st.title("登录")
st.caption("校园留言分类与垃圾信息识别系统")

if st.session_state.pop("registration_success", False):
    st.success("注册成功，请使用新账号登录")

with st.container(width=420, border=True):
    with st.form("login", clear_on_submit=True):
        username = st.text_input(
            "用户名", max_chars=20, key="login_username",
            help="用于登录的账号，3～20 个字符。",
        )
        password = st.text_input(
            "密码", type="password", max_chars=32, key="login_password",
            help="8～32 个字符。",
        )
        submitted = st.form_submit_button("登录", type="primary", width="stretch")

    if submitted:
        username = username.strip()
        if not username or not password:
            st.error("请输入用户名和密码")
        elif not 3 <= len(username) <= 20:
            st.error("用户名长度须为 3～20 个字符")
        elif not 8 <= len(password) <= 32:
            st.error("密码长度须为 8～32 个字符")
        else:
            try:
                result = login(username, password)
            except ApiError as error:
                st.error(str(error))
            else:
                clear_session()
                st.session_state.access_token = result["access_token"]
                st.rerun()

st.caption("没有账号？点击顶部“注册”创建普通用户账号。")
