from pathlib import Path

from museum_rag.chunk import MAX_CHARS, chunk_documents
from museum_rag.normalize import normalize_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_chunk_current_dataset_is_stable_and_bounded(tmp_path: Path) -> None:
    documents = normalize_data(
        PROJECT_ROOT,
        tmp_path / "documents.jsonl",
        tmp_path / "cleaning.json",
    )
    first = chunk_documents(documents)
    second = chunk_documents(documents)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert len({chunk.chunk_id for chunk in first}) == len(first)
    assert all(chunk.text.strip() for chunk in first)
    assert max(map(lambda chunk: len(chunk.text), first)) <= MAX_CHARS
    assert any(chunk.metadata["title"] == "大事记" for chunk in first)

