"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM (Ollama — local, free, no API key required) ──────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL",
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Ollama model to use for all LLM tasks (e.g. llama3.2, mistral, gemma2)",
    )

    # ── Embeddings (sentence-transformers — local, free) ─────────────────────
    sentence_transformer_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="HuggingFace sentence-transformer model for embeddings (384-dim)",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/research_assistant.db",
        description="Async database URL",
    )

    # ── Environment ──────────────────────────────────────────────────────────
    environment: str = Field(default="development")

    # ── File storage ─────────────────────────────────────────────────────────
    data_dir: Path = Field(default=Path("./data"), description="Root data directory")
    max_upload_size_mb: int = Field(default=50, description="Max PDF upload size in MB")

    # ── External APIs (all free) ─────────────────────────────────────────────
    semantic_scholar_api_key: str = Field(
        default="",
        description="Semantic Scholar API key (optional — increases rate limits)",
    )
    arxiv_user_agent: str = Field(
        default="AgenticResearchAssistant/0.1",
        description="User-Agent for arXiv requests",
    )

    # ── Server ───────────────────────────────────────────────────────────────
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8000)
    frontend_url: str = Field(default="http://localhost:5173")

    # ── Pipeline defaults ────────────────────────────────────────────────────
    default_paper_limit: int = Field(default=50)
    default_relevance_threshold: float = Field(default=0.3)
    embedding_batch_size: int = Field(default=32)
    rag_default_k: int = Field(default=5)
    chunk_tokens: int = Field(default=512)
    chunk_overlap_tokens: int = Field(default=50)
    agent_max_retries: int = Field(default=2)

    # ── Derived paths ────────────────────────────────────────────────────────

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def faiss_dir(self) -> Path:
        return self.data_dir / "faiss"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_data_dirs(self) -> None:
        """Create data subdirectories if they don't exist."""
        for d in (self.uploads_dir, self.exports_dir, self.faiss_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
