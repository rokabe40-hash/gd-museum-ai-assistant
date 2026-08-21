"""聊天 UI 组件 — 消息渲染、头像、加载动画、流式输出。"""

from __future__ import annotations

import streamlit as st

from components.api_client import stream_chat_response
from components.chat_state import append_message
from components.config import ASSISTANT_AVATAR, ASSISTANT_NAME


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
    处理用户消息：写入历史 → 流式生成 AI 回答 → 存入 session state。

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
        # 1. 独立创建一个占位符并渲染加载动画
        loading_placeholder = st.empty()
        with loading_placeholder:
            render_loading_indicator()

        # 2. 获取原始的流式生成器
        stream_gen = stream_chat_response(question)

        # 3. 阻塞获取第一个 token（此时加载动画正在持续显示）
        try:
            first_chunk = next(stream_gen)
        except StopIteration:
            first_chunk = ""

        # 4. 第一个 token 到达后，在 st.write_stream 启动前，先清空加载动画！
        # 这样就不会在流式输出中途打乱 Streamlit 的元素索引
        loading_placeholder.empty()

        # 5. 重新拼合生成器，将其变成一个纯文本流，交给 st.write_stream 渲染
        def pure_text_gen():
            if first_chunk:
                yield first_chunk
            yield from stream_gen

        response = st.write_stream(pure_text_gen())

    append_message("assistant", response)
