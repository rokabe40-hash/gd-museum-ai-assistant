from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    dashscope_api_key: str = ""
    dashscope_base_url: str = ""
    dashscope_workspace_id: str = ""
    embedding_model: str = "qwen3.7-text-embedding"
    embedding_dimension: int = 1024
    embedding_batch_size: int = Field(default=20, ge=1, le=20)
    embedding_timeout_seconds: float = 60.0
    embedding_max_retries: int = 5

    qdrant_mode: Literal["local", "server"] = "local"
    qdrant_path: Path = PROJECT_ROOT / "data" / "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "museum_chunks_v1"
    retrieval_score_threshold: float = 0.0

    data_root: Path = PROJECT_ROOT
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    report_dir: Path = PROJECT_ROOT / "data" / "reports"
    cache_path: Path = PROJECT_ROOT / "data" / "cache" / "embeddings.sqlite3"

    @computed_field
    @property
    def embedding_endpoint(self) -> str:
        if self.dashscope_base_url:
            return self.dashscope_base_url.rstrip("/")
        if not self.dashscope_workspace_id:
            return ""
        return (
            f"https://{self.dashscope_workspace_id}.cn-beijing.maas.aliyuncs.com"
            "/api/v1/services/embeddings/text-embedding/text-embedding"
        )

    def require_embedding_credentials(self) -> None:
        missing = []
        if not self.dashscope_api_key:
            missing.append("DASHSCOPE_API_KEY")
        if not self.embedding_endpoint:
            missing.append("DASHSCOPE_BASE_URL 或 DASHSCOPE_WORKSPACE_ID")
        if missing:
            raise ValueError(f"缺少嵌入服务配置：{', '.join(missing)}")
