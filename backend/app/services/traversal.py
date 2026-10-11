"""Thuật toán traversal: tại mỗi node, hỏi 1 decision client (Jev/Kev/LLM)
xem nên đi theo cạnh nào tiếp theo để tìm thông tin trả lời câu hỏi.

TODO: triển khai thật — xem TODO.md. Các quyết định còn mở (tham khảo
TODO.md): điều kiện dừng khi nào đủ thông tin để trả lời, beam search
(BEAM_WIDTH trong config) khi greedy đi sai nhánh, giới hạn MAX_HOPS.
"""

from __future__ import annotations

from app.services.decision_models.base import DecisionClient


async def run_traversal(
    client: DecisionClient,
    question: str,
    start_node_id: str,
) -> dict:
    """Trả về đường đi đã đi qua, câu trả lời cuối, và usage/latency cộng dồn."""
    raise NotImplementedError("TODO: xem app/services/traversal.py và TODO.md")
