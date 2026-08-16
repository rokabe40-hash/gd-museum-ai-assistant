import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from museum_rag.io import read_json, write_json, write_jsonl
from museum_rag.models import Document, Origin, SourceType


DOCUMENT_NAMESPACE = uuid.UUID("42ec4cde-98ec-4da0-b488-543db109ce97")
SPACE_RE = re.compile(r"[ \t\u3000]+")
SENTENCE_RE = re.compile(r"(?<=[。！？；])")


@dataclass
class CleanReport:
    input_records: int = 0
    output_documents: int = 0
    merged_duplicates: int = 0
    text_changes: list[dict[str, Any]] = field(default_factory=list)


def normalize_space(value: str) -> str:
    lines = [SPACE_RE.sub(" ", line).strip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def _comparison_text(value: str) -> str:
    return re.sub(r"[\s，。！？；：、“”‘’（）()《》]+", "", value)


def clean_text(value: str | None) -> tuple[str, list[str]]:
    if not value:
        return "", []
    normalized = normalize_space(str(value))
    sentences = [item.strip() for item in SENTENCE_RE.split(normalized) if item.strip()]
    kept: list[str] = []
    removed: list[str] = []
    for sentence in sentences:
        if not kept:
            kept.append(sentence)
            continue
        previous = _comparison_text(kept[-1])
        current = _comparison_text(sentence)
        similarity = SequenceMatcher(None, previous, current).ratio() if previous and current else 0.0
        same_start = len(previous) >= 20 and len(current) >= 20 and previous[:20] == current[:20]
        if current == previous or (same_start and similarity >= 0.96):
            if len(current) > len(previous):
                removed.append(kept[-1])
                kept[-1] = sentence
            else:
                removed.append(sentence)
            continue
        kept.append(sentence)
    return "".join(kept), removed


def normalize_locations(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        locations = []
        for name, location in value.items():
            normalized_name = normalize_space(str(name))
            for normalized_location in normalize_locations(location):
                locations.append(f"{normalized_name}：{normalized_location}")
        return locations
    if isinstance(value, list):
        return [location for item in value for location in normalize_locations(item)]
    normalized = normalize_space(str(value))
    return [normalized] if normalized else []


def _optional_text(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return normalize_space(str(value))


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_document(
    source_type: SourceType,
    title: str,
    content: str,
    metadata: dict[str, Any],
    origin: Origin,
) -> Document:
    canonical = json.dumps(
        {"source_type": source_type, "title": title, "content": content, "metadata": metadata},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = _content_hash(canonical)
    return Document(
        document_id=str(uuid.uuid5(DOCUMENT_NAMESPACE, f"{source_type}:{digest}")),
        source_type=source_type,
        title=title,
        content=content,
        metadata=metadata,
        origins=[origin],
        content_hash=digest,
    )


def _clean_segments(values: Any) -> tuple[list[str], list[str]]:
    raw_values = values if isinstance(values, list) else [values]
    cleaned: list[str] = []
    removed: list[str] = []
    for value in raw_values:
        text, changes = clean_text(None if value is None else str(value))
        if text:
            cleaned.append(text)
        removed.extend(changes)
    return cleaned, removed


def _convert_info(record: dict, origin: Origin, source_type: SourceType) -> tuple[Document, list[str]]:
    title = normalize_space(str(record["title"]))
    segments, removed = _clean_segments(record.get("info", []))
    content = "\n".join([f"主题：{title}", *segments])
    return _build_document(source_type, title, content, {"topic": title}, origin), removed


def _convert_hall(record: dict, origin: Origin) -> tuple[Document, list[str]]:
    title = normalize_space(str(record["name"]))
    locations = normalize_locations(record.get("location"))
    information, removed = clean_text(record.get("information"))
    lines = [f"展厅名称：{title}"]
    if locations:
        lines.append(f"位置：{'；'.join(locations)}")
    if information:
        lines.append(f"展厅介绍：{information}")
    return _build_document(SourceType.HALL, title, "\n".join(lines), {"location": locations}, origin), removed


def _convert_exhibition(record: dict, origin: Origin) -> tuple[Document, list[str]]:
    title = normalize_space(str(record["title"]))
    state = normalize_space(str(record["state"]))
    introduction, removed = clean_text(record.get("introduction"))
    state_labels = {"current": "当前展览", "permanent": "常设展览", "review": "往期展览"}
    lines = [f"展览名称：{title}", f"展览状态：{state_labels.get(state, state)}"]
    if introduction:
        lines.append(f"展览介绍：{introduction}")
    return _build_document(SourceType.EXHIBITION, title, "\n".join(lines), {"state": state}, origin), removed


def _convert_collection(record: dict, origin: Origin) -> tuple[Document, list[str]]:
    title = normalize_space(str(record["name"]))
    fields = {
        "era": _optional_text(record.get("era")),
        "category": _optional_text(record.get("category")),
        "texture": _optional_text(record.get("texture")),
        "size": _optional_text(record.get("size")),
        "acquisition_source": _optional_text(record.get("source")),
    }
    labels = {
        "era": "年代",
        "category": "类别",
        "texture": "材质",
        "size": "尺寸",
        "acquisition_source": "藏品来源",
    }
    lines = [f"藏品名称：{title}"]
    for key, value in fields.items():
        if value:
            lines.append(f"{labels[key]}：{value}")
    introduction, removed = clean_text(record.get("introduction"))
    if introduction:
        lines.append(f"藏品介绍：{introduction}")
    metadata = {key: value for key, value in fields.items() if value is not None}
    return _build_document(SourceType.COLLECTION, title, "\n".join(lines), metadata, origin), removed


def _convert_facility(record: dict, origin: Origin) -> tuple[Document, list[str]]:
    title = normalize_space(str(record["facility"]))
    locations = normalize_locations(record.get("location"))
    information, removed = clean_text(record.get("information"))
    lines = [f"设施：{title}"]
    if locations:
        lines.append(f"位置：{'；'.join(locations)}")
    if information:
        lines.append(f"说明：{information}")
    return _build_document(SourceType.FACILITY, title, "\n".join(lines), {"location": locations}, origin), removed


Converter = Callable[[dict, Origin], tuple[Document, list[str]]]
FILE_SPECS: dict[str, tuple[SourceType, Converter]] = {
    "基本信息.json": (SourceType.BASIC_INFO, lambda row, origin: _convert_info(row, origin, SourceType.BASIC_INFO)),
    "参观信息.json": (SourceType.VISIT_INFO, lambda row, origin: _convert_info(row, origin, SourceType.VISIT_INFO)),
    "展厅.json": (SourceType.HALL, _convert_hall),
    "展览.json": (SourceType.EXHIBITION, _convert_exhibition),
    "藏品库.json": (SourceType.COLLECTION, _convert_collection),
    "设施信息.json": (SourceType.FACILITY, _convert_facility),
}


def audit_data(data_root: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"files": {}, "total_records": 0}
    for file_name, (_, _) in FILE_SPECS.items():
        rows = read_json(data_root / file_name)
        keys = sorted({key for row in rows for key in row})
        missing = {
            key: sum(row.get(key) is None or row.get(key) == "" or row.get(key) == [] for row in rows)
            for key in keys
        }
        serialized = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
        report["files"][file_name] = {
            "records": len(rows),
            "fields": keys,
            "missing": missing,
            "exact_duplicates": len(serialized) - len(set(serialized)),
        }
        report["total_records"] += len(rows)
    return report


def normalize_data(data_root: Path, output_path: Path, report_path: Path) -> list[Document]:
    unique: dict[str, Document] = {}
    reports: dict[str, CleanReport] = {}
    for file_name, (_, converter) in FILE_SPECS.items():
        rows = read_json(data_root / file_name)
        report = CleanReport(input_records=len(rows))
        for index, row in enumerate(rows):
            document, removed = converter(row, Origin(file=file_name, record_index=index))
            if removed:
                report.text_changes.append({"record_index": index, "removed_segments": removed})
            existing = unique.get(document.document_id)
            if existing:
                existing.origins.extend(document.origins)
                report.merged_duplicates += 1
            else:
                unique[document.document_id] = document
        reports[file_name] = report

    documents = sorted(unique.values(), key=lambda item: (item.source_type, item.title, item.document_id))
    for document in documents:
        reports[document.origins[0].file].output_documents += 1
    write_jsonl(output_path, documents)
    write_json(
        report_path,
        {file_name: report.__dict__ for file_name, report in reports.items()},
    )
    return documents
