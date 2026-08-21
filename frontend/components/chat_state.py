"""聊天状态管理 — 参考 Streamlit 官方 Chatbot Template 模式。"""

from __future__ import annotations

import streamlit as st


def init_chat_state() -> None:
    """初始化 session state，确保消息在 rerun 间持久化。"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None


def append_message(role: str, content: str, citations: list[dict[str, str]] | None = None) -> None:
    """追加一条消息到历史记录；assistant 消息可携带引用溯源。"""
    st.session_state.messages.append(
        {"role": role, "content": content, "citations": citations or []}
    )


def clear_messages() -> None:
    """清空聊天记录。"""
    st.session_state.messages = []


def set_pending_question(question: str) -> None:
    """设置待发送的推荐问题（由按钮触发）。"""
    st.session_state.pending_question = question


def consume_pending_question() -> str | None:
    """取出并清除待发送问题，返回 None 表示无待发送。"""
    question = st.session_state.pending_question
    st.session_state.pending_question = None
    return question
