"""Pydantic schema dùng chung cho các router.

Khớp với format node/edge trong data/*.json (xem data/README.md) và format
answers của TypeSafe System One (xem skills/typesafe-ai/SKILL.md).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Node(BaseModel):
    id: str
    label: str
    properties: dict


class SearchResult(BaseModel):
    id: str
    label: str
    description: str | None = None


class Neighbor(BaseModel):
    edge_type: str
    edge_props: dict
    target_id: str
    target_label: str
    target_description: str | None = None


class ModelRequest(BaseModel):
    """Request chung cho /model/jev, /model/kev, /model/llm — khớp schema
    TypeSafe System One (state + questions), xem skills/typesafe-ai/SKILL.md.
    """

    state: str
    questions: dict[str, Any]
    model: str | None = None  # chỉ /model/llm dùng, chọn model LLM cụ thể


class ModelResponse(BaseModel):
    answers: dict[str, Any]
    usage: dict[str, Any] = {}
    latency_ms: float
