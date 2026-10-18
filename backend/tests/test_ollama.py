"""Gemma local qua Ollama — dùng httpx.MockTransport, không cần Ollama thật."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.decision_models import llm, ollama

QUESTIONS = {"pick": {"type": "choice", "criteria": {"a": "A", "b": "B"}}}


def settings(model: str = "gemma4:12b") -> SimpleNamespace:
    return SimpleNamespace(ollama_base_url="http://ollama.test:11434/", ollama_model=model,
                           ollama_reasoning_effort="low")


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    ollama._VERSIONS.clear()
    monkeypatch.setattr(ollama, "get_settings", lambda: settings())
    monkeypatch.setattr(llm, "get_settings", lambda: settings())
    monkeypatch.setattr(llm, "_backoff", 0)  # không chờ khi thử lại
    yield
    monkeypatch.setattr(llm, "_transport", None)
    monkeypatch.setattr(ollama, "_transport", None)


def serve(monkeypatch, handler) -> None:
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(ollama, "_transport", httpx.MockTransport(handler))


def tags_and_chat(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{
            "name": "gemma4:12b", "model": "gemma4:12b",
            "details": {"parameter_size": "11.9B", "quantization_level": "Q4_K_M"}}]})
    body = json.loads(request.content)
    assert request.url.path == "/v1/chat/completions" and body["model"] == "gemma4:12b"
    return httpx.Response(200, json={
        "choices": [{"message": {"content": '{"pick": "b"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 42}})


def test_client_calls_local_endpoint_and_reports_version(monkeypatch) -> None:
    serve(monkeypatch, tags_and_chat)
    client = ollama.OllamaClient()
    result = asyncio.run(client.decide("state", QUESTIONS))
    assert result["answers"]["pick"] == {"type": "choice", "choice": "b"}
    assert result["usage"]["cost"] == 0.0 and result["usage"]["prompt_tokens"] == 42
    assert result["model_version"] == "gemma4:12b · 11.9B · Q4_K_M"
    assert client.model_name == "gemma4:12b" and client.name == "ollama"


def test_missing_model_config_is_a_clear_error(monkeypatch) -> None:
    monkeypatch.setattr(ollama, "get_settings", lambda: settings(""))
    with pytest.raises(RuntimeError, match="OLLAMA_MODEL"):
        asyncio.run(ollama.OllamaClient().decide("s", QUESTIONS))
    assert asyncio.run(ollama.ollama_version()) is None


def test_server_off_and_model_not_pulled_give_actionable_errors(monkeypatch) -> None:
    def refuse(request):
        raise httpx.ConnectError("refused")

    serve(monkeypatch, refuse)
    with pytest.raises(RuntimeError, match="ollama serve"):
        asyncio.run(ollama.OllamaClient().decide("s", QUESTIONS))
    assert asyncio.run(ollama.ollama_version()) is None  # không ném lỗi, chỉ để hiển thị

    serve(monkeypatch, lambda request: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(RuntimeError, match="ollama pull gemma4:12b"):
        asyncio.run(ollama.OllamaClient().decide("s", QUESTIONS))


def test_context_overflow_500_is_explained_and_not_retried(monkeypatch) -> None:
    """Ollama cắt prompt quá ngữ cảnh rồi trả 500 "no user query found in messages"."""
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500, json={"error": {"message": "no user query found in messages"}})

    serve(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="biến thể 32K") as info:
        asyncio.run(ollama.OllamaClient().decide("s", QUESTIONS))
    assert "no user query found" in str(info.value)
    assert len(calls) == 1  # lỗi cố định, thử lại chỉ tốn thêm vài phút


def test_empty_answer_with_finish_reason_length_points_to_the_context_fix(monkeypatch) -> None:
    """Model suy luận hết ngữ cảnh 4096 -> content rỗng, finish_reason=length (lỗi đã gặp thật)."""
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})

    serve(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="finish_reason=length") as info:
        asyncio.run(ollama.OllamaClient().decide("s", QUESTIONS))
    assert "biến thể 32K" in str(info.value)
