"""线上 FastAPI 客户端。"""

from __future__ import annotations

import time
from collections.abc import Generator

import requests

from components.config import API_CHAT_URL, API_KEY


def _api_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }


def fetch_chat_response(query: str, timeout: int = 60) -> str:
    """
    调用 POST /chat 接口。

    请求体: {"query": "..."}
    响应体: {"status": "success", "answer": "...", ...}
    """
    response = requests.post(
        API_CHAT_URL,
        json={"query": query},
        headers=_api_headers(),
        timeout=timeout,
    )

    if response.status_code == 401:
        return "**鉴权失败**：请检查 X-API-Key 是否正确。"
    if response.status_code == 429:
        return "**请求过于频繁**：请稍后再试（限流 60 次/分钟）。"
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "success":
            return data.get("answer", "接口返回成功，但没有 answer 字段")
        return f"**接口返回异常**：{data.get('status', 'unknown')}"

    return (
        f"**API 调用失败**\n\n"
        f"- 状态码：`{response.status_code}`\n"
        f"- 返回：{response.text}"
    )


def stream_chat_response(query: str, timeout: int = 60) -> Generator[str, None, None]:
    """调用 /chat 并以打字机效果流式展示回答。"""
    try:
        full_answer = fetch_chat_response(query, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        yield _connection_error_message(e)
        return
    except requests.exceptions.Timeout:
        yield "**请求超时**，请稍后重试。"
        return
    except Exception as e:
        yield f"**请求异常**：{e}"
        return

    for char in full_answer:
        yield char
        time.sleep(0.015)


def _connection_error_message(error: Exception) -> str:
    return (
        f"**无法连接后端服务**\n\n"
        f"错误信息：`{error}`\n\n"
        f"请检查网络连接，或确认服务地址：\n"
        f"`{API_CHAT_URL}`"
    )
