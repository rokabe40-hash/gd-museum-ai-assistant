"""pytest 共享 fixture：打桩 LLM / Neo4j 图 / RAG 检索器，让节点测试不依赖外网。"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 确保能从项目根导入 main 及其依赖
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

import main as agent  # noqa: E402


class StubLLM:
    """模拟 ChatOpenAI.invoke，返回固定 content。"""

    def __init__(self, content: str = "OK"):
        self._content = content

    def invoke(self, messages: list) -> SimpleNamespace:
        return SimpleNamespace(content=self._content)


@pytest.fixture
def stub_llm(monkeypatch):
    def _set(content: str) -> StubLLM:
        stub = StubLLM(content)
        monkeypatch.setattr(agent, "llm", stub)
        return stub

    return _set


class FakeGraph:
    """内存版 MuseumGraph，覆盖节点测试用到的查询方法。"""

    def __init__(
        self,
        artifacts: dict | None = None,
        hall: dict | None = None,
        exhibition: dict | None = None,
        halls_by_floor: dict | None = None,
        exhibitions: list | None = None,
    ):
        self._artifacts = artifacts or {}
        self._hall = hall
        self._exhibition = exhibition
        self._halls_by_floor = halls_by_floor or {}
        self._exhibitions = exhibitions or []

    async def get_artifact_context(self, name):
        return self._artifacts.get(name)

    async def fulltext_search_artifact(self, keyword, limit=10):
        # 模拟真实全文索引：名字或简介含关键字即命中（含"简介蹭中"误命中）
        hits = [
            {"name": name, "era": data.get("era", "")}
            for name, data in self._artifacts.items()
            if keyword in name or keyword in (data.get("introduction") or "")
        ]
        return hits[:limit]

    async def get_hall(self, name):
        return self._hall

    async def fulltext_search_exhibition(self, keyword, limit=5):
        if self._exhibition:
            return [{"title": self._exhibition["title"], "state": self._exhibition["state"]}]
        return []

    async def get_hall_for_exhibition(self, title):
        return {"hall_name": self._exhibition.get("hall")} if self._exhibition else None

    async def get_exhibitions(self, state=None, limit=50):
        return self._exhibitions

    async def list_halls(self, floor=None):
        return self._halls_by_floor.get(floor, [])


@pytest.fixture
def fake_graph(monkeypatch):
    def _set(graph: FakeGraph) -> FakeGraph:
        monkeypatch.setattr(agent, "museum_graph", graph)
        return graph

    return _set


class FakeRetriever:
    def __init__(self, hits=None, insufficient: bool = False):
        self._hits = hits or []
        self._insufficient = insufficient

    async def retrieve(self, query, top_k=2, filters=None):
        return SimpleNamespace(evidence_insufficient=self._insufficient, hits=self._hits)


@pytest.fixture
def fake_retriever(monkeypatch):
    def _set(retriever: FakeRetriever) -> FakeRetriever:
        monkeypatch.setattr(agent, "rag_retriever", retriever)
        return retriever

    return _set
