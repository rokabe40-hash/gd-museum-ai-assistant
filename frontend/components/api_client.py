"""线上 FastAPI 客户端。"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from components.config import API_CHAT_URL, API_KEY


@dataclass
class ChatResult:
    """一次 /chat 的完整返回：回答文本 + 引用溯源列表。"""

    answer: str
    citations: list[dict[str, str]] = field(default_factory=list)


def _api_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }


def fetch_chat_response(query: str, timeout: int = 60) -> ChatResult:
    """
    调用 POST /chat 接口。

    请求体: {"query": "..."}
    响应体: {"status": "success", "answer": "...", "citations": [...]}
    """
    try:
        response = requests.post(
            API_CHAT_URL,
            json={"query": query},
            headers=_api_headers(),
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError as e:
        return ChatResult(_connection_error_message(e))
    except requests.exceptions.Timeout:
        return ChatResult("**请求超时**，请稍后重试。")
    except Exception as e:
        return ChatResult(f"**请求异常**：{e}")

    if response.status_code == 401:
        return ChatResult("**鉴权失败**：请检查 X-API-Key 是否正确。")
    if response.status_code == 429:
        return ChatResult("**请求过于频繁**：请稍后再试（限流 60 次/分钟）。")
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "success":
            return ChatResult(
                data.get("answer", "接口返回成功，但没有 answer 字段"),
                data.get("citations", []),
            )
        if data.get("status") == "error":
            # 后端异常降级：展示服务端返回的友好提示
            return ChatResult(data.get("answer", "回答服务暂时繁忙，请稍后再试。"))
        return ChatResult(f"**接口返回异常**：{data.get('status', 'unknown')}")

    return ChatResult(
        f"**API 调用失败**\n\n"
        f"- 状态码：`{response.status_code}`\n"
        f"- 返回：{response.text}"
    )


def _connection_error_message(error: Exception) -> str:
    return (
        f"**无法连接后端服务**\n\n"
        f"错误信息：`{error}`\n\n"
        f"请检查网络连接，或确认服务地址：\n"
        f"`{API_CHAT_URL}`"
    )
