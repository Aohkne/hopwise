"""gpt-oss-20b (hoặc model khác) qua NVIDIA NIM — endpoint tương thích OpenAI ở
`NVIDIA_BASE_URL` (mặc định https://integrate.api.nvidia.com/v1), xác thực bằng
`NVIDIA_API_KEY`. Tham số gọi (temperature, top_p, max_tokens) nằm trong llm.REQUEST_EXTRAS."""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.services.decision_models.llm import LLMClient


class NvidiaClient(LLMClient):
    name = "nvidia"

    def __init__(self) -> None:
        super().__init__(f"nvidia/{get_settings().nvidia_model}")

    @property
    def model_name(self) -> str:
        return get_settings().nvidia_model or "chưa cấu hình"

    async def decide(self, state: str, questions: dict) -> dict:
        if not get_settings().nvidia_model:
            raise RuntimeError("Chưa cấu hình NVIDIA_MODEL trong .env (VD openai/gpt-oss-20b)")
        try:
            return await super().decide(state, questions)
        except httpx.HTTPStatusError as err:
            code = err.response.status_code
            hint = {401: " — kiểm tra NVIDIA_API_KEY", 403: " — key không có quyền với model này",
                    404: " — sai NVIDIA_MODEL", 429: " — vượt giới hạn tốc độ của NVIDIA"}.get(code, "")
            raise RuntimeError(f"NVIDIA trả HTTP {code}{hint}: {err.response.text[:200]}") from err
