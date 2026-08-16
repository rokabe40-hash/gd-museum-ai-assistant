import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from museum_rag.chunk import chunk_documents
from museum_rag.config import Settings
from museum_rag.embedding import QwenEmbedder
from museum_rag.evaluate import evaluate_retriever
from museum_rag.io import read_jsonl, write_json, write_jsonl
from museum_rag.models import Chunk, Document, SearchFilters, SourceType
from museum_rag.normalize import audit_data, normalize_data
from museum_rag.retriever import Retriever
from museum_rag.store import QdrantStore


app = typer.Typer(help="广东省博物馆 RAG 数据处理与检索工具", no_args_is_help=True)


def _settings() -> Settings:
    return Settings()


@app.command()
def audit() -> None:
    """审计六份原始 JSON 并输出统计报告。"""
    settings = _settings()
    report = audit_data(settings.data_root)
    output = settings.report_dir / "audit.json"
    write_json(output, report)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    typer.echo(f"报告已写入 {output}")


@app.command()
def normalize() -> None:
    """将不同原始结构转换成统一文档 JSONL。"""
    settings = _settings()
    output = settings.processed_dir / "documents.jsonl"
    report = settings.report_dir / "cleaning.json"
    documents = normalize_data(settings.data_root, output, report)
    typer.echo(f"生成 {len(documents)} 篇文档：{output}")
    typer.echo(f"清洗报告：{report}")


@app.command()
def chunk() -> None:
    """将统一文档切分成待嵌入文本块。"""
    settings = _settings()
    source = settings.processed_dir / "documents.jsonl"
    if not source.exists():
        raise typer.BadParameter("缺少 documents.jsonl，请先运行 museum-rag normalize")
    documents = read_jsonl(source, Document)
    chunks = chunk_documents(documents)
    output = settings.processed_dir / "chunks.jsonl"
    write_jsonl(output, chunks)
    typer.echo(f"生成 {len(chunks)} 个文本块：{output}")


async def _index(recreate: bool) -> None:
    settings = _settings()
    source = settings.processed_dir / "chunks.jsonl"
    if not source.exists():
        raise typer.BadParameter("缺少 chunks.jsonl，请先运行 museum-rag chunk")
    chunks = read_jsonl(source, Chunk)
    async with QwenEmbedder(settings) as embedder:
        store = QdrantStore(settings)
        try:
            version = await store.index_chunks(chunks, embedder, recreate=recreate)
        finally:
            await store.aclose()
    typer.echo(f"索引完成，数据版本：{version}")


@app.command()
def index(
    recreate: Annotated[bool, typer.Option("--recreate", help="删除并重建派生向量集合")] = False,
) -> None:
    """调用 Qwen 生成向量并写入 Qdrant。"""
    asyncio.run(_index(recreate))


def _parse_source_types(value: str | None) -> list[SourceType] | None:
    if not value:
        return None
    return [SourceType(item.strip()) for item in value.split(",") if item.strip()]


async def _search(
    query: str,
    top_k: int,
    source_type: str | None,
    state: str | None,
    category: str | None,
    era: str | None,
) -> None:
    filters = SearchFilters(
        source_types=_parse_source_types(source_type),
        state=state,
        category=category,
        era=era,
    )
    async with Retriever(_settings()) as retriever:
        response = await retriever.retrieve(query, top_k=top_k, filters=filters)
    typer.echo(response.model_dump_json(indent=2))


@app.command()
def search(
    query: str,
    top_k: Annotated[int, typer.Option(min=1, max=20)] = 5,
    source_type: Annotated[str | None, typer.Option(help="逗号分隔的 source_type")] = None,
    state: str | None = None,
    category: str | None = None,
    era: str | None = None,
) -> None:
    """执行 Dense+Sparse 混合检索。"""
    asyncio.run(_search(query, top_k, source_type, state, category, era))


async def _evaluate(dataset: Path, top_k: int) -> None:
    settings = _settings()
    output = settings.report_dir / "evaluation.json"
    async with Retriever(settings) as retriever:
        report = await evaluate_retriever(retriever, dataset, output, top_k=top_k)
    typer.echo(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    typer.echo(f"评测报告：{output}")


@app.command(name="evaluate")
def evaluate_command(
    dataset: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path("data/evaluation/qa_dataset.jsonl"),
    top_k: Annotated[int, typer.Option(min=1, max=20)] = 5,
) -> None:
    """在标注问题集上评测召回和拒答效果。"""
    asyncio.run(_evaluate(dataset, top_k))


if __name__ == "__main__":
    app()

