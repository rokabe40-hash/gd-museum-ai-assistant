"""_parse_floor 楼层号解析单测。"""
from __future__ import annotations

import pytest

from main import _FLOOR_CONTENT_WORDS, _parse_floor


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("三楼", 3),
        ("3楼", 3),
        ("3层", 3),
        ("四楼", 4),
        ("一楼", 1),
        ("负一楼", -1),
        ("地下二层", -2),
        ("B1", -1),
        ("b1", -1),
        ("三楼有什么展厅", 3),
        ("洗手间在二楼", 2),
        # 不应误解析
        ("12楼", None),          # 多位数不解析
        ("几楼", None),
        ("端砚", None),
        ("广东历史文化展厅", None),
        ("", None),
        ("3.5楼", None),
    ],
)
def test_parse_floor(text: str, expected: int | None) -> None:
    assert _parse_floor(text) == expected


@pytest.mark.parametrize(
    "text",
    ["三楼有什么展厅", "4楼有哪些展馆", "二楼展区怎么逛", "负一楼有文物展吗"],
)
def test_floor_content_detection_true(text: str) -> None:
    assert _parse_floor(text) is not None
    assert any(w in text for w in _FLOOR_CONTENT_WORDS)


@pytest.mark.parametrize(
    "text",
    ["洗手间在二楼", "二楼咖啡厅在哪", "三楼停车场怎么去", "母婴室在一楼"],
)
def test_floor_content_detection_false_for_facility(text: str) -> None:
    """馆务问题即使带楼层，也不应命中楼层浏览判定。"""
    assert _parse_floor(text) is not None
    assert not any(w in text for w in _FLOOR_CONTENT_WORDS)
