"""Gọi Jev qua OpenRouter.

Đã verify thủ công trong quá trình nghiên cứu (xem lịch sử dự án): endpoint
đúng là `POST {OPENROUTER_BASE_URL}{OPENROUTER_DECISIONS_PATH}` — KHÔNG phải
`/chat/completions` — với body `{"model": JEV_MODEL, "state": ..., "questions": ...}`.

TODO: triển khai thật — xem TODO.md.
"""

from __future__ import annotations

from app.config import get_settings


class JevClient:
    name = "jev"

    async def decide(self, state: str, questions: dict) -> dict:
        settings = get_settings()
        raise NotImplementedError(
            f"TODO: POST {settings.openrouter_base_url}{settings.openrouter_decisions_path} "
            f"với model={settings.jev_model!r}, body={{'state': state, 'questions': questions}}"
        )
