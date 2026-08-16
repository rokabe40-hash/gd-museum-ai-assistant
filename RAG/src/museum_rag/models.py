from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    BASIC_INFO = "basic_info"
    VISIT_INFO = "visit_info"
    HALL = "hall"
    EXHIBITION = "exhibition"
    COLLECTION = "collection"
    FACILITY = "facility"


class Origin(BaseModel):
    file: str
    record_index: int = Field(ge=0)


class Document(BaseModel):
    schema_version: str = "1.0"
    document_id: str
    source_type: SourceType
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    origins: list[Origin]
    content_hash: str


class Chunk(BaseModel):
    schema_version: str = "1.0"
    chunk_id: str
    document_id: str
    chunk_index: int = Field(ge=0)
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    origins: list[Origin]
    content_hash: str


class SparseEmbedding(BaseModel):
    indices: list[int]
    values: list[float]


class EmbeddingResult(BaseModel):
    dense: list[float]
    sparse: SparseEmbedding


class SearchFilters(BaseModel):
    source_types: list[SourceType] | None = None
    state: str | None = None
    category: str | None = None
    era: str | None = None


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    text: str
    score: float
    source_type: SourceType
    metadata: dict[str, Any] = Field(default_factory=dict)
    origins: list[Origin]


class RetrievalResponse(BaseModel):
    query: str
    evidence_insufficient: bool
    hits: list[SearchHit]
    dataset_version: str | None = None

