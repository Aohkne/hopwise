"""Đọc Knowledge Graph từ Neo4j, và nhận tài liệu để trích xuất thêm vào graph (bản 2.0.0)."""

from __future__ import annotations

from pathlib import PurePath

from fastapi import APIRouter, HTTPException

from app.harness import jobs
from app.harness.pipeline import DEFAULT_DOMAIN
from app.models.schemas import DocumentRequest, GraphPayload, Neighbor, Node, SearchResult
from app.services import neo4j_client

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/domains/{domain}", response_model=GraphPayload)
def read_domain_graph(domain: str) -> GraphPayload:
    payload = neo4j_client.get_domain_graph(domain)
    if not payload["nodes"]:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' không có dữ liệu")
    return GraphPayload(**payload)


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


@router.post("/documents")
async def upload_document(request: DocumentRequest) -> dict:
    """Trích xuất Entity / Relationship / Claim từ văn bản rồi gộp vào graph của `domain`.
    Trả job ngay (chạy nền); xem tiến độ ở `GET /documents/{id}`."""
    name = PurePath(request.name).name or "document.txt"  # bỏ đường dẫn, chỉ giữ tên file
    try:
        return jobs.start_job(name, request.text, request.domain or DEFAULT_DOMAIN)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err


@router.get("/documents/{job_id}")
def read_document_job(job_id: str) -> dict:
    job = jobs.JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Không có lượt upload '{job_id}'")
    return job
