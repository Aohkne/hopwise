"""POST /model/jev, /model/kev, /model/llm — gọi trực tiếp 1 decision model.

Mỗi endpoint nhận cùng schema {state, questions} (TypeSafe System One, xem
skills/typesafe-ai/SKILL.md) và trả về cùng shape {answers, usage, latency_ms}
— để 3 panel Jev/Kev/LLM ở frontend benchmark xử lý giống nhau.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import ModelRequest, ModelResponse
from app.services.decision_models.jev import JevClient
from app.services.decision_models.kev import KevClient
from app.services.decision_models.llm import LLMClient

router = APIRouter(prefix="/model", tags=["model"])


async def _call(client, request: ModelRequest) -> ModelResponse:
    try:
        result = await client.decide(request.state, request.questions)
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"{client.name} lỗi: {err}") from err
    return ModelResponse(**result)


@router.post("/jev", response_model=ModelResponse)
async def call_jev(request: ModelRequest) -> ModelResponse:
    return await _call(JevClient(), request)


@router.post("/kev", response_model=ModelResponse)
async def call_kev(request: ModelRequest) -> ModelResponse:
    return await _call(KevClient(), request)


@router.post("/llm", response_model=ModelResponse)
async def call_llm(request: ModelRequest) -> ModelResponse:
    if not request.model:
        raise HTTPException(status_code=422, detail="Thiếu `model` (ví dụ 'openai/gpt-6-sol')")
    return await _call(LLMClient(request.model), request)
