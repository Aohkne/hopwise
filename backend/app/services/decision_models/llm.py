"""Gọi LLM thông thường (OpenAI, Gemini, DeepSeek) làm baseline (System 2) để so
sánh với Jev (System 1) — gọi THẲNG API của từng hãng, không qua OpenRouter.

Model ghi dạng "<hãng>/<model>" (VD "google/gemini-3.8-flash"): phần hãng chọn
endpoint + API key, phần sau là tên model gửi cho hãng đó. Cả 3 hãng đều có
endpoint tương thích chuẩn OpenAI `/chat/completions`, nên dùng chung 1 client.
API của hãng không trả chi phí như OpenRouter, nên `cost` luôn là 0.

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

# hãng -> (base URL tương thích OpenAI, tên field API key trong Settings)
PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "openai_api_key"),
    "google": ("https://generativelanguage.googleapis.com/v1beta/openai", "google_api_key"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek_api_key"),
}

# Để test thay bằng httpx.MockTransport (không gọi mạng thật).
_transport: httpx.AsyncBaseTransport | None = None

# Lỗi tạm thời của hãng (quá tải, rate-limit) -> thử lại thay vì đánh lỗi cả lượt.
# Đã gặp thật: Gemini trả 503 giữa chừng dù 2 lần gọi trước thành công.
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRIES = 3
_backoff = 1.0  # giây, nhân đôi mỗi lần; test đặt về 0


def resolve(model: str) -> tuple[str, str, str]:
    """"google/gemini-3.8-flash" -> (base_url, api_key, "gemini-3.8-flash")."""
    provider, _, name = model.partition("/")
    if provider not in PROVIDERS or not name:
        raise RuntimeError(
            f"Model '{model}' không hợp lệ — cần dạng <hãng>/<model>, hãng ∈ {sorted(PROVIDERS)}"
        )
    base_url, key_field = PROVIDERS[provider]
    api_key = getattr(get_settings(), key_field)
    if not api_key:
        raise RuntimeError(f"Thiếu {key_field.upper()} trong .env (cho model {model})")
    return base_url, api_key, name


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


def _normalize(qtype: str, value: object) -> dict:
    if qtype == "noul":
        return {"type": "noul", "noul": float(value)}  # type: ignore[arg-type]
    if qtype == "score":
        return {"type": "score", "score": float(value)}  # type: ignore[arg-type]
    return {"type": "choice", "choice": str(value)}


class LLMClient:
    name = "llm"

    def __init__(self, model: str) -> None:
        self.model = model

    @property
    def model_name(self) -> str:
        return self.model

    async def decide(self, state: str, questions: dict) -> dict:
        base_url, api_key, name = resolve(self.model)
        user_prompt = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)

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
                        json={
                            "model": name,
                            "messages": [
                                {"role": "system", "content": _SYSTEM_PROMPT},
                                {"role": "user", "content": user_prompt},
                            ],
                            "response_format": {"type": "json_object"},
                        },
                    )
                except httpx.TransportError:
                    if attempt == RETRIES - 1:
                        raise
                else:
                    if resp.status_code not in RETRY_STATUSES or attempt == RETRIES - 1:
                        break
                await asyncio.sleep(_backoff * 2**attempt)
        latency_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"LLM ({self.model}) không trả JSON hợp lệ: {raw[:200]!r}") from err

        answers = {
            qid: _normalize(q["type"], parsed[qid])
            for qid, q in questions.items()
            if qid in parsed
        }
        usage = data.get("usage") or {}
        usage["cost"] = 0.0  # API hãng không trả chi phí
        return {"answers": answers, "usage": usage, "latency_ms": latency_ms}
