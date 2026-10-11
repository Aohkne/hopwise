"""Gọi Kev — bản mã nguồn mở tương thích API với Jev, chạy local/miễn phí.

Server Kev (github.com/jaredpalmer/kev) expose `POST /v1/systemone` với cùng
schema `{state, questions}` và response `{answers, usage}` như Jev.
"""

from __future__ import annotations

import time

import httpx

from app.config import get_settings


class KevClient:
    name = "kev"

    async def decide(self, state: str, questions: dict) -> dict:
        settings = get_settings()
        url = f"{settings.kev_base_url}/v1/systemone"
        headers = {"Content-Type": "application/json"}
        if settings.kev_api_key:
            headers["Authorization"] = f"Bearer {settings.kev_api_key}"

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={"model": settings.kev_model, "state": state, "questions": questions},
            )
        latency_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        return {
            "answers": data["answers"],
            "usage": data.get("usage", {}),
            "latency_ms": latency_ms,
        }
