"""Interface chung cho mọi "decision client" (Jev, Kev, LLM thường).

Mỗi implementation nhận vào `state` (ngữ cảnh node hiện tại + câu hỏi gốc)
và `questions` (dict các câu hỏi Choice/Score/Noul theo đúng format của
TypeSafe System One — xem skills/typesafe-ai/SKILL.md), trả về dict answers
cùng cấu trúc, để `traversal.py` dùng chung một code path cho cả 3 bên khi
benchmark.
"""

from __future__ import annotations

from typing import Protocol


class DecisionClient(Protocol):
    name: str

    async def decide(self, state: str, questions: dict) -> dict:
        """Trả về `{"answers": {...}, "usage": {...}, "latency_ms": ...}`."""
        ...
