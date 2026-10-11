"""Đọc Knowledge Graph từ Neo4j — đã triển khai, không phải stub."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import Neighbor, Node, SearchResult
from app.services import neo4j_client

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/search", response_model=list[SearchResult])
def search(q: str, limit: int = 20) -> list[SearchResult]:
    if not q.strip():
        return []
    return [SearchResult(**row) for row in neo4j_client.search_nodes(q, limit=limit)]


@router.get("/nodes/{node_id}", response_model=Node)
def read_node(node_id: str) -> Node:
    node = neo4j_client.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy node '{node_id}'")
    return Node(**node)


@router.get("/nodes/{node_id}/neighbors", response_model=list[Neighbor])
def read_neighbors(node_id: str) -> list[Neighbor]:
    return [Neighbor(**row) for row in neo4j_client.get_neighbors(node_id)]
