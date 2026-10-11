"""Đọc cấu hình từ biến môi trường (file .env ở gốc repo)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # OpenRouter / Jev
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api"
    openrouter_decisions_path: str = "/alpha/decisions"
    jev_model: str = "typesafe/jev-1.13"

    # Kev (local, free)
    kev_base_url: str = "http://127.0.0.1:8009"
    kev_model: str = "kev-latest"
    kev_api_key: str = ""

    # Benchmark
    baseline_models: str = ""
    beam_width: int = 1
    max_hops: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
