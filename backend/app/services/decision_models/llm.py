"""Gọi LLM thông thường (GPT, Claude, Gemini qua OpenRouter /chat/completions)
làm baseline (System 2) để so sánh với Jev/Kev (System 1).

Khác biệt so với jev.py/kev.py: LLM không hiểu schema `{state, questions}`
có sẵn, nên phải tự convert `questions` thành 1 prompt tự nhiên và tự parse
câu trả lời (thường ở dạng JSON do model trả về) ngược lại thành cùng cấu
trúc answers để traversal.py đối xử như nhau với cả 3 client.

TODO: triển khai thật — xem TODO.md.
"""

from __future__ import annotations

from app.config import get_settings


class LLMClient:
    name = "llm"

    def __init__(self, model: str) -> None:
        self.model = model

    async def decide(self, state: str, questions: dict) -> dict:
        get_settings()  # giữ tham chiếu settings cho khi triển khai thật
        raise NotImplementedError(
            f"TODO: convert `questions` thành prompt, gọi {self.model} qua "
            "/chat/completions, parse JSON trả lời thành cùng cấu trúc answers "
            "với jev.py/kev.py"
        )
