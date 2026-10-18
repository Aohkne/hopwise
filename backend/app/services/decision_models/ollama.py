"""Gemma 4 (hoặc model bất kỳ) chạy local bằng Ollama — dùng chung cách gọi với LLM qua
endpoint tương thích OpenAI của Ollama: `{OLLAMA_BASE_URL}/v1/chat/completions`."""

from __future__ import annotations

import time

import httpx

from app.config import get_settings
from app.services.decision_models.llm import LLMClient

# (base_url, model) -> (thời điểm lấy, phiên bản). Cache ngắn: người dùng có thể
# `ollama pull` model khác trong lúc backend vẫn chạy.
_VERSIONS: dict[tuple[str, str], tuple[float, str]] = {}
VERSION_TTL = 60.0
_transport: httpx.AsyncBaseTransport | None = None  # test thay bằng MockTransport


async def ollama_version() -> str | None:
    """Phiên bản thật của model local, VD "gemma4:12b · 11.9B · Q4_K_M".

    Trả None nếu chưa cấu hình, Ollama chưa bật hoặc model chưa được pull (không ném
    lỗi: chỉ dùng để hiển thị).
    """
    settings = get_settings()
    name = settings.ollama_model
    if not name:
        return None
    key = (settings.ollama_base_url, name)
    cached = _VERSIONS.get(key)
    if cached and time.monotonic() - cached[0] < VERSION_TTL:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=3, transport=_transport) as client:
            resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        resp.raise_for_status()
        models = resp.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return None
    wanted = {name, f"{name}:latest"}
    entry = next((m for m in models if m.get("name") in wanted or m.get("model") in wanted), None)
    if not entry:
        return None
    details = entry.get("details") or {}
    parts = [entry.get("name") or name, details.get("parameter_size"), details.get("quantization_level")]
    version = " · ".join(p for p in parts if p)
    _VERSIONS[key] = (time.monotonic(), version)
    return version


class OllamaClient(LLMClient):
    name = "ollama"

    def __init__(self) -> None:
        super().__init__(f"ollama/{get_settings().ollama_model}")

    @property
    def model_name(self) -> str:
        return get_settings().ollama_model or "chưa cấu hình"

    async def decide(self, state: str, questions: dict) -> dict:
        settings = get_settings()
        if not settings.ollama_model:
            raise RuntimeError("Chưa cấu hình OLLAMA_MODEL trong .env (VD gemma4:12b)")
        try:
            result = await super().decide(state, questions)
        except httpx.ConnectError as err:
            raise RuntimeError(
                f"Không kết nối được Ollama ở {settings.ollama_base_url} — bật bằng `ollama serve`"
            ) from err
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                raise RuntimeError(
                    f"Ollama chưa có model '{settings.ollama_model}' — chạy `ollama pull "
                    f"{settings.ollama_model}` (hoặc `ollama create` nếu là biến thể tự tạo, xem GUIDE.md)"
                ) from err
            body = err.response.text[:200]
            hint = ""
            if err.response.status_code == 500 and "no user query" in body:
                # Ollama cắt prompt dài hơn ngữ cảnh (log: "truncating input prompt") rồi mất
                # luôn tin nhắn người dùng. Đã gặp thật với câu có 250 lựa chọn (~9.000 token).
                hint = (" — prompt dài hơn ngữ cảnh của Ollama: dùng biến thể 32K "
                        "(xem GUIDE.md) hoặc giảm BENCH_CHUNK")
            raise RuntimeError(f"Ollama trả HTTP {err.response.status_code}{hint}: {body}") from err
        result["model_version"] = await ollama_version()
        return result
