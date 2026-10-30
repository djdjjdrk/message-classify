import sys
from pathlib import Path

import streamlit as st

# Streamlit CLI 只把入口文件所在的 frontend 目录加入搜索路径。
# 显式加入项目根目录，使 frontend.* 导入不依赖启动终端的工作目录。
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from frontend.api_client import ApiError, get_current_user
from frontend.auth import clear_session

st.set_page_config(
    page_title="校园留言分类与垃圾信息识别系统",
    page_icon=":material/forum:",
    layout="wide",
)

st.session_state.setdefault("access_token", None)
st.session_state.setdefault("user", None)

if st.session_state.access_token:
    try:
        st.session_state.user = get_current_user(st.session_state.access_token)
    except ApiError as error:
        if error.status_code == 401:
            clear_session()
            st.warning(str(error))
        else:
            st.error(str(error))
            if st.button("重试"):
                st.rerun()
            if st.button("退出登录"):
                clear_session()
                st.rerun()
            st.stop()

if not st.session_state.get("access_token"):
    st.navigation(
        [
            st.Page("app_pages/login.py", title="登录", icon=":material/login:", default=True),
            st.Page("app_pages/register.py", title="注册", icon=":material/person_add:"),
        ],
        position="top",
    ).run()
    st.stop()

user = st.session_state.user
with st.sidebar:
    st.text(user["username"])
    st.caption("管理员" if user["role"] == "admin" else "普通用户")
    if st.button("退出登录", icon=":material/logout:"):
        clear_session()
        st.rerun()

pages = [
    st.Page(
        "app_pages/messages.py",
        title="留言管理",
        icon=":material/forum:",
        default=True,
    )
]
if user["role"] == "admin":
    pages.extend(
        [
            st.Page(
                "app_pages/review.py",
                title="标注审核",
                icon=":material/fact_check:",
            ),
            st.Page(
                "app_pages/statistics.py",
                title="统计看板",
                icon=":material/bar_chart:",
            ),
            st.Page(
                "app_pages/model.py",
                title="模型结果",
                icon=":material/psychology:",
            ),
        ]
    )

page = st.navigation(pages, position="top")

st.caption("校园留言分类与垃圾信息识别系统")
st.title(page.title)
page.run()
