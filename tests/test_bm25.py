"""BM25 中文检索回归：分词器 + 16 个馆务关键词的命中章节。"""
from __future__ import annotations

import pytest

from main import _bm25_tokenize, bm25_retriever

# 每个标准化关键词应命中的章节（Header 2），防止再次出现"任意返回"式的召回回归
KEYWORD_EXPECTED_HEADER = {
    "洗手间": "无障碍洗手间",
    "母婴室": "母婴室",
    "婴儿车": "婴儿车",
    "餐饮": "餐饮服务",
    "咖啡厅": "餐饮服务",
    "停车": "停车信息",
    "行李寄存": "寄存服务",
    "购物": "购物服务",
    "无线网络": "无线网络",
    "便民雨伞": "便民雨伞",
    "轮椅租借": "便民轮椅",
    "充电宝": "充电宝",
    "讲解服务": "讲解预约",
    "预约参观": "参观制度",
    "开放时间": "开放时间",
    "交通路线": "交通路线",
}


def test_bm25_tokenize_cjk_bigram() -> None:
    toks = _bm25_tokenize("洗手间在哪里")
    assert "洗手" in toks
    assert "手间" in toks
    assert "在哪" in toks


def test_bm25_tokenize_ascii_whole_word() -> None:
    toks = _bm25_tokenize("WiFi password 123")
    assert "wifi" in toks
    assert "password" in toks
    assert "123" in toks
    # 不应按空格拆成整句单 token
    assert len(toks) >= 3


@pytest.mark.parametrize(
    ("keyword", "expected_header"),
    list(KEYWORD_EXPECTED_HEADER.items()),
    ids=list(KEYWORD_EXPECTED_HEADER),
)
def test_bm25_recall_hits_expected_section(keyword: str, expected_header: str) -> None:
    docs = bm25_retriever.invoke(keyword)
    assert docs, f"关键词 {keyword} 应至少召回一段"
    top = docs[0]
    h2 = top.metadata.get("Header 2", "")
    h3 = top.metadata.get("Header 3", "")
    assert expected_header in f"{h2} {h3}", (
        f"关键词 {keyword} 命中了 {h2}/{h3}，期望 {expected_header}"
    )
