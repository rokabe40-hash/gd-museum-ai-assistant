import asyncio
import hashlib
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import httpx

from museum_rag.config import Settings
from museum_rag.models import EmbeddingResult, SparseEmbedding


class EmbeddingCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                cache_key TEXT PRIMARY KEY,
                dense_json TEXT NOT NULL,
                sparse_indices_json TEXT NOT NULL,
                sparse_values_json TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def get(self, cache_key: str) -> EmbeddingResult | None:
        row = self.connection.execute(
            "SELECT dense_json, sparse_indices_json, sparse_values_json FROM embeddings WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        return EmbeddingResult(
            dense=json.loads(row[0]),
            sparse=SparseEmbedding(indices=json.loads(row[1]), values=json.loads(row[2])),
        )

    def put(self, cache_key: str, value: EmbeddingResult) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?, ?)",
            (
                cache_key,
                json.dumps(value.dense, separators=(",", ":")),
                json.dumps(value.sparse.indices, separators=(",", ":")),
                json.dumps(value.sparse.values, separators=(",", ":")),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


class QwenEmbedder:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        settings.require_embedding_credentials()
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=settings.embedding_timeout_seconds)
        self.cache = cache or EmbeddingCache(settings.cache_path)
        self._owns_cache = cache is None

    def _cache_key(self, text: str, text_type: str) -> str:
        source = f"{self.settings.embedding_model}\0{self.settings.embedding_dimension}\0{text_type}\0{text}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    async def _request_batch(self, texts: list[str], text_type: str) -> list[EmbeddingResult]:
        payload = {
            "model": self.settings.embedding_model,
            "input": {"texts": texts},
            "parameters": {
                "dimension": self.settings.embedding_dimension,
                "output_type": "dense&sparse",
                "text_type": text_type,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.settings.embedding_max_retries):
            try:
                response = await self.client.post(self.settings.embedding_endpoint, headers=headers, json=payload)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError("嵌入服务暂时不可用", request=response.request, response=response)
                response.raise_for_status()
                body = response.json()
                items = body.get("output", {}).get("embeddings", [])
                if len(items) != len(texts):
                    raise ValueError(f"嵌入结果数量异常：期望 {len(texts)}，实际 {len(items)}")
                ordered = sorted(items, key=lambda item: item.get("text_index", 0))
                results = []
                for item in ordered:
                    sparse_items = item.get("sparse_embedding") or []
                    result = EmbeddingResult(
                        dense=item["embedding"],
                        sparse=SparseEmbedding(
                            indices=[entry["index"] for entry in sparse_items],
                            values=[entry["value"] for entry in sparse_items],
                        ),
                    )
                    if len(result.dense) != self.settings.embedding_dimension:
                        raise ValueError(
                            f"向量维度异常：期望 {self.settings.embedding_dimension}，实际 {len(result.dense)}"
                        )
                    results.append(result)
                return results
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 == self.settings.embedding_max_retries:
                    break
                await asyncio.sleep(min(2**attempt, 16))
        raise RuntimeError("嵌入请求重试后仍失败") from last_error

    async def embed_many(self, texts: Sequence[str], text_type: str) -> list[EmbeddingResult]:
        if text_type not in {"document", "query"}:
            raise ValueError("text_type 必须是 document 或 query")
        results: list[EmbeddingResult | None] = [None] * len(texts)
        missing: list[tuple[int, str, str]] = []
        for index, text in enumerate(texts):
            if not text.strip():
                raise ValueError("不能嵌入空文本")
            key = self._cache_key(text, text_type)
            cached = self.cache.get(key)
            if cached:
                results[index] = cached
            else:
                missing.append((index, text, key))

        batch_size = self.settings.embedding_batch_size
        for offset in range(0, len(missing), batch_size):
            batch = missing[offset : offset + batch_size]
            embedded = await self._request_batch([item[1] for item in batch], text_type)
            for (index, _, key), result in zip(batch, embedded, strict=True):
                self.cache.put(key, result)
                results[index] = result
        if any(result is None for result in results):
            raise RuntimeError("部分文本未生成嵌入")
        return [result for result in results if result is not None]

    async def embed_query(self, query: str) -> EmbeddingResult:
        return (await self.embed_many([query], "query"))[0]

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()
        if self._owns_cache:
            self.cache.close()

    async def __aenter__(self) -> "QwenEmbedder":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
