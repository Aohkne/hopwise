"""LLM gọi thẳng API (Ollama local, NVIDIA NIM) — dùng httpx.MockTransport,
không gọi mạng thật."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.decision_models import llm, nvidia


def make_settings(**over) -> SimpleNamespace:
    base = {
        "ollama_base_url": "http://ollama.test:11434/", "ollama_model": "gemma4:12b",
        "ollama_reasoning_effort": "low",
        "nvidia_api_key": "nv-key", "nvidia_base_url": "https://integrate.api.nvidia.com/v1/",
        "nvidia_model": "openai/gpt-oss-20b",
    }
    return SimpleNamespace(**{**base, **over})


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    s = make_settings()
    for module in (llm, nvidia):
        monkeypatch.setattr(module, "get_settings", lambda s=s: s)
    monkeypatch.setattr(llm, "_backoff", 0)
    yield
    monkeypatch.setattr(llm, "_transport", None)


QUESTIONS = {
    "answer": {"type": "noul", "instructions": "?"},
    "next": {"type": "choice", "instructions": "?", "criteria": {"e0": "a", "e1": "b"}},
}


def completion(content: str | None, **extra) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content, **extra}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 5},
    })


def test_resolve_ollama_needs_no_key_and_nvidia_uses_its_key() -> None:
    assert llm.resolve("ollama/gemma4:12b") == ("http://ollama.test:11434/v1", "ollama", "gemma4:12b")
    base, key, name = llm.resolve("nvidia/openai/gpt-oss-20b")
    assert base == "https://integrate.api.nvidia.com/v1" and key == "nv-key"
    assert name == "openai/gpt-oss-20b"  # chỉ bỏ phần nơi cung cấp


def test_resolve_rejects_missing_key_and_unknown_provider(monkeypatch) -> None:
    monkeypatch.setattr(llm, "get_settings", lambda: make_settings(nvidia_api_key=""))
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        llm.resolve("nvidia/openai/gpt-oss-20b")
    for bad in ("google/gemini-3.8-flash", "openai/gpt-4o", "gpt-oss-20b", "nvidia/", "ollama/"):
        with pytest.raises(RuntimeError, match="không hợp lệ"):
            llm.resolve(bad)


def test_nvidia_request_matches_the_official_example(monkeypatch) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return completion(json.dumps({"answer": 0.9, "next": "e1"}), reasoning_content="đang suy luận...")

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    reply = asyncio.run(nvidia.NvidiaClient().decide("state", QUESTIONS))

    assert seen["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert seen["auth"] == "Bearer nv-key"
    body = seen["body"]
    assert body["model"] == "openai/gpt-oss-20b"
    assert (body["temperature"], body["top_p"], body["max_tokens"]) == (1, 1, 4096)
    assert "response_format" not in body  # NIM không đảm bảo hỗ trợ JSON mode
    assert reply["answers"] == {"answer": {"type": "noul", "noul": 0.9},
                                "next": {"type": "choice", "choice": "e1"}}
    assert reply["usage"]["prompt_tokens"] == 42 and reply["usage"]["cost"] == 0.0
    assert nvidia.NvidiaClient().model_name == "openai/gpt-oss-20b"


def test_ollama_request_forces_json_mode(monkeypatch) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"], seen["url"] = json.loads(request.content), str(request.url)
        return completion('{"answer": 0.1}')

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    asyncio.run(llm.LLMClient("ollama/gemma4:12b").decide("s", QUESTIONS))
    assert seen["url"] == "http://ollama.test:11434/v1/chat/completions"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["reasoning_effort"] == "low"  # mặc định của OLLAMA_REASONING_EFFORT
    assert "temperature" not in seen["body"]


def test_ollama_reasoning_effort_is_configurable_and_can_be_left_to_the_model(monkeypatch) -> None:
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return completion('{"answer": 0.1}')

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    for effort in ("none", ""):
        monkeypatch.setattr(llm, "get_settings", lambda e=effort: make_settings(ollama_reasoning_effort=e))
        asyncio.run(llm.LLMClient("ollama/gemma4:12b").decide("s", QUESTIONS))
    assert bodies[0]["reasoning_effort"] == "none"
    assert "reasoning_effort" not in bodies[1]  # để trống = mặc định của model


def test_json_inside_fences_or_prose_is_accepted_but_nothing_is_invented(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(
        lambda req: completion('Kết quả:\n```json\n{"answer": 0.3}\n```')))
    assert asyncio.run(llm.LLMClient("ollama/q").decide("s", QUESTIONS))["answers"]["answer"]["noul"] == 0.3

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: completion("không có json")))
    with pytest.raises(RuntimeError, match="không trả JSON hợp lệ"):
        asyncio.run(llm.LLMClient("ollama/q").decide("s", QUESTIONS))


def test_empty_content_from_a_reasoning_model_explains_why(monkeypatch) -> None:
    """gpt-oss dùng hết max_tokens cho bước suy luận -> content rỗng, finish_reason=length."""
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "reasoning_content": "..."},
                                                      "finish_reason": "length"}]})

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="finish_reason=length"):
        asyncio.run(nvidia.NvidiaClient().decide("s", QUESTIONS))


def test_transient_errors_are_retried_then_given_up(monkeypatch) -> None:
    replies = [httpx.Response(503), httpx.Response(429), completion('{"answer": 0.2}')]
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: replies.pop(0)))
    assert asyncio.run(nvidia.NvidiaClient().decide("s", QUESTIONS))["answers"]["answer"]["noul"] == 0.2
    assert replies == []

    calls = []
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: (calls.append(1), httpx.Response(503))[1]))
    with pytest.raises(RuntimeError, match="NVIDIA trả HTTP 503"):
        asyncio.run(nvidia.NvidiaClient().decide("s", QUESTIONS))
    assert len(calls) == llm.RETRIES


def test_nvidia_client_errors_are_explained_and_not_retried(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: (calls.append(1), httpx.Response(401, text="bad key"))[1]))
    with pytest.raises(RuntimeError, match="kiểm tra NVIDIA_API_KEY"):
        asyncio.run(nvidia.NvidiaClient().decide("s", QUESTIONS))
    assert len(calls) == 1


@pytest.mark.parametrize("raw, expected", [
    ('{"answer": "false", "next": "e1"}', 0.0),   # gpt-oss trả thật như vậy (football-002)
    ('{"answer": true, "next": "e1"}', 1.0),
    ('{"answer": "0.75", "next": "e1"}', 0.75),
    ('{"answer": "Yes", "next": "e1"}', 1.0),
])
def test_noul_accepts_booleans_and_numeric_strings(monkeypatch, raw, expected) -> None:
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: completion(raw)))
    reply = asyncio.run(nvidia.NvidiaClient().decide("s", QUESTIONS))
    assert reply["answers"]["answer"] == {"type": "noul", "noul": expected}
    assert reply["answers"]["next"] == {"type": "choice", "choice": "e1"}


def test_unreadable_noul_is_treated_as_no_answer_not_a_crash(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(
        lambda req: completion('{"answer": "có lẽ", "next": "e0"}')))
    reply = asyncio.run(nvidia.NvidiaClient().decide("s", QUESTIONS))
    assert "answer" not in reply["answers"]  # vòng lặp coi như điểm 0 -> đi tiếp, không đoán
    assert reply["answers"]["next"] == {"type": "choice", "choice": "e0"}


def test_complete_returns_plain_text_without_forcing_json(monkeypatch) -> None:
    """Trích xuất graph cần văn bản thô: Ollama không bị ép JSON mode, NVIDIA nhận max_tokens riêng."""
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return completion('("entity"<|>VF3<|>PRODUCT<|>xe)')

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    local = asyncio.run(llm.LLMClient("ollama/gemma4:12b").complete("prompt", max_tokens=8192))
    cloud = asyncio.run(nvidia.NvidiaClient().complete("prompt", max_tokens=8192))

    assert local["text"] == cloud["text"] == '("entity"<|>VF3<|>PRODUCT<|>xe)'
    assert local["truncated"] is False and local["usage"]["prompt_tokens"] == 42
    assert bodies[0]["messages"] == [{"role": "user", "content": "prompt"}]  # prompt tự mang chỉ dẫn
    assert "response_format" not in bodies[0] and bodies[0]["max_tokens"] == 8192
    assert bodies[1]["max_tokens"] == 8192  # thay mức mặc định 4096


def test_complete_flags_truncated_output_and_retries_like_decide(monkeypatch) -> None:
    replies = [httpx.Response(503), httpx.Response(200, json={
        "choices": [{"message": {"content": "cụt"}, "finish_reason": "length"}]})]
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: replies.pop(0)))
    reply = asyncio.run(nvidia.NvidiaClient().complete("p"))
    assert reply["text"] == "cụt" and reply["truncated"] is True
    assert replies == []  # 503 được thử lại


def test_complete_translates_http_errors_like_decide(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(lambda req: httpx.Response(401, text="no")))
    with pytest.raises(RuntimeError, match="kiểm tra NVIDIA_API_KEY"):
        asyncio.run(nvidia.NvidiaClient().complete("p"))
