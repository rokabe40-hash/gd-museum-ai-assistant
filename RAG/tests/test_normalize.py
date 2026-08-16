from pathlib import Path

from museum_rag.models import SourceType
from museum_rag.normalize import audit_data, clean_text, normalize_data, normalize_locations


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_clean_text_removes_adjacent_duplicate_sentence() -> None:
    text, removed = clean_text("第一句话。第一句话。第二句话。")

    assert text == "第一句话。第二句话。"
    assert removed == ["第一句话。"]


def test_normalize_locations_accepts_mixed_input() -> None:
    assert normalize_locations("四楼") == ["四楼"]
    assert normalize_locations(["一楼", " 二楼 "]) == ["一楼", "二楼"]
    assert normalize_locations([{"展一": "四楼", "展二": "三夹层"}]) == [
        "展一：四楼",
        "展二：三夹层",
    ]
    assert normalize_locations(None) == []


def test_audit_and_normalize_current_dataset(tmp_path: Path) -> None:
    audit = audit_data(PROJECT_ROOT)
    assert audit["total_records"] == 3852
    assert audit["files"]["藏品库.json"]["exact_duplicates"] == 186

    documents = normalize_data(
        PROJECT_ROOT,
        tmp_path / "documents.jsonl",
        tmp_path / "cleaning.json",
    )

    assert len(documents) < audit["total_records"]
    assert {document.source_type for document in documents} == set(SourceType)
    assert all(document.content and document.title for document in documents)
    assert any(len(document.origins) > 1 for document in documents)
