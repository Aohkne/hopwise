"""Gọi Jev qua OpenRouter.

Endpoint và format đã verify thủ công (curl) trong quá trình nghiên cứu
project: Jev là "decisions model", KHÔNG dùng được với /chat/completions —
phải gọi `POST {OPENROUTER_BASE_URL}{OPENROUTER_DECISIONS_PATH}` với body
`{"model": JEV_MODEL, "state": ..., "questions": ...}`.
"""

from __future__ import annotations

import time

import httpx

from app.config import get_settings
from app.services.decision_models import CALL_TIMEOUT


class JevClient:
    name = "jev"

    @property
    def model_name(self) -> str:
        return get_settings().jev_model

    async def decide(self, state: str, questions: dict) -> dict:
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise RuntimeError("Thiếu OPENROUTER_API_KEY trong .env")

        url = settings.openrouter_base_url + settings.openrouter_decisions_path
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": settings.jev_model, "state": state, "questions": questions},
            )
        latency_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        return {
            "answers": data["answers"],
            "usage": data.get("usage", {}),
            "latency_ms": latency_ms,
            # phiên bản thật OpenRouter đã route tới, VD "typesafe/jev-1.13-20260917"
            "model_version": data.get("model"),
        }
