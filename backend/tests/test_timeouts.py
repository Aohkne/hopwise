"""Cả 2 client dùng chung CALL_TIMEOUT: không giới hạn chờ phản hồi 1 lần gọi
(giới hạn thật là 5 phút/model ở benchmark.py), chỉ giới hạn kết nối."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.services.decision_models import CALL_TIMEOUT, jev, llm


class _Stop(Exception):
    pass


def test_call_timeout_has_no_read_limit_but_short_connect() -> None:
    assert CALL_TIMEOUT.read is None
    assert CALL_TIMEOUT.connect == 5


@pytest.mark.parametrize("module, client", [
    (jev, lambda: jev.JevClient()),
    (llm, lambda: llm.LLMClient("google/gemini-test")),
])
def test_every_client_uses_call_timeout(monkeypatch, module, client) -> None:
    seen = {}

    def fake_async_client(*args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        raise _Stop

    settings = SimpleNamespace(
        openrouter_api_key="k", openrouter_base_url="http://x", openrouter_decisions_path="/d",
        jev_model="j",
        google_api_key="k", openai_api_key="", deepseek_api_key="",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)

    with pytest.raises(_Stop):
        asyncio.run(client().decide("s", {}))
    assert seen["timeout"] is CALL_TIMEOUT
