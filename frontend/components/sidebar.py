"""侧边栏组件。"""

import streamlit as st

from components.chat_state import clear_messages


def render_sidebar() -> None:
    """渲染侧边栏（仅 AI 智能问答）。"""
    with st.sidebar:
        st.title("🏛 粤博智游")

        st.markdown(
            """
            **💬 AI 智能问答**

            基于大语言模型、Agent 智能体、
            知识图谱与 RAG 检索增强的
            广东省博物馆智能助手。
            """
        )

        st.divider()

        if st.button("🗑 清空对话", use_container_width=True):
            clear_messages()
            st.rerun()

        st.caption("👨‍💻by谢恩泽 吴弘翔 王智勇 雷仕鹏 陈宣乐")
