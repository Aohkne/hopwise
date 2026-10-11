"""Pydantic schema dùng chung cho các router.

Khớp với format node/edge trong data/*.json (xem data/README.md) và format
answers của TypeSafe System One (xem skills/typesafe-ai/SKILL.md).
"""

from __future__ import annotations

from pydantic import BaseModel


class Node(BaseModel):
    id: str
    label: str
    properties: dict


class Neighbor(BaseModel):
    edge_type: str
    edge_props: dict
    target_id: str
    target_label: str
    target_description: str | None = None


class DecideRequest(BaseModel):
    question: str
    start_node_id: str
    model: str  # "jev" | "kev" | tên LLM, ví dụ "openai/gpt-6-sol"


class DecideResponse(BaseModel):
    path: list[str]
    answer: str | None
    hops: int
    latency_ms: float
    usage: dict


class BenchmarkRunRequest(BaseModel):
    domain: str  # "football_vn" | "vinfast"
    models: list[str]


class BenchmarkRunResult(BaseModel):
    run_id: str
    status: str  # "pending" | "running" | "done" | "failed"
