"""Benchmark: chạy Jev/LLM song song trên 1 câu hỏi, xem tiến độ, dừng,
và xem lại lịch sử (đọc từ CSV trong outputs/)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.services import benchmark
from app.services.decision_models.jev import JevClient
from app.services.decision_models.llm import LLMClient
from app.services.search import Graph, Neo4jGraph

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


def baseline_models() -> list[str]:
    raw = get_settings().baseline_models
    return [m.strip() for m in raw.split(",") if m.strip()]


# Tách thành hàm để test thay bằng client/graph giả.
def make_clients(llm_model: str) -> dict[str, Any]:
    return {"jev": JevClient(), "llm": LLMClient(llm_model)}


def make_graph() -> Graph:
    return Neo4jGraph()


class StartRunRequest(BaseModel):
    question: str
    llm_model: str | None = None


@router.get("/models")
async def models() -> dict:
    """Model đang dùng: LLM bật trong BASELINE_MODELS và phiên bản Jev (theo cấu hình)."""
    settings = get_settings()
    return {
        "llm": baseline_models(),
        "jev": settings.jev_model,
    }


@router.post("/runs")
async def start(request: StartRunRequest) -> dict:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Câu hỏi trống")
    allowed = baseline_models()
    llm_model = request.llm_model or (allowed[0] if allowed else "")
    if not llm_model:
        raise HTTPException(status_code=422, detail="Chưa cấu hình BASELINE_MODELS")
    settings = get_settings()
    return benchmark.start_run(
        question, llm_model, make_clients(llm_model), make_graph(),
        settings.bench_timeout_seconds, settings.outputs_dir,
    )


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = benchmark.RUNS.get(run_id) or benchmark.load_run(run_id, get_settings().outputs_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Không có lượt chạy '{run_id}'")
    return run


@router.post("/runs/{run_id}/stop")
def stop(run_id: str) -> dict:
    if not benchmark.stop_run(run_id):
        raise HTTPException(status_code=404, detail="Lượt chạy không còn đang chạy")
    return {"stopped": run_id}


@router.get("/history")
def history() -> list[dict]:
    return benchmark.list_history(get_settings().outputs_dir)
