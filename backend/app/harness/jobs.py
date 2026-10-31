"""Job nền cho upload tài liệu: trích xuất mất vài chục giây tới vài phút nên API trả `id` ngay,
frontend poll `GET /graph/documents/{id}` (cùng mẫu với benchmark.RUNS)."""

from __future__ import annotations

import asyncio
import uuid

from app.harness import pipeline

MAX_DOCUMENT_CHARS = 200_000  # chặn tài liệu quá lớn: mỗi 3.000 ký tự là một lần gọi LLM tốn tiền

# job_id -> job (chỉ trong phiên backend này; kết quả thật nằm ở data/<domain>.json và Neo4j)
JOBS: dict[str, dict] = {}
_RUNNING: set[asyncio.Task] = set()  # giữ tham chiếu để task không bị GC giữa chừng


def start_job(name: str, text: str, domain: str) -> dict:
    """Chạy `pipeline.ingest_document` ở nền. Ném ValueError nếu domain/văn bản không hợp lệ."""
    pipeline.check_domain(domain)
    if not text.strip():
        raise ValueError("Văn bản trống")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise ValueError(f"Văn bản quá dài ({len(text):,} ký tự, tối đa {MAX_DOCUMENT_CHARS:,})")

    job = {"id": uuid.uuid4().hex[:12], "name": name, "domain": domain, "status": "running",
           "done_chunks": 0, "total_chunks": 0, "report": None, "error": None}
    JOBS[job["id"]] = job

    def progress(done: int, total: int) -> None:
        job["done_chunks"], job["total_chunks"] = done, total

    async def run() -> None:
        try:
            job["report"] = await pipeline.ingest_document(name, text, domain=domain, on_chunk=progress)
            job["status"] = "done"
        # Cố ý bắt rộng: mọi lỗi (thiếu key, hết credit, Neo4j tắt...) phải hiện ở job, không mất im lặng.
        except Exception as err:  # noqa: BLE001
            job["status"], job["error"] = "error", str(err) or type(err).__name__

    task = asyncio.create_task(run())
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)
    return job
