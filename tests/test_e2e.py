"""端到端集成测试：/chat 全路径，需要 Neo4j/Qdrant/DashScope/DeepSeek 全栈在线。

运行：pytest -m integration
注意：Qdrant 本地库有独占文件锁，跑之前先停掉开发服务器（否则报 Storage folder already accessed）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main as agent

pytestmark = pytest.mark.integration

QUERIES = [
    "你好",
    "洗手间在哪",
    "三楼有什么展厅",
    "端砚是什么年代的",
    "最近有什么展览",
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(agent.app) as c:  # lifespan：连真实 Neo4j + Qdrant
        yield c


@pytest.mark.parametrize("query", QUERIES)
def test_chat_e2e(client: TestClient, query: str) -> None:
    resp = client.post("/chat", json={"query": query})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["answer"]
    assert data["reasoning_steps"]
