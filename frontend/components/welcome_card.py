"""AI 欢迎卡片组件。"""

import streamlit as st

from components.config import ASSISTANT_NAME


def render_welcome_card() -> None:
    """在无聊天记录时展示欢迎卡片。"""
    st.markdown(
        f"""
        <div class="welcome-card">
            <div class="welcome-badge">✦ AI 智能导览</div>
            <h2>你好，欢迎来到{ASSISTANT_NAME}</h2>
            <p>
                我是广东省博物馆 AI 助手，基于大语言模型、Agent 智能体、
                知识图谱与 RAG 检索增强技术，为你解答文物历史、
                参观路线与岭南文化相关问题。
                \n点击下方推荐问题，或直接输入你的疑问吧~
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
