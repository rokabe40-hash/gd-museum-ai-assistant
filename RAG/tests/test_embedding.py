from pathlib import Path

import httpx
import pytest
import respx

from museum_rag.config import Settings
from museum_rag.embedding import EmbeddingCache, QwenEmbedder


@pytest.mark.asyncio
async def test_embedder_parses_dense_sparse_and_uses_cache(tmp_path: Path) -> None:
    settings = Settings(
        dashscope_api_key="test-key",
        dashscope_base_url="https://example.test/embedding",
        embedding_dimension=3,
        cache_path=tmp_path / "cache.sqlite3",
    )
    response = {
        "output": {
            "embeddings": [
                {
                    "text_index": 0,
                    "embedding": [0.1, 0.2, 0.3],
                    "sparse_embedding": [
                        {"index": 10, "value": 0.8, "token": "粤"},
                        {"index": 20, "value": 0.4, "token": "博"},
                    ],
                }
            ]
        }
    }
    async with httpx.AsyncClient() as client:
        cache = EmbeddingCache(settings.cache_path)
        embedder = QwenEmbedder(settings, client=client, cache=cache)
        with respx.mock(assert_all_called=True) as router:
            route = router.post(settings.embedding_endpoint).mock(return_value=httpx.Response(200, json=response))
            first = await embedder.embed_many(["广东省博物馆"], "document")
            second = await embedder.embed_many(["广东省博物馆"], "document")
            assert route.call_count == 1
        cache.close()

    assert first == second
    assert first[0].dense == [0.1, 0.2, 0.3]
    assert first[0].sparse.indices == [10, 20]


@pytest.mark.asyncio
async def test_embedder_retries_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        dashscope_api_key="test-key",
        dashscope_base_url="https://example.test/embedding",
        embedding_dimension=1,
        embedding_max_retries=2,
        cache_path=tmp_path / "cache.sqlite3",
    )
    success = {
        "output": {
            "embeddings": [
                {"text_index": 0, "embedding": [1.0], "sparse_embedding": [{"index": 1, "value": 1.0}]}
            ]
        }
    }

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("museum_rag.embedding.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient() as client:
        cache = EmbeddingCache(settings.cache_path)
        embedder = QwenEmbedder(settings, client=client, cache=cache)
        with respx.mock(assert_all_called=True) as router:
            route = router.post(settings.embedding_endpoint).mock(
                side_effect=[httpx.Response(429), httpx.Response(200, json=success)]
            )
            result = await embedder.embed_many(["测试"], "document")
            assert route.call_count == 2
        cache.close()

    assert result[0].dense == [1.0]


def test_missing_credentials_are_rejected(tmp_path: Path) -> None:
    settings = Settings(
        dashscope_api_key="",
        dashscope_base_url="",
        dashscope_workspace_id="",
        cache_path=tmp_path / "cache.sqlite3",
    )
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        QwenEmbedder(settings)
