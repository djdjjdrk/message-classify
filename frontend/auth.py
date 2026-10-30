import streamlit as st

from frontend.api_client import ApiError, login


def clear_session() -> None:
    # 退出或令牌失效时同时清理当前用户的页面状态，避免换账号后残留数据。
    for key in list(st.session_state):
        del st.session_state[key]


def render_login() -> None:
    st.title("登录")
    st.caption("校园留言分类与垃圾信息识别系统")
    if st.session_state.pop("registration_success", False):
        st.success("注册成功，请使用新账号登录")
    with st.container(width=420, border=True):
        with st.form("login", clear_on_submit=True):
            username = st.text_input("用户名", max_chars=64)
            password = st.text_input("密码", type="password", max_chars=1024)
            submitted = st.form_submit_button("登录", type="primary", width="stretch")
        if submitted:
            if not username.strip() or not password:
                st.error("请输入用户名和密码")
                return
            try:
                result = login(username.strip(), password)
            except ApiError as error:
                st.error(str(error))
                return
            clear_session()
            st.session_state.access_token = result["access_token"]
            st.rerun()
    st.caption("没有账号？点击顶部“注册”创建普通用户账号。")
