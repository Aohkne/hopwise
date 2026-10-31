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


class GraphNode(BaseModel):
    id: str
    label: str
    caption: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Neighbor(BaseModel):
    edge_type: str
    edge_props: dict
    target_id: str
    target_label: str
    target_description: str | None = None
    direction: str = "out"  # "out" | "in", xem neo4j_client.get_neighbors


class ModelRequest(BaseModel):
    """Request chung cho /model/jev, /model/llm — khớp schema
    TypeSafe System One (state + questions), xem skills/typesafe-ai/SKILL.md.
    """

    state: str
    questions: dict[str, Any]
    model: str | None = None  # chỉ /model/llm dùng, chọn model LLM cụ thể


class ModelResponse(BaseModel):
    answers: dict[str, Any]
    usage: dict[str, Any] = {}
    latency_ms: float


class DocumentRequest(BaseModel):
    """Tài liệu văn bản để trích xuất vào graph (POST /graph/documents)."""

    name: str  # tên file, dùng làm nguồn (`source_docs`) của mọi node/cạnh trích xuất được
    text: str
    domain: str | None = None  # mặc định vinfast_policy, xem harness.pipeline.DEFAULT_DOMAIN
