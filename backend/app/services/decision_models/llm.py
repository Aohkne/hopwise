"""Gọi LLM thông thường (GPT, Claude, Gemini qua OpenRouter /chat/completions)
làm baseline (System 2) để so sánh với Jev/Kev (System 1).

Khác biệt so với jev.py/kev.py: LLM không hiểu sẵn schema `{state, questions}`
của TypeSafe System One, nên phải tự convert `questions` thành 1 prompt tự
nhiên yêu cầu trả lời bằng JSON, rồi tự parse ngược lại. Không bịa thêm
`probabilities`/`confidence` như Jev/Kev trả về — một LLM thường không tính
ra con số đó, bịa ra sẽ gây hiểu nhầm khi so sánh.
"""

from __future__ import annotations

import json
import time

import httpx

from app.config import get_settings

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

    async def decide(self, state: str, questions: dict) -> dict:
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise RuntimeError("Thiếu OPENROUTER_API_KEY trong .env")

        user_prompt = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
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
        return {"answers": answers, "usage": data.get("usage", {}), "latency_ms": latency_ms}
