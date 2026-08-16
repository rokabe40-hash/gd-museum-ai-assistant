"""各 LangGraph 节点单测：LLM / Neo4j / RAG 全部打桩，不依赖外网。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

import main as agent
from conftest import FakeGraph, FakeRetriever


# ── 路由 ──────────────────────────────────────────────

def test_route_after_intent() -> None:
    assert agent.route_after_intent({"current_intent": "chitchat"}) == "chitchat_node"
    assert agent.route_after_intent({"current_intent": "facility"}) == "facility_node"
    assert agent.route_after_intent({"current_intent": "museum_query"}) == "graph_retrieval_node"
    # 未知 intent 的兜底：intent_parser 已提前规范化，这里只会落到图谱查询
    assert agent.route_after_intent({"current_intent": "乱写"}) == "graph_retrieval_node"


# ── 意图解析 ──────────────────────────────────────────

def test_intent_parser_artifact(stub_llm) -> None:
    stub_llm('{"intent": "museum_query", "entity": "端砚", "entity_type": "artifact"}')
    state = {"messages": [HumanMessage(content="端砚是什么年代的")], "reasoning_log": []}
    out = agent.intent_parser_node(state)
    assert out["current_intent"] == "museum_query"
    assert out["current_entity"] == "端砚"
    assert out["entity_type"] == "artifact"


def test_intent_parser_floor_override(stub_llm) -> None:
    """LLM 误判为 facility/楼层导览，但"三楼+展厅"应强制走图谱楼层查询。"""
    stub_llm('{"intent": "facility", "normalized_keyword": "楼层导览"}')
    state = {"messages": [HumanMessage(content="三楼有什么展厅")], "reasoning_log": []}
    out = agent.intent_parser_node(state)
    assert out["current_intent"] == "museum_query"
    assert out["current_entity"] == "3楼"
    assert out["entity_type"] == "floor"


def test_intent_parser_floor_not_hijack_facility(stub_llm) -> None:
    """带楼层的馆务问题（洗手间在二楼）不应被楼层拦截。"""
    stub_llm('{"intent": "facility", "normalized_keyword": "洗手间"}')
    state = {"messages": [HumanMessage(content="洗手间在二楼")], "reasoning_log": []}
    out = agent.intent_parser_node(state)
    assert out["current_intent"] == "facility"
    assert out["normalized_keyword"] == "洗手间"


def test_intent_parser_chitchat_fallback(stub_llm) -> None:
    """LLM 返回非法 JSON 时兜底为 chitchat。"""
    stub_llm("不是 JSON 的文本")
    state = {"messages": [HumanMessage(content="你好")], "reasoning_log": []}
    out = agent.intent_parser_node(state)
    assert out["current_intent"] == "chitchat"


# ── 图谱检索 ──────────────────────────────────────────

def test_graph_artifact(fake_graph) -> None:
    fake_graph(FakeGraph(artifacts={
        "端砚": {"name": "端砚", "era": "宋代", "texture": "石", "size": "长20cm", "introduction": "文房四宝之首"},
    }))
    state = {"messages": [HumanMessage(content="端砚")], "current_entity": "端砚", "entity_type": "artifact", "reasoning_log": []}
    out = asyncio.run(agent.graph_retrieval_node(state))
    assert out["is_graph_sufficient"] is True
    assert out["graph_result"]["name"] == "端砚"
    assert out["graph_result"]["年代"] == "宋代"


def test_graph_artifact_miss_then_exhibition_list(fake_graph) -> None:
    """未知藏品名 + 泛称展览词，落到展览列表分支。"""
    fake_graph(FakeGraph(exhibitions=[
        {"title": "陶瓷展", "state": "current"},
        {"title": "木雕展", "state": "current"},
    ]))
    state = {"messages": [HumanMessage(content="最近有什么展览")], "current_entity": "", "entity_type": "exhibition", "reasoning_log": []}
    out = asyncio.run(agent.graph_retrieval_node(state))
    assert out["is_graph_sufficient"] is True
    assert out["graph_result"]["name"] == "展览列表"
    assert "陶瓷展" in out["graph_result"]["简介"]


def test_graph_hall(fake_graph) -> None:
    fake_graph(FakeGraph(hall={"name": "广东历史文化展厅", "location": "四楼", "floor": 4, "info": "常设展厅"}))
    state = {"messages": [HumanMessage(content="广东历史文化展厅在哪")], "current_entity": "广东历史文化展厅", "entity_type": "hall", "reasoning_log": []}
    out = asyncio.run(agent.graph_retrieval_node(state))
    assert out["graph_result"]["位置"] == "四楼"


def test_graph_floor_list(fake_graph) -> None:
    fake_graph(FakeGraph(halls_by_floor={3: [
        {"name": "端砚展厅", "location": "三楼", "floor": 3},
        {"name": "潮州木雕展厅", "location": "三楼", "floor": 3},
    ]}))
    state = {"messages": [HumanMessage(content="三楼有什么展厅")], "current_entity": "3楼", "entity_type": "floor", "reasoning_log": []}
    out = asyncio.run(agent.graph_retrieval_node(state))
    assert out["is_graph_sufficient"] is True
    assert "2 个展厅" in out["graph_result"]["简介"]
    assert "端砚展厅" in out["graph_result"]["简介"]


def test_graph_miss_returns_not_sufficient(fake_graph) -> None:
    fake_graph(FakeGraph())
    state = {"messages": [HumanMessage(content="不存在的展品")], "current_entity": "不存在的展品", "entity_type": "artifact", "reasoning_log": []}
    out = asyncio.run(agent.graph_retrieval_node(state))
    assert out["is_graph_sufficient"] is False


# ── 向量检索 ──────────────────────────────────────────

def test_vector_retrieval_hits(fake_retriever) -> None:
    fake_retriever(FakeRetriever(hits=[SimpleNamespace(text="端砚背景故事", score=0.9)]))
    state = {"messages": [HumanMessage(content="端砚")], "current_entity": "端砚", "reasoning_log": []}
    out = asyncio.run(agent.vector_retrieval_node(state))
    assert out["vector_result"] == "端砚背景故事"


def test_vector_retrieval_insufficient(fake_retriever) -> None:
    fake_retriever(FakeRetriever(hits=[], insufficient=True))
    state = {"messages": [HumanMessage(content="端砚")], "current_entity": "端砚", "reasoning_log": []}
    out = asyncio.run(agent.vector_retrieval_node(state))
    assert out["vector_result"] == ""


# ── 生成 ──────────────────────────────────────────────

def test_generate_answer_graph_and_vector(stub_llm) -> None:
    stub_llm("综合回答")
    state = {
        "messages": [HumanMessage(content="端砚是什么年代的")],
        "graph_result": {"name": "端砚", "年代": "宋代", "材质": "石", "简介": "文房四宝之首"},
        "vector_result": "这是一方砚台",
        "is_graph_sufficient": True,
        "reasoning_log": [],
    }
    out = agent.generate_answer_node(state)
    assert out["messages"][0].content == "综合回答"
    assert [c["source_type"] for c in out["citations"]] == ["graph", "vector"]


def test_generate_answer_no_data(stub_llm) -> None:
    stub_llm("暂无资料")
    state = {
        "messages": [HumanMessage(content="未知")],
        "graph_result": None,
        "vector_result": "",
        "is_graph_sufficient": False,
        "reasoning_log": [],
    }
    out = agent.generate_answer_node(state)
    assert out["citations"] == []


# ── 馆务 / 闲聊 ───────────────────────────────────────

def test_facility_node_citation(stub_llm) -> None:
    stub_llm("洗手间在二楼")
    state = {"messages": [HumanMessage(content="洗手间在哪")], "normalized_keyword": "洗手间", "reasoning_log": []}
    out = agent.facility_node(state)
    assert out["facility_result"] == "洗手间在二楼"
    assert any(c["source_type"] == "facility" for c in out["citations"])


def test_chitchat_node(stub_llm) -> None:
    stub_llm("你好呀")
    state = {"messages": [HumanMessage(content="你好")], "reasoning_log": []}
    out = agent.chitchat_node(state)
    assert out["messages"][0].content == "你好呀"
