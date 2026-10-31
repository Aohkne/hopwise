"""POST/GET /api/v1/graph/documents — job nền, pipeline giả (không gọi LLM, không cần Neo4j)."""

import asyncio
import time

from fastapi.testclient import TestClient

from app.harness import jobs, pipeline
from app.main import app

client = TestClient(app)


def test_upload_runs_the_pipeline_in_the_background_and_exposes_the_report(monkeypatch) -> None:
    calls = []

    async def fake_ingest(name, text, *, domain, on_chunk=None, **kw):
        calls.append((name, text, domain))
        on_chunk(1, 2)
        await asyncio.sleep(0)
        on_chunk(2, 2)
        return {"entities": 3, "domain": domain}

    monkeypatch.setattr(pipeline, "ingest_document", fake_ingest)
    with TestClient(app) as c:  # giữ một event loop sống để job nền chạy tới cùng
        started = c.post("/api/v1/graph/documents", json={"name": "../../tb.md", "text": "VF3 giảm 30%"})
        assert started.status_code == 200
        job_id = started.json()["id"]
        assert started.json()["domain"] == "vinfast_policy" and started.json()["status"] == "running"

        final = None
        for _ in range(50):
            final = c.get(f"/api/v1/graph/documents/{job_id}").json()
            if final["status"] != "running":
                break
            time.sleep(0.02)
    assert calls == [("tb.md", "VF3 giảm 30%", "vinfast_policy")]  # đường dẫn bị bỏ
    assert final["status"] == "done" and final["report"] == {"entities": 3, "domain": "vinfast_policy"}
    assert (final["done_chunks"], final["total_chunks"]) == (2, 2)


def test_pipeline_failure_is_reported_on_the_job(monkeypatch) -> None:
    async def boom(*a, **kw):
        raise RuntimeError("Thiếu NVIDIA_API_KEY trong .env")

    monkeypatch.setattr(pipeline, "ingest_document", boom)
    with TestClient(app) as c:
        job_id = c.post("/api/v1/graph/documents", json={"name": "a.md", "text": "x"}).json()["id"]
        for _ in range(50):
            job = c.get(f"/api/v1/graph/documents/{job_id}").json()
            if job["status"] != "running":
                break
            time.sleep(0.02)
    assert job["status"] == "error" and "NVIDIA_API_KEY" in job["error"]


def test_bad_requests_are_rejected_before_any_job_starts() -> None:
    before = len(jobs.JOBS)
    for body in (
        {"name": "a.md", "text": "   "},
        {"name": "a.md", "text": "x", "domain": "../etc"},
        {"name": "a.md", "text": "x" * (jobs.MAX_DOCUMENT_CHARS + 1)},
    ):
        assert client.post("/api/v1/graph/documents", json=body).status_code == 422
    assert len(jobs.JOBS) == before


def test_unknown_job_is_404() -> None:
    assert client.get("/api/v1/graph/documents/nope").status_code == 404
