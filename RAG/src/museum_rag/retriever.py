from museum_rag.config import Settings
from museum_rag.embedding import QwenEmbedder
from museum_rag.models import RetrievalResponse, SearchFilters
from museum_rag.store import QdrantStore


class Retriever:
    def __init__(
        self,
        settings: Settings | None = None,
        embedder: QwenEmbedder | None = None,
        store: QdrantStore | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self._owns_embedder = embedder is None
        self._owns_store = store is None
        self.embedder = embedder or QwenEmbedder(self.settings)
        self.store = store or QdrantStore(self.settings)

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> RetrievalResponse:
        query = query.strip()
        if not query:
            raise ValueError("查询文本不能为空")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k 必须在 1 到 20 之间")
        embedding = await self.embedder.embed_query(query)
        hits, version = await self.store.search(embedding, top_k=top_k, filters=filters)
        insufficient = not hits or hits[0].score < self.settings.retrieval_score_threshold
        return RetrievalResponse(
            query=query,
            evidence_insufficient=insufficient,
            hits=hits,
            dataset_version=version,
        )

    async def aclose(self) -> None:
        if self._owns_embedder:
            await self.embedder.aclose()
        if self._owns_store:
            await self.store.aclose()

    async def __aenter__(self) -> "Retriever":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

