import hashlib
import re
import uuid
from collections.abc import Iterable

from museum_rag.models import Chunk, Document, SourceType


CHUNK_NAMESPACE = uuid.UUID("921d435f-0a77-49ca-969a-27081c43b45c")
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；])")
TARGET_CHARS = 450
MAX_CHARS = 700
OVERLAP_CHARS = 100


def _split_long_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue
        for sentence in (item.strip() for item in SENTENCE_BOUNDARY.split(paragraph) if item.strip()):
            units.extend(sentence[offset : offset + max_chars] for offset in range(0, len(sentence), max_chars))

    chunks: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
            continue
        if len(current) + 1 + len(unit) <= max_chars:
            current = f"{current}\n{unit}"
            continue

        previous = current
        chunks.append(previous)
        overlap = SENTENCE_BOUNDARY.split(previous[-OVERLAP_CHARS:])[-1].strip()
        if overlap and len(overlap) + 1 + len(unit) <= max_chars:
            current = f"{overlap}\n{unit}"
        else:
            current = unit
        if len(current) >= TARGET_CHARS and len(current) == max_chars:
            chunks.append(current)
            current = ""
    if current:
        if chunks and len(current) < 30 and len(chunks[-1]) + 1 + len(current) <= max_chars:
            chunks[-1] = f"{chunks[-1]}\n{current}"
        else:
            chunks.append(current)
    return chunks


def _document_parts(document: Document, max_chars: int) -> list[str]:
    if document.source_type == SourceType.BASIC_INFO and document.title == "大事记":
        lines = [line for line in document.content.split("\n") if line.strip()]
        header, events = lines[0], lines[1:]
        return [f"{header}\n{event}" for event in events]
    if len(document.content) <= max_chars:
        return [document.content]
    return _split_long_text(document.content, max_chars)


def chunk_documents(documents: Iterable[Document]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        prefix = f"数据类型：{document.source_type.value}\n标题：{document.title}"
        body_limit = MAX_CHARS - len(prefix) - 1
        for index, body in enumerate(_document_parts(document, body_limit)):
            text = f"{prefix}\n{body}"
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunk_id = str(uuid.uuid5(CHUNK_NAMESPACE, f"{document.document_id}:{index}:{digest}"))
            metadata = {
                "source_type": document.source_type.value,
                "title": document.title,
                **document.metadata,
            }
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    chunk_index=index,
                    text=text,
                    metadata=metadata,
                    origins=document.origins,
                    content_hash=digest,
                )
            )
    return chunks
