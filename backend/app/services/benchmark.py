"""Chạy 1 lượt benchmark: 2 model (Jev, LLM) song song trên cùng câu hỏi.

- Mỗi model bị giới hạn `bench_timeout_seconds` (5 phút) bằng asyncio.wait_for —
  cắt được cả giữa một lần gọi API đang treo.
- Tiến độ ghi thẳng vào dict của lượt chạy để frontend poll xem trực tiếp.
- Chạy xong ghi CSV vào `outputs/`: runs.csv (mỗi model 1 dòng) và
  run_<id>_trace.csv (từng bước) — tab Lịch sử đọc lại chính các file này.
"""

from __future__ import annotations

import asyncio
import csv
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.search import Graph, find_answer

MODEL_KEYS = ("jev", "llm")

RUN_COLUMNS = [
    "run_id", "started_at", "question", "model", "model_name", "model_version", "status",
    "answer_node_id", "answer_text", "elapsed_ms", "calls", "tokens", "cost",
    "domain", "label", "error",
]
TRACE_COLUMNS = [
    "run_id", "model", "step", "phase", "decision", "node_id", "node_label",
    "node_caption", "from_node_id", "via_edge", "answer_score", "latency_ms",
    "tokens", "cost", "candidates",
]

# run_id -> run dict (lượt đang chạy / vừa chạy trong phiên backend này)
RUNS: dict[str, dict] = {}
# run_id -> {model_key: asyncio.Task}, để dừng được
_TASKS: dict[str, dict[str, asyncio.Task]] = {}
# giữ tham chiếu task điều phối, tránh bị GC giữa chừng
_ORCHESTRATORS: set[asyncio.Task] = set()


def _empty_result(key: str, model_name: str) -> dict:
    return {
        "model": key, "model_name": model_name, "model_version": None, "status": "running",
        "answer_node_id": None, "answer_text": None, "error": None,
        "elapsed_ms": 0.0, "tokens": 0, "cost": 0.0,
        "domain": None, "label": None, "steps": [],
    }


async def _run_one(run: dict, key: str, client: Any, graph: Graph, timeout: float) -> None:
    result = run["models"][key]
    started = time.perf_counter()
    try:
        await asyncio.wait_for(find_answer(client, run["question"], graph, result), timeout)
    except TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"quá {timeout:g}s"
    except asyncio.CancelledError:
        # Do người dùng bấm Dừng (stop_run huỷ task này) — ghi nhận, không ném tiếp
        # để lượt chạy vẫn kết thúc bình thường và ghi CSV.
        result["status"] = "stopped"
    # Cố ý bắt rộng: lỗi của 1 model (mạng, API, thiếu key...) không được làm
    # sập 2 model còn lại — ghi thành status "error" của riêng model đó.
    except Exception as err:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = str(err) or type(err).__name__
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)


async def _orchestrate(run: dict, clients: dict[str, Any], graph: Graph, timeout: float,
                       outputs_dir: Path) -> None:
    tasks = {
        key: asyncio.create_task(_run_one(run, key, clients[key], graph, timeout))
        for key in MODEL_KEYS
    }
    _TASKS[run["id"]] = tasks
    await asyncio.gather(*tasks.values())
    run["status"] = "done"
    _TASKS.pop(run["id"], None)
    write_csv(run, outputs_dir)


def start_run(question: str, llm_model: str, clients: dict[str, Any], graph: Graph,
              timeout: float, outputs_dir: Path) -> dict:
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    names = {"jev": clients["jev"].model_name, "llm": llm_model}
    run = {
        "id": run_id,
        "question": question,
        "llm_model": llm_model,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "running",
        "models": {key: _empty_result(key, names[key]) for key in MODEL_KEYS},
    }
    RUNS[run_id] = run
    task = asyncio.create_task(_orchestrate(run, clients, graph, timeout, outputs_dir))
    _ORCHESTRATORS.add(task)
    task.add_done_callback(_ORCHESTRATORS.discard)
    return run


def stop_run(run_id: str) -> bool:
    tasks = _TASKS.get(run_id)
    if not tasks:
        return False
    for task in tasks.values():
        task.cancel()
    return True


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #

def write_csv(run: dict, outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    runs_file = outputs_dir / "runs.csv"
    _migrate_header(runs_file)
    new = not runs_file.exists()
    with runs_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_COLUMNS)
        if new:
            writer.writeheader()
        for key in MODEL_KEYS:
            r = run["models"][key]
            writer.writerow({
                "run_id": run["id"], "started_at": run["started_at"], "question": run["question"],
                "model": key, "model_name": r["model_name"],
                "model_version": r.get("model_version") or "", "status": r["status"],
                "answer_node_id": r["answer_node_id"] or "", "answer_text": r["answer_text"] or "",
                "elapsed_ms": r["elapsed_ms"], "calls": len(r["steps"]), "tokens": r["tokens"],
                "cost": r["cost"], "domain": r["domain"] or "", "label": r["label"] or "",
                "error": r["error"] or "",
            })
    with (outputs_dir / f"run_{run['id']}_trace.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for key in MODEL_KEYS:
            for step in run["models"][key]["steps"]:
                writer.writerow({"run_id": run["id"], "model": key,
                                 **{c: step.get(c, "") for c in TRACE_COLUMNS[2:]}})


def _migrate_header(runs_file: Path) -> None:
    """runs.csv cũ thiếu cột mới (VD model_version) -> ghi lại với header mới, nếu
    không các dòng append sau sẽ lệch cột so với header cũ."""
    if not runs_file.exists():
        return
    with runs_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == RUN_COLUMNS:
            return
        rows = list(reader)
    with runs_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c) or "" for c in RUN_COLUMNS})


def _num(value: str, cast: Callable = float) -> Any:
    if value in ("", None):
        return None
    try:
        return cast(value)
    except ValueError:
        return None


def list_history(outputs_dir: Path) -> list[dict]:
    """Các lượt đã chạy (mới nhất trước), gom từ runs.csv."""
    runs_file = outputs_dir / "runs.csv"
    if not runs_file.exists():
        return []
    grouped: dict[str, dict] = {}
    with runs_file.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["model"] not in MODEL_KEYS:
                continue  # dòng của model đã bỏ (VD Kev trong các lượt chạy cũ)
            run = grouped.setdefault(row["run_id"], {
                "id": row["run_id"], "question": row["question"],
                "started_at": row["started_at"], "models": {},
            })
            run["models"][row["model"]] = {
                "model": row["model"], "model_name": row["model_name"],
                "model_version": row.get("model_version") or None, "status": row["status"],
                "answer_node_id": row["answer_node_id"] or None,
                "answer_text": row["answer_text"] or None, "error": row["error"] or None,
                "elapsed_ms": _num(row["elapsed_ms"]) or 0.0, "tokens": _num(row["tokens"], int) or 0,
                "cost": _num(row["cost"]) or 0.0, "domain": row["domain"] or None,
                "label": row["label"] or None, "calls": _num(row["calls"], int) or 0,
            }
    return sorted(grouped.values(), key=lambda r: r["started_at"], reverse=True)


def load_run(run_id: str, outputs_dir: Path) -> dict | None:
    """1 lượt đã chạy, kèm trace từng bước — đọc lại từ CSV."""
    run = next((r for r in list_history(outputs_dir) if r["id"] == run_id), None)
    if run is None:
        return None
    for result in run["models"].values():
        result["steps"] = []
    trace_file = outputs_dir / f"run_{run_id}_trace.csv"
    if trace_file.exists():
        with trace_file.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                result = run["models"].get(row["model"])
                if result is None:
                    continue
                result["steps"].append({
                    "step": _num(row["step"], int), "phase": row["phase"],
                    "decision": row["decision"] or None, "node_id": row["node_id"] or None,
                    "node_label": row["node_label"] or None,
                    "node_caption": row["node_caption"] or None,
                    "from_node_id": row["from_node_id"] or None, "via_edge": row["via_edge"] or None,
                    "answer_score": _num(row["answer_score"]), "latency_ms": _num(row["latency_ms"]),
                    "tokens": _num(row["tokens"], int), "cost": _num(row["cost"]),
                    "candidates": _num(row["candidates"], int),
                })
    run["status"] = "done"
    return run
