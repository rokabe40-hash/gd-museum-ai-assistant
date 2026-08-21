"""推荐问题按钮组件。"""

import streamlit as st

from components.chat_state import set_pending_question
from components.config import SUGGESTED_QUESTIONS


def render_suggested_questions() -> None:
    """渲染推荐问题按钮组。"""
    st.markdown('<p class="suggest-label">💡 推荐问题</p>', unsafe_allow_html=True)

    cols = st.columns(2)
    for i, question in enumerate(SUGGESTED_QUESTIONS):
        with cols[i % 2]:
            if st.button(question, key=f"suggest_{i}", use_container_width=True):
                set_pending_question(question)
                st.rerun()
