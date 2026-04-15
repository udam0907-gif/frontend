from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "R&D 비용 집행 관리 시스템"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)
    api_v1_prefix: str = "/api/v1"
    # Comma-separated origins stored as string, parsed at runtime
    allowed_origins_str: str = "http://localhost:3000,http://localhost:3001"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins_str.split(",") if o.strip()]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/rnd_expense_db"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # LLM
    anthropic_api_key: str = ""
    llm_provider: Literal["anthropic", "ollama"] = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1
    prompt_cache_enabled: bool = True

    # Embedding
    embedding_provider: Literal["openai", "local"] = "local"
    openai_api_key: str = ""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_base_path: str = "./storage"
    storage_templates_path: str = "./storage/templates"
    storage_documents_path: str = "./storage/documents"
    storage_manuals_path: str = "./storage/manuals"
    storage_exports_path: str = "./storage/exports"

    # RAG
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    rag_max_chunks: int = 5
    rag_min_confidence: float = 0.75

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    def ensure_storage_dirs(self) -> None:
        for path_attr in [
            "storage_base_path",
            "storage_templates_path",
            "storage_documents_path",
            "storage_manuals_path",
            "storage_exports_path",
        ]:
            os.makedirs(getattr(self, path_attr), exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
