"""POST /benchmark/run, GET /benchmark/{run_id} — chạy và theo dõi benchmark
nhiều model (Jev/Kev/LLM) trên cùng bộ test-case.

TODO: triển khai thật — xem TODO.md (phụ thuộc bộ test-case ground truth,
hiện chưa có — xem TODO.md).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import BenchmarkRunRequest, BenchmarkRunResult

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.post("/run", response_model=BenchmarkRunResult)
def run_benchmark(request: BenchmarkRunRequest) -> BenchmarkRunResult:
    raise HTTPException(status_code=501, detail="TODO: chưa triển khai — xem TODO.md")


@router.get("/{run_id}", response_model=BenchmarkRunResult)
def get_benchmark(run_id: str) -> BenchmarkRunResult:
    raise HTTPException(status_code=501, detail="TODO: chưa triển khai — xem TODO.md")
