"""Gọi Kev — bản mã nguồn mở tương thích API với Jev, chạy local/miễn phí.

Server Kev (github.com/jaredpalmer/kev) expose `POST /v1/systemone` với cùng
schema `{state, questions}`. Xem KEV_BASE_URL trong app/config.py.

TODO: triển khai thật — xem TODO.md.
"""

from __future__ import annotations

from app.config import get_settings


class KevClient:
    name = "kev"

    async def decide(self, state: str, questions: dict) -> dict:
        settings = get_settings()
        raise NotImplementedError(
            f"TODO: POST {settings.kev_base_url}/v1/systemone "
            f"với model={settings.kev_model!r}, body={{'state': state, 'questions': questions}}"
        )
