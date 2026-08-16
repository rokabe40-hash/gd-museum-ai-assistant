import hashlib
from collections import Counter
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient, models

from museum_rag.config import Settings
from museum_rag.embedding import QwenEmbedder
from museum_rag.models import Chunk, EmbeddingResult, SearchFilters, SearchHit


def dataset_version(chunks: Sequence[Chunk]) -> str:
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda item: item.chunk_id):
        digest.update(chunk.chunk_id.encode("ascii"))
        digest.update(chunk.content_hash.encode("ascii"))
    return digest.hexdigest()[:12]


class QdrantStore:
    def __init__(self, settings: Settings, client: AsyncQdrantClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or self._create_client(settings)

    @staticmethod
    def _create_client(settings: Settings) -> AsyncQdrantClient:
        if settings.qdrant_mode == "local":
            settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            return AsyncQdrantClient(path=str(settings.qdrant_path))
        return AsyncQdrantClient(url=settings.qdrant_url)

    async def ensure_collection(self, recreate: bool = False) -> None:
        collection = self.settings.qdrant_collection
        exists = await self.client.collection_exists(collection)
        if exists and recreate:
            await self.client.delete_collection(collection)
            exists = False
        if not exists:
            await self.client.create_collection(
                collection_name=collection,
                vectors_config={
                    "dense": models.VectorParams(
                        size=self.settings.embedding_dimension,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
                },
            )
            if self.settings.qdrant_mode == "server":
                for field_name in ["source_type", "state", "category", "era", "document_id"]:
                    await self.client.create_payload_index(
                        collection_name=collection,
                        field_name=field_name,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

    async def index_chunks(
        self,
        chunks: Sequence[Chunk],
        embedder: QwenEmbedder,
        recreate: bool = False,
    ) -> str:
        await self.ensure_collection(recreate=recreate)
        version = dataset_version(chunks)
        batch_size = self.settings.embedding_batch_size
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset : offset + batch_size]
            embeddings = await embedder.embed_many([chunk.text for chunk in batch], "document")
            points = [self._point(chunk, embedding, version) for chunk, embedding in zip(batch, embeddings, strict=True)]
            await self.client.upsert(
                collection_name=self.settings.qdrant_collection,
                points=points,
                wait=True,
            )
        return version

    def _point(self, chunk: Chunk, embedding: EmbeddingResult, version: str) -> models.PointStruct:
        payload = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "text": chunk.text,
            "title": chunk.metadata["title"],
            "source_type": chunk.metadata["source_type"],
            "origins": [origin.model_dump() for origin in chunk.origins],
            "dataset_version": version,
            **{key: value for key, value in chunk.metadata.items() if key not in {"title", "source_type"}},
        }
        return models.PointStruct(
            id=chunk.chunk_id,
            vector={
                "dense": embedding.dense,
                "sparse": models.SparseVector(
                    indices=embedding.sparse.indices,
                    values=embedding.sparse.values,
                ),
            },
            payload=payload,
        )

    @staticmethod
    def _query_filter(filters: SearchFilters | None) -> models.Filter | None:
        if filters is None:
            return None
        conditions: list[models.FieldCondition] = []
        if filters.source_types:
            conditions.append(
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchAny(any=[item.value for item in filters.source_types]),
                )
            )
        for field_name in ["state", "category", "era"]:
            value = getattr(filters, field_name)
            if value:
                conditions.append(models.FieldCondition(key=field_name, match=models.MatchValue(value=value)))
        return models.Filter(must=conditions) if conditions else None

    async def search(
        self,
        embedding: EmbeddingResult,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> tuple[list[SearchHit], str | None]:
        query_filter = self._query_filter(filters)
        response = await self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            prefetch=[
                models.Prefetch(query=embedding.dense, using="dense", filter=query_filter, limit=20),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=embedding.sparse.indices,
                        values=embedding.sparse.values,
                    ),
                    using="sparse",
                    filter=query_filter,
                    limit=20,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=max(top_k * 4, 20),
            with_payload=True,
        )
        dense_response = await self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=embedding.dense,
            using="dense",
            query_filter=query_filter,
            limit=max(top_k * 4, 20),
            with_payload=False,
        )
        dense_scores = {str(point.id): point.score for point in dense_response.points}
        counts: Counter[str] = Counter()
        hits: list[SearchHit] = []
        version: str | None = None
        for point in response.points:
            payload = point.payload or {}
            document_id = str(payload["document_id"])
            if counts[document_id] >= 2:
                continue
            counts[document_id] += 1
            version = version or payload.get("dataset_version")
            metadata = {
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "chunk_id",
                    "document_id",
                    "text",
                    "title",
                    "source_type",
                    "origins",
                    "dataset_version",
                }
            }
            hits.append(
                SearchHit.model_validate(
                    {
                        "chunk_id": payload["chunk_id"],
                        "document_id": document_id,
                        "title": payload["title"],
                        "text": payload["text"],
                        "score": dense_scores.get(str(point.id), point.score),
                        "source_type": payload["source_type"],
                        "metadata": metadata,
                        "origins": payload.get("origins", []),
                    }
                )
            )
            if len(hits) >= top_k:
                break
        return hits, version

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.close()
