"""Đọc cấu hình từ biến môi trường (file .env ở gốc repo)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # OpenRouter — chỉ dùng cho Jev (decisions model, không gọi thẳng được)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api"
    openrouter_decisions_path: str = "/alpha/decisions"
    jev_model: str = "typesafe/jev-1.13"

    # LLM baseline — gọi thẳng API từng hãng (KHÔNG qua OpenRouter)
    openai_api_key: str = ""
    google_api_key: str = ""
    deepseek_api_key: str = ""

    # Benchmark
    baseline_models: str = "google/gemini-3.8-flash"
    bench_timeout_seconds: float = 300  # 5 phút cho mỗi model mỗi lượt
    # Số lựa chọn mỗi câu Choice khi chia lô. Jev cho tối đa 255 lựa chọn, chừa 1
    # cho "none" -> tối đa 254.
    bench_chunk: int = Field(250, ge=2, le=254)
    outputs_dir: Path = ROOT_ENV_FILE.parent / "outputs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
