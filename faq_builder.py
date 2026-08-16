# ============================================================
# FAQ 数据 ETL 模块
# 负责读取、清洗、转换博物馆静态知识数据
# ============================================================

from __future__ import annotations

import json
import os
from pathlib import Path


# 数据文件所在目录（与本文件同目录）
_DATA_DIR = Path(__file__).parent


def _read_json_file(filename: str) -> list[dict]:
    """读取 JSON 文件，失败时返回空列表。"""
    filepath = _DATA_DIR / filename
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[faq_builder] 文件不存在: {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"[faq_builder] JSON 解析失败: {filepath}, 错误: {e}")
        return []


def _flatten_records(records: list[dict]) -> str:
    """将 {title, info[]} 结构拍平为 Markdown 文本。"""
    lines: list[str] = []
    for rec in records:
        title = rec.get("title", "").strip()
        info_list = rec.get("info", [])
        if not title:
            continue
        lines.append(f"## {title}")
        for item in info_list:
            item = str(item).strip()
            if item:
                lines.append(f"- {item}")
        lines.append("")  # 空行分隔
    return "\n".join(lines)


def _flatten_facilities(records: list[dict]) -> str:
    """将 {facility, location[], information} 结构拍平为 Markdown 文本。"""
    lines: list[str] = []
    for rec in records:
        facility = rec.get("facility", "").strip()
        if not facility:
            continue
        locations = rec.get("location") or []
        info = (rec.get("information") or "").strip()
        lines.append(f"## {facility}")
        if locations:
            loc_str = "、".join(str(loc).strip() for loc in locations if loc)
            if loc_str:
                lines.append(f"- 位置：{loc_str}")
        if info:
            lines.append(f"- 说明：{info}")
        lines.append("")
    return "\n".join(lines)


def load_and_flatten_faq() -> str:
    """
    读取基本信息.json 和参观信息.json，拍平为一个 Markdown 字符串。
    文件不存在或解析失败时返回友好默认文本，绝不抛出致命异常。
    """
    sections: list[str] = []

    # 读取基本信息
    basic_records = _read_json_file("基本信息.json")
    if basic_records:
        sections.append("# 博物馆基本信息\n")
        sections.append(_flatten_records(basic_records))
    else:
        sections.append("# 博物馆基本信息\n\n暂无基本信息数据。\n")

    # 读取参观信息
    visit_records = _read_json_file("参观信息.json")
    if visit_records:
        sections.append("# 参观须知\n")
        sections.append(_flatten_records(visit_records))
    else:
        sections.append("# 参观须知\n\n暂无参观信息数据。\n")

    # 读取设施信息
    facility_records = _read_json_file("设施信息.json")
    if facility_records:
        sections.append("# 馆内设施\n")
        sections.append(_flatten_facilities(facility_records))
    else:
        sections.append("# 馆内设施\n\n暂无设施信息数据。\n")

    result = "\n".join(sections).strip()

    # 兜底：如果结果为空，返回默认提示
    if not result:
        return "暂无博物馆 FAQ 数据，请前往服务台咨询。"

    return result
