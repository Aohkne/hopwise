"""Benchmark: chạy Jev, Gemma (Ollama) và gpt-oss (NVIDIA) song song trên 1 câu hỏi, xem tiến độ, dừng,
và xem lại lịch sử (đọc từ CSV trong outputs/)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.services import benchmark, ground_truth
from app.services.decision_models.jev import JevClient
from app.services.decision_models.nvidia import NvidiaClient
from app.services.decision_models.ollama import OllamaClient, ollama_version
from app.services.search import Graph, Neo4jGraph

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


# Tách thành hàm để test thay bằng client/graph giả.
def make_clients() -> dict[str, Any]:
    return {"jev": JevClient(), "ollama": OllamaClient(), "nvidia": NvidiaClient()}


def make_graph() -> Graph:
    return Neo4jGraph()


class StartRunRequest(BaseModel):
    question: str = ""
    case_id: str | None = None  # câu ground truth: dùng câu hỏi của case và chấm đúng/sai


@router.get("/models")
async def models() -> dict:
    """Model của 3 card: Jev (theo cấu hình), Gemma local qua Ollama (hỏi Ollama; version
    None nếu chưa bật / chưa pull) và gpt-oss qua NVIDIA."""
    settings = get_settings()
    return {
        "jev": settings.jev_model,
        "ollama": {"model": settings.ollama_model or None, "version": await ollama_version()},
        "nvidia": {"model": settings.nvidia_model or None},
    }


@router.get("/cases")
def cases() -> list[dict]:
    """Bộ câu hỏi ground truth (id, domain, câu hỏi, số bước)."""
    return ground_truth.summarize(get_settings().cases_dir)


@router.post("/runs")
async def start(request: StartRunRequest) -> dict:
    case = None
    if request.case_id:
        case = ground_truth.load_cases(get_settings().cases_dir).get(request.case_id)
        if case is None:
            raise HTTPException(status_code=422, detail=f"Không có câu ground truth '{request.case_id}'")
    question = case["question"] if case else request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Câu hỏi trống")
    settings = get_settings()
    return benchmark.start_run(
        question, make_clients(), make_graph(),
        settings.bench_timeout_seconds, settings.outputs_dir, case,
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
