"""LLM gọi thẳng API hãng (không qua OpenRouter) — dùng httpx.MockTransport,
không gọi mạng thật."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.services.decision_models import llm


class S:
    openai_api_key = ""
    google_api_key = "g-key"
    deepseek_api_key = ""


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: S)
    monkeypatch.setattr(llm, "_backoff", 0)
    yield
    monkeypatch.setattr(llm, "_transport", None)


def test_resolve_picks_provider_endpoint_and_key() -> None:
    base, key, name = llm.resolve("google/gemini-3.8-flash")
    assert base == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert key == "g-key" and name == "gemini-3.8-flash"


def test_resolve_rejects_missing_key_and_unknown_provider() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm.resolve("openai/gpt-6-sol")
    with pytest.raises(RuntimeError, match="không hợp lệ"):
        llm.resolve("anthropic/claude")
    with pytest.raises(RuntimeError, match="không hợp lệ"):
        llm.resolve("gemini-3.8-flash")


def test_decide_calls_provider_directly(monkeypatch) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        content = json.dumps({"answer": 0.9, "next": "e1"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 5},
        })

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    questions = {
        "answer": {"type": "noul", "instructions": "?"},
        "next": {"type": "choice", "instructions": "?", "criteria": {"e0": "a", "e1": "b"}},
    }
    reply = asyncio.run(llm.LLMClient("google/gemini-3.8-flash").decide("state", questions))

    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert seen["auth"] == "Bearer g-key"
    assert seen["body"]["model"] == "gemini-3.8-flash"
    assert "openrouter" not in seen["url"]
    assert reply["answers"] == {
        "answer": {"type": "noul", "noul": 0.9},
        "next": {"type": "choice", "choice": "e1"},
    }
    assert reply["usage"]["prompt_tokens"] == 42 and reply["usage"]["cost"] == 0.0


QUESTIONS = {"answer": {"type": "noul", "instructions": "?"}}


def _ok() -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"answer": 0.2}'}}]})


def test_transient_503_is_retried(monkeypatch) -> None:
    replies = [httpx.Response(503), httpx.Response(429), _ok()]
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: replies.pop(0)))
    reply = asyncio.run(llm.LLMClient("google/gemini-3.8-flash").decide("s", QUESTIONS))
    assert reply["answers"]["answer"]["noul"] == 0.2
    assert replies == []


def test_gives_up_after_retries(monkeypatch) -> None:
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503)

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(llm.LLMClient("google/gemini-3.8-flash").decide("s", QUESTIONS))
    assert len(calls) == llm.RETRIES


def test_client_errors_are_not_retried(monkeypatch) -> None:
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(401)

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(llm.LLMClient("google/gemini-3.8-flash").decide("s", QUESTIONS))
    assert len(calls) == 1
