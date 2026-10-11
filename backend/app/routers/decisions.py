"""POST /decide — chạy traversal bằng 1 decision client cho 1 câu hỏi.

TODO: triển khai thật — xem TODO.md (phụ thuộc app/services/traversal.py
và app/services/decision_models/*.py, hiện vẫn là stub).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import DecideRequest, DecideResponse

router = APIRouter(prefix="/decide", tags=["decisions"])


@router.post("", response_model=DecideResponse)
def decide(request: DecideRequest) -> DecideResponse:
    raise HTTPException(status_code=501, detail="TODO: chưa triển khai — xem TODO.md")
