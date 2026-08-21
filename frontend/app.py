"""
粤博智游 — 广东省博物馆 AI 助手

架构参考 Streamlit 官方 Chatbot Template:
https://github.com/streamlit/chatbot-template
"""

import streamlit as st

from components.chat_state import consume_pending_question, init_chat_state
from components.chat_ui import handle_user_message, render_chat_history
from components.sidebar import render_sidebar
from components.styles import inject_museum_theme
from components.suggested_questions import render_suggested_questions
from components.welcome_card import render_welcome_card

# =====================
# 页面配置
# =====================

st.set_page_config(
    page_title="粤博智游",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_museum_theme()
init_chat_state()

# =====================
# 侧边栏
# =====================

render_sidebar()

# =====================
# 主页面头部
# =====================

st.markdown('<p class="museum-header">🏛 广东省博物馆 AI 助手</p>', unsafe_allow_html=True)
st.markdown('<p class="museum-subtitle">探索岭南文化 · 发现历史文物</p>', unsafe_allow_html=True)

# =====================
# AI 智能问答
# =====================

# 1. 建立一个永久的顶部坑位
welcome_placeholder = st.empty()

# 2. 将欢迎组件全部放进这个坑位里
if not st.session_state.messages:
    with welcome_placeholder.container():
        render_welcome_card()
        render_suggested_questions()

# 3. 把坑位存进 session_state，供 handle_user_message 首条消息时清空
st.session_state["welcome_placeholder"] = welcome_placeholder

render_chat_history()

# 处理推荐问题按钮触发的 pending question
pending = consume_pending_question()
if pending:
    handle_user_message(pending)

# 聊天输入框
question = st.chat_input("请输入你想了解的问题，例如：端砚是什么年代的？")

if question:
    handle_user_message(question)
