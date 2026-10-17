"""FastAPI entrypoint.

Chạy: uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import benchmark, graph, model

app = FastAPI(title="Hopwise API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # frontend dev (Vite)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router, prefix="/api/v1")
app.include_router(model.router, prefix="/api/v1")
app.include_router(benchmark.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
