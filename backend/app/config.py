"""Đọc cấu hình từ biến môi trường (file .env ở gốc repo)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    # Gemma 4 chạy local bằng Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4-12b-32k"  # biến thể 32K ngữ cảnh, xem GUIDE.md
    # Mức suy luận của model local: none | low | medium | high; để trống = mặc định của model.
    # Đo thật gemma4:12b: mặc định ~16s/lần gọi, low ~18-30s, none ~1,4s (nhưng chưa
    # kiểm tra độ chính xác).
    ollama_reasoning_effort: str = "low"

    # gpt-oss-20b qua NVIDIA NIM (https://build.nvidia.com)
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "openai/gpt-oss-20b"

    # Benchmark
    bench_timeout_seconds: float = 300  # 5 phút cho mỗi model mỗi lượt
    # Số lựa chọn mỗi câu Choice khi chia lô. Jev cho tối đa 255 lựa chọn, chừa 1
    # cho "none" -> tối đa 254.
    bench_chunk: int = Field(250, ge=2, le=254)
    outputs_dir: Path = ROOT_ENV_FILE.parent / "outputs"
    cases_dir: Path = ROOT_ENV_FILE.parent / "benchmarks" / "cases"  # ground truth

    # Trích xuất graph từ văn bản (bản 2.0.0, xem backend/app/harness)
    extract_provider: Literal["nvidia", "ollama"] = "nvidia"  # model nào đọc văn bản
    extract_chunk_chars: int = Field(3000, ge=500)  # độ dài tối đa mỗi đoạn gửi model
    # Đầu ra trích xuất dài hơn câu trả lời quyết định; gpt-oss còn dùng token cho suy luận.
    extract_max_tokens: int = Field(8192, ge=1024)
    data_dir: Path = ROOT_ENV_FILE.parent / "data"  # nơi ghi data/<domain>.json


@lru_cache
def get_settings() -> Settings:
    return Settings()
