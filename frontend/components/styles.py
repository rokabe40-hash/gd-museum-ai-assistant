"""博物馆科技风 UI 样式。"""

import streamlit as st
import base64
from pathlib import Path


def inject_museum_theme() -> None:
    """注入博物馆科技风全局 CSS。"""

    # ---- 读取本地图片，转为 Base64 嵌入 CSS（自动适配路径） ----
    # 当前文件在 frontend/components/styles.py，向上两级到 frontend/
    img_path = Path(__file__).parent.parent / "static" / "bg.jpg"

    if img_path.exists():
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        # 如果图片是 PNG 格式，请将 image/jpeg 改为 image/png
        bg_style = f"background-image: url('data:image/jpeg;base64,{img_data}');"
    else:
        # 图片丢失时降级为渐变背景
        bg_style = "background: linear-gradient(135deg, #0a0e17 0%, #12182a 50%, #0d1520 100%);"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

        :root {{
            --museum-gold: #c9a227;
            --museum-gold-light: #e8c547;
            --museum-teal: #00d4aa;
            --museum-dark: #0a0e17;
            --museum-card: rgba(26, 31, 46, 0.85);
            --museum-border: rgba(201, 162, 39, 0.25);
        }}

        /* 清空最外层背景，让子容器显示图片 */
        .stApp {{
            background: transparent !important;
        }}

        /* 主内容区域（聊天区）使用嵌入的图片 */
        [data-testid="stAppViewContainer"] {{
            {bg_style}
            background-size: cover !important;
            background-position: center center !important;
            background-repeat: no-repeat !important;
            background-attachment: fixed !important;
        }}

        /* 侧边栏 — 深色底 + 白色文字 */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0f1420 0%, #151b2e 100%);
            border-right: 1px solid var(--museum-border);
        }}
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown li,
        [data-testid="stSidebar"] .stMarkdown strong,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] p {{
            color: #ffffff !important;
        }}
        [data-testid="stSidebar"] * {{
            color: #ffffff !important;
        }}
        [data-testid="stSidebar"] h1 {{
            color: #ffffff !important;
            font-family: 'Noto Serif SC', serif;
            font-weight: 700;
        }}
        [data-testid="stSidebar"] hr {{
            border-color: rgba(255, 255, 255, 0.15);
        }}
        [data-testid="stSidebar"] .stButton > button {{
            background: rgba(255,255,255,0.08);
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 10px;
            font-weight: 600;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: rgba(201,162,39,0.25);
            color: #e8c547 !important;
            border-color: #c9a227;
        }}

        /* 主标题 */
        .museum-header {{
            font-family: 'Noto Serif SC', serif;
            background: linear-gradient(90deg, #e8c547, #00d4aa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 700;
            margin-bottom: 0.25rem;
            font-size: 90px;
        }}
        .museum-subtitle {{
            color: rgba(255, 255, 255, 0.55);
            font-size: 0.95rem;
            letter-spacing: 0.08em;
        }}

        /* 欢迎卡片 */
        .welcome-card {{
            background: var(--museum-card);
            border: 1px solid var(--museum-border);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin: 1.5rem 0 2rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3),
                        inset 0 1px 0 rgba(255, 255, 255, 0.05);
            position: relative;
            overflow: hidden;
        }}
        .welcome-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--museum-gold), var(--museum-teal), transparent);
        }}
        .welcome-card h2 {{
            font-family: 'Noto Serif SC', serif;
            color: var(--museum-gold-light);
            font-size: 1.5rem;
            margin: 0 0 0.75rem;
        }}
        .welcome-card p {{
            color: rgba(255, 255, 255, 0.75);
            line-height: 1.7;
            margin: 0;
        }}
        .welcome-badge {{
            display: inline-block;
            background: rgba(0, 212, 170, 0.12);
            border: 1px solid rgba(0, 212, 170, 0.3);
            color: var(--museum-teal);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-bottom: 1rem;
        }}

        /* 聊天气泡增强 */
        [data-testid="stChatMessage"] {{
            background: transparent !important;
            border: none !important;
            padding: 0.5rem 0 !important;
        }}
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
            flex-direction: row-reverse;
        }}
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {{
            background: rgba(26,31,46,1);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            color: #ffffff !important;
        }}
        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] span,
        [data-testid="stChatMessage"] li {{
            color: #ffffff !important;
        }}
        [data-testid="stChatMessage"] strong {{
            color: #ffffff !important;
        }}
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] {{
            background: rgba(201, 162, 39, 0.12);
            border-color: rgba(201, 162, 39, 0.2);
        }}
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] {{
            background: rgba(0, 212, 170, 0.06);
            border-color: rgba(0, 212, 170, 0.15);
        }}

        /* 推荐问题按钮 */
        .suggest-label {{
            color: rgba(255, 255, 255, 0.5);
            font-size: 0.85rem;
            margin: 1rem 0 0.5rem;
        }}
        div[data-testid="stHorizontalBlock"] .stButton > button {{
            background: rgba(26, 31, 46, 0.8);
            border: 1px solid var(--museum-border);
            color: rgba(255, 255, 255, 0.85);
            border-radius: 20px;
            font-size: 0.85rem;
            padding: 0.4rem 1rem;
            transition: all 0.2s ease;
        }}
        div[data-testid="stHorizontalBlock"] .stButton > button:hover {{
            border-color: var(--museum-gold);
            color: var(--museum-gold-light);
            background: rgba(201, 162, 39, 0.1);
        }}

        /* 加载动画 */
        .typing-indicator {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 0.5rem 0;
        }}
        .typing-indicator span {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--museum-teal);
            animation: typing-bounce 1.4s infinite ease-in-out both;
        }}
        .typing-indicator span:nth-child(1) {{ animation-delay: -0.32s; }}
        .typing-indicator span:nth-child(2) {{ animation-delay: -0.16s; }}
        @keyframes typing-bounce {{
            0%, 80%, 100% {{ transform: scale(0.6); opacity: 0.4; }}
            40% {{ transform: scale(1); opacity: 1; }}
        }}

        /* 占位页面 */
        .placeholder-card {{
            background: var(--museum-card);
            border: 1px dashed var(--museum-border);
            border-radius: 12px;
            padding: 3rem;
            text-align: center;
            color: rgba(255, 255, 255, 0.5);
        }}

        /* 隐藏 Streamlit 默认 footer */
        footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )