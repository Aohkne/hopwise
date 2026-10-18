"""Chạy hàng loạt bộ câu hỏi ground truth (benchmarks/cases/*.json) qua cả 3 model.

Mỗi câu = 1 lượt benchmark bình thường (3 model song song, 5 phút mỗi model, chấm
đúng/sai), các câu chạy LẦN LƯỢT: model local (Ollama) chỉ xử lý 1 yêu cầu một lúc,
chạy song song nhiều câu sẽ làm sai thời gian đo. Kết quả ghi vào cùng outputs/runs.csv
nên tab Lịch sử xem lại được từng câu. Chạy lại thì bỏ qua câu đã có đủ kết quả.
"""

from __future__ import annotations

import asyncio
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.services import benchmark
from app.services.search import Graph

OUTCOMES = ("correct", "wrong", "not_found", "timeout", "stopped", "error")


def completed_case_ids(outputs_dir: Path) -> set[str]:
    """Câu ground truth đã có kết quả của đủ mọi model trong outputs/runs.csv."""
    done = set()
    for run in benchmark.list_history(outputs_dir):
        if run.get("case_id") and set(benchmark.MODEL_KEYS) <= set(run["models"]):
            done.add(run["case_id"])
    return done


async def run_cases(cases: list[dict], make_clients: Callable[[], dict[str, Any]], graph: Graph,
                    timeout: float, outputs_dir: Path,
                    on_done: Callable[[int, dict, dict], None] | None = None) -> list[dict]:
    """Chạy lần lượt từng câu chưa có kết quả; trả về các lượt vừa chạy."""
    skip = completed_case_ids(outputs_dir)
    runs = []
    for i, case in enumerate(cases, 1):
        if case["id"] in skip:
            continue
        run = benchmark.start_run(case["question"], make_clients(), graph, timeout, outputs_dir, case)
        while run["status"] != "done":
            await asyncio.sleep(0.2)
        runs.append(run)
        if on_done:
            on_done(i, case, run)
    return runs


def outcome(result: dict) -> str:
    """found -> correct / wrong theo ground truth; các trạng thái khác giữ nguyên."""
    if result["status"] == "found":
        return "correct" if result.get("correct") else "wrong"
    return result["status"]


def summarize(runs: list[dict], cases: dict[str, dict]) -> dict[str, dict]:
    """Tổng hợp theo model: số câu theo kết quả (tất cả / theo domain / theo số bước) và
    thời gian trung vị của các lượt đúng. Mỗi câu chỉ tính lượt chạy mới nhất."""
    latest: dict[str, dict] = {}
    for run in sorted(runs, key=lambda r: r["started_at"]):
        if run.get("case_id") in cases:
            latest[run["case_id"]] = run

    summary: dict[str, dict] = {}
    for key in benchmark.MODEL_KEYS:
        rows = [(cases[cid], run["models"][key]) for cid, run in latest.items() if key in run["models"]]
        groups: dict[str, dict[str, int]] = {}
        for case, result in rows:
            for group in ("all", f"domain:{case['domain']}", f"hops:{case['hops']}"):
                counts = groups.setdefault(group, dict.fromkeys(OUTCOMES, 0))
                counts[outcome(result)] += 1
        correct_ms = [r["elapsed_ms"] for _, r in rows if outcome(r) == "correct"]
        by_hops = {}
        for h in (1, 2, 3):
            ms = [r["elapsed_ms"] for c, r in rows if c["hops"] == h and outcome(r) == "correct"]
            if ms:
                by_hops[h] = statistics.median(ms)
        summary[key] = {
            "model_name": rows[0][1]["model_name"] if rows else None,
            "model_version": next((r.get("model_version") for _, r in rows if r.get("model_version")), None),
            "cases": len(rows),
            "groups": groups,
            "median_correct_ms": statistics.median(correct_ms) if correct_ms else None,
            "median_correct_ms_by_hops": by_hops,
            "calls": sum(r.get("calls") or len(r.get("steps") or []) for _, r in rows),
            "tokens": sum(r.get("tokens") or 0 for _, r in rows),
            "cost": round(sum(r.get("cost") or 0.0 for _, r in rows), 6),
        }
    return summary
