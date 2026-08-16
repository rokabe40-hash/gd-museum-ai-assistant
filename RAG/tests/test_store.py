import warnings
from pathlib import Path

import pytest
from qdrant_client import AsyncQdrantClient

from museum_rag.config import Settings
from museum_rag.models import Chunk, EmbeddingResult, Origin, SparseEmbedding
from museum_rag.store import QdrantStore


@pytest.mark.asyncio
async def test_qdrant_dense_sparse_rrf_smoke() -> None:
    settings = Settings(embedding_dimension=3, qdrant_collection="test_collection")
    client = AsyncQdrantClient(location=":memory:")
    store = QdrantStore(settings, client=client)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        await store.ensure_collection()

    chunk = Chunk(
        chunk_id="19dd5500-270d-4a6b-9fb1-4c12b66d1700",
        document_id="doc-1",
        chunk_index=0,
        text="广东历史文化展厅位于四楼",
        metadata={"title": "广东历史文化展厅", "source_type": "hall", "location": ["四楼"]},
        origins=[Origin(file="展厅.json", record_index=0)],
        content_hash="abc",
    )
    embedding = EmbeddingResult(
        dense=[1.0, 0.0, 0.0],
        sparse=SparseEmbedding(indices=[1, 2], values=[1.0, 0.5]),
    )
    await client.upsert(
        collection_name=settings.qdrant_collection,
        points=[store._point(chunk, embedding, "test")],
        wait=True,
    )

    hits, version = await store.search(embedding, top_k=1)

    assert hits[0].title == "广东历史文化展厅"
    assert version == "test"
    await client.close()


@pytest.mark.asyncio
async def test_qdrant_local_persists_after_reopen(tmp_path: Path) -> None:
    settings = Settings(
        embedding_dimension=3,
        qdrant_mode="local",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="persistent_collection",
    )
    chunk = Chunk(
        chunk_id="c426c347-65f8-42f8-b243-37a8a09acb75",
        document_id="doc-persistent",
        chunk_index=0,
        text="端砚展厅位于三楼",
        metadata={"title": "端砚展厅", "source_type": "hall", "location": ["三楼"]},
        origins=[Origin(file="展厅.json", record_index=2)],
        content_hash="persistent",
    )
    embedding = EmbeddingResult(
        dense=[0.0, 1.0, 0.0],
        sparse=SparseEmbedding(indices=[3, 4], values=[0.9, 0.4]),
    )

    first = QdrantStore(settings)
    await first.ensure_collection()
    await first.client.upsert(
        collection_name=settings.qdrant_collection,
        points=[first._point(chunk, embedding, "persisted")],
        wait=True,
    )
    await first.aclose()

    reopened = QdrantStore(settings)
    hits, version = await reopened.search(embedding, top_k=1)
    await reopened.aclose()

    assert hits[0].title == "端砚展厅"
    assert version == "persisted"
