import streamlit as st

def clear_session() -> None:
    # 退出或令牌失效时同时清理当前用户的页面状态，避免换账号后残留数据。
    for key in list(st.session_state):
        del st.session_state[key]
