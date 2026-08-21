"""聊天 UI 组件 — 消息渲染、头像、加载动画、流式输出、引用溯源面板。"""

from __future__ import annotations

import time
from collections.abc import Generator

import streamlit as st

from components.api_client import ChatResult, fetch_chat_response
from components.chat_state import append_message
from components.config import ASSISTANT_AVATAR, ASSISTANT_NAME

# 引用来源 → （中文名, 徽章颜色）
_SOURCE_META = {
    "graph": ("图谱事实", "#1f6feb"),
    "vector": ("背景故事", "#1a7f37"),
    "facility": ("馆务资料", "#bc4c00"),
}


def render_citations(citations: list[dict[str, str]]) -> None:
    """在回答下方渲染可展开的引用溯源面板（graph / vector / facility）。"""
    with st.expander(f"引用溯源（{len(citations)} 条）"):
        for i, cite in enumerate(citations, 1):
            source_type = cite.get("source_type", "unknown")
            label, color = _SOURCE_META.get(source_type, ("来源", "#6e7781"))
            st.markdown(
                f"**{i}.** "
                f"<span style='background:{color};color:#fff;padding:1px 8px;"
                f"border-radius:10px;font-size:12px'>{label}</span>"
                f"　`{source_type}`",
                unsafe_allow_html=True,
            )
            st.code(cite.get("content", ""))


def render_chat_history() -> None:
    """渲染历史聊天记录（使用正确的写法避免重影报错）"""
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            with st.chat_message(
                ASSISTANT_NAME,
                avatar=ASSISTANT_AVATAR
            ):
                st.empty()
                st.markdown(message["content"])
                if message.get("citations"):
                    render_citations(message["citations"])
        else:
            with st.chat_message("user"):
                st.markdown(message["content"])


def render_loading_indicator() -> None:
    """渲染打字加载动画。"""
    st.markdown(
        """
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def handle_user_message(question: str) -> None:
    """
    处理用户消息：写入历史 → 流式生成 AI 回答 → 渲染引用溯源 → 存入 session state。

    模式参考 Streamlit 官方 Chatbot Template:
    https://github.com/streamlit/chatbot-template
    """
    # 首条消息进来时清掉顶部欢迎区，避免与聊天记录重叠（坑位为空则跳过）
    placeholder = st.session_state.pop("welcome_placeholder", None)
    if placeholder is not None:
        placeholder.empty()

    append_message("user", question)

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message(
            ASSISTANT_NAME,
            avatar=ASSISTANT_AVATAR
    ):
        # 1. 独立创建一个占位符并渲染加载动画（真实等待网络返回）
        loading_placeholder = st.empty()
        with loading_placeholder:
            render_loading_indicator()

        # 2. 拉取完整回答 + 引用
        result: ChatResult = fetch_chat_response(question)

        # 3. 清空加载动画，以打字机效果流式打印回答
        loading_placeholder.empty()

        def typewriter() -> Generator[str, None, None]:
            for char in result.answer:
                yield char
                time.sleep(0.015)

        response = st.write_stream(typewriter())

        # 4. 回答下方展示引用溯源面板
        if result.citations:
            render_citations(result.citations)

    append_message("assistant", response, citations=result.citations)
