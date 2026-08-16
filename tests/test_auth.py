"""API 访问密钥鉴权单元测试：直接测 check_access_key 依赖，不打外网。"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request

import main as agent


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.mark.parametrize("key", ["", "wrong-key"])
def test_check_access_key_rejects_invalid(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "ACCESS_KEYS", ["secret-1", "secret-2"])
    req = _request({"x-api-key": key} if key else {})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(agent.check_access_key(req))
    assert exc.value.status_code == 401


def test_check_access_key_allows_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "ACCESS_KEYS", ["secret-1", "secret-2"])
    asyncio.run(agent.check_access_key(_request({"x-api-key": "secret-2"})))


def test_check_access_key_disabled_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "ACCESS_KEYS", [])
    asyncio.run(agent.check_access_key(_request({"x-api-key": "anything"})))
