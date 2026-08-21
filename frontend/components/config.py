"""应用配置与线上 API 接口。"""

import os

# =========================
# 线上 FastAPI 接口
# =========================
# 容器内通过 compose 注入 API_BASE_URL=http://app:8000 走内网；本地/直跑时回落到公网地址
API_BASE_URL = os.environ.get("API_BASE_URL", "http://REDACTED:8000")
API_CHAT_URL = f"{API_BASE_URL}/chat"
API_HEALTH_URL = f"{API_BASE_URL}/health"

# 鉴权密钥（见交接文档）；容器内/本地均由环境变量 API_KEY 提供，源码不写死线上 key
API_KEY = os.environ.get("API_KEY", "")

# 推荐问题
SUGGESTED_QUESTIONS = [
    "端砚是什么年代的？",
    "介绍一下“白切鸡”广宁玉雕",
    "请介绍一下岭南文化的发展脉络",
    "博物馆有哪些适合亲子参观的展区？",
]

# AI 助手信息
ASSISTANT_NAME = "粤博智游"
ASSISTANT_AVATAR = "🏛️"
