"""Gọi LLM thông thường (System 2) để so sánh với Jev (System 1): Gemma 4 chạy local
bằng Ollama và gpt-oss-20b qua NVIDIA NIM. Cả hai đều có endpoint tương thích chuẩn
OpenAI `/chat/completions`, nên dùng chung 1 client.

Model ghi dạng "<nhà cung cấp>/<model>": phần đầu chọn endpoint + API key, phần sau là
tên model gửi đi (VD "nvidia/openai/gpt-oss-20b" -> gửi "openai/gpt-oss-20b" tới NVIDIA).
Cả hai nơi đều không trả chi phí, nên `cost` luôn là 0.

Khác biệt so với jev.py: LLM không hiểu sẵn schema `{state, questions}`
của TypeSafe System One, nên phải tự convert `questions` thành 1 prompt tự
nhiên yêu cầu trả lời bằng JSON, rồi tự parse ngược lại. Không bịa thêm
`probabilities`/`confidence` như Jev trả về — một LLM thường không tính
ra con số đó, bịa ra sẽ gây hiểu nhầm khi so sánh.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx

from app.config import get_settings
from app.services.decision_models import CALL_TIMEOUT

PROVIDERS = ("ollama", "nvidia")

def request_extras(provider: str) -> dict:
    """Tham số riêng của từng nơi.

    NVIDIA: đúng ví dụ chính thức của build.nvidia.com (temperature 1, top_p 1,
    max_tokens 4096) và không ép JSON mode — gpt-oss có bước suy luận riêng
    (`reasoning_content`) và NIM không đảm bảo hỗ trợ response_format.
    Ollama: ép JSON mode và đặt mức suy luận (OLLAMA_REASONING_EFFORT) cho model local.
    """
    if provider == "nvidia":
        return {"temperature": 1, "top_p": 1, "max_tokens": 4096}
    if provider == "ollama":
        extras: dict = {"response_format": {"type": "json_object"}}
        effort = get_settings().ollama_reasoning_effort
        if effort:
            extras["reasoning_effort"] = effort
        return extras
    return {}

# Để test thay bằng httpx.MockTransport (không gọi mạng thật).
_transport: httpx.AsyncBaseTransport | None = None

# Lỗi tạm thời (quá tải, rate-limit) -> thử lại thay vì đánh lỗi cả lượt.
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRIES = 3
_backoff = 1.0  # giây, nhân đôi mỗi lần; test đặt về 0


def resolve(model: str) -> tuple[str, str, str]:
    """"nvidia/openai/gpt-oss-20b" -> (base_url, api_key, "openai/gpt-oss-20b")."""
    provider, _, name = model.partition("/")
    settings = get_settings()
    if provider == "ollama" and name:  # chạy local, không cần API key
        return f"{settings.ollama_base_url.rstrip('/')}/v1", "ollama", name
    if provider == "nvidia" and name:
        if not settings.nvidia_api_key:
            raise RuntimeError("Thiếu NVIDIA_API_KEY trong .env (lấy ở https://build.nvidia.com)")
        return settings.nvidia_base_url.rstrip("/"), settings.nvidia_api_key, name
    raise RuntimeError(
        f"Model '{model}' không hợp lệ — cần dạng <nơi>/<model>, nơi ∈ {sorted(PROVIDERS)}"
    )


_SYSTEM_PROMPT = """\
Bạn trả lời các câu hỏi có cấu trúc dựa trên một đoạn "state" cho trước.
Mỗi câu hỏi có 1 "type":
- "noul": trả lời bằng 1 số thực trong [0, 1] — xác suất điều được hỏi là đúng.
- "choice": chọn đúng 1 key trong "criteria" của câu hỏi đó.
- "score": chọn đúng 1 chỉ số (bắt đầu từ 0) trong danh sách "criteria".

Trả lời bằng DUY NHẤT 1 object JSON, key là id câu hỏi, value là câu trả lời
tương ứng (số cho noul/score, chuỗi key cho choice). Không thêm giải thích,
không thêm markdown.
"""


_TRUE = {"true", "yes", "có", "đúng"}
_FALSE = {"false", "no", "không", "sai"}


def _number(value: object) -> float | None:
    """Số trong câu trả lời: 0.8, "0.8", true/false (kể cả dạng chuỗi) -> 1.0/0.0.

    Đã gặp thật: gpt-oss trả `"answer": "false"` cho câu noul thay vì xác suất. Giá trị
    không hiểu được -> None (coi như model không trả lời câu đó), không đoán.
    """
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return 1.0
        if text in _FALSE:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _normalize(qtype: str, value: object) -> dict | None:
    if qtype in ("noul", "score"):
        number = _number(value)
        return None if number is None else {"type": qtype, qtype: number}
    return {"type": "choice", "choice": str(value)}


def _extract_json(raw: str) -> dict | None:
    """JSON thuần; nếu không được thì lấy object JSON đầu tiên trong văn bản (model
    suy luận hay bọc trong ```json hoặc kèm lời dẫn). Áp dụng như nhau cho mọi model."""
    candidates = [raw]
    start, end = raw.find("{"), raw.rfind("}")
    if 0 <= start < end:
        candidates.append(raw[start : end + 1])
    for text in candidates:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


class LLMClient:
    name = "llm"

    def __init__(self, model: str) -> None:
        self.model = model

    @property
    def model_name(self) -> str:
        return self.model

    async def decide(self, state: str, questions: dict) -> dict:
        base_url, api_key, name = resolve(self.model)
        provider = self.model.partition("/")[0]
        user_prompt = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
        body = {
            "model": name,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            **request_extras(provider),
        }

        # Ollama chạy local: lỗi 5xx là lỗi cố định (VD prompt vượt ngữ cảnh), gọi lại chỉ tốn
        # thêm vài phút. Chỉ API từ xa mới có lỗi tạm thời đáng thử lại.
        retryable = RETRY_STATUSES if provider != "ollama" else set()

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT, transport=_transport) as client:
            for attempt in range(RETRIES):
                try:
                    resp = await client.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                except httpx.TransportError:
                    if attempt == RETRIES - 1:
                        raise
                else:
                    if resp.status_code not in retryable or attempt == RETRIES - 1:
                        break
                await asyncio.sleep(_backoff * 2**attempt)
        latency_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        raw = choice["message"].get("content") or ""

        parsed = _extract_json(raw)
        if parsed is None:
            # gpt-oss có thể dùng hết max_tokens cho bước suy luận và để trống nội dung
            reason = f" (finish_reason={choice.get('finish_reason')})" if not raw else ""
            if choice.get("finish_reason") == "length" and provider == "ollama":
                reason += (" — hết ngữ cảnh: Ollama mặc định chỉ 4096 token, dùng biến thể 32K "
                           "(xem GUIDE.md)")
            raise RuntimeError(
                f"LLM ({self.model}) không trả JSON hợp lệ{reason}: {raw[:200]!r}"
            )

        answers = {}
        for qid, q in questions.items():
            if qid in parsed and (normalized := _normalize(q["type"], parsed[qid])) is not None:
                answers[qid] = normalized
        usage = data.get("usage") or {}
        usage["cost"] = 0.0  # không trả chi phí
        return {"answers": answers, "usage": usage, "latency_ms": latency_ms}
