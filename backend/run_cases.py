"""CLI: chạy cả bộ câu hỏi ground truth qua 3 model (Jev, Ollama, NVIDIA).

Chạy (cần Neo4j, Ollama đang chạy và key trong .env):
    cd backend
    uv run python run_cases.py                    # cả 60 câu
    uv run python run_cases.py --domain vinfast   # 1 domain
    uv run python run_cases.py --ids vinfast-001 football-003
    uv run python run_cases.py --summary          # chỉ in tổng hợp từ outputs/runs.csv

Các câu chạy lần lượt; mỗi câu ghi ngay vào outputs/runs.csv (xem được ở tab Lịch sử).
Dừng giữa chừng rồi chạy lại thì bỏ qua câu đã có đủ kết quả. Cuối cùng in bảng tổng
hợp và ghi outputs/summary.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from app.config import get_settings
from app.routers.benchmark import make_clients, make_graph
from app.services import batch, benchmark, ground_truth


def fmt_result(r: dict) -> str:
    mark = {"correct": "✓", "wrong": "✗"}.get(batch.outcome(r), batch.outcome(r))
    return f"{r['model']}={mark} {r['elapsed_ms'] / 1000:.0f}s"


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 78)
    print(f"{'model':8} {'đúng':>6} {'sai':>5} {'không ra':>9} {'quá giờ':>8} {'lỗi':>5} "
          f"{'trung vị (đúng)':>16}  phiên bản")
    for key, s in summary.items():
        g = s["groups"].get("all", dict.fromkeys(batch.OUTCOMES, 0))
        med = f"{s['median_correct_ms'] / 1000:.1f}s" if s["median_correct_ms"] else "—"
        print(f"{key:8} {g['correct']:>3}/{s['cases']:<2} {g['wrong']:>5} {g['not_found']:>9} "
              f"{g['timeout']:>8} {g['error']:>5} {med:>16}  {s['model_version'] or s['model_name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", choices=["football_vn", "vinfast"])
    parser.add_argument("--ids", nargs="+", help="chỉ chạy các câu này")
    parser.add_argument("--summary", action="store_true", help="không chạy, chỉ tổng hợp")
    args = parser.parse_args()

    settings = get_settings()
    cases = ground_truth.load_cases(settings.cases_dir)
    selected = [c for c in cases.values()
                if (not args.domain or c["domain"] == args.domain) and (not args.ids or c["id"] in args.ids)]

    if not args.summary:
        done = batch.completed_case_ids(settings.outputs_dir)
        todo = [c for c in selected if c["id"] not in done]
        print(f"{len(selected)} câu, {len(selected) - len(todo)} đã có kết quả, chạy {len(todo)} câu "
              f"| Ollama {settings.ollama_model} (suy luận: {settings.ollama_reasoning_effort or 'mặc định'}) "
              f"| BENCH_CHUNK={settings.bench_chunk} | {settings.bench_timeout_seconds:g}s/model", flush=True)
        started = time.perf_counter()

        def on_done(i: int, case: dict, run: dict) -> None:
            spent = (time.perf_counter() - started) / 60
            results = "  ".join(fmt_result(run["models"][k]) for k in benchmark.MODEL_KEYS)
            print(f"[{i:>2}/{len(selected)}] {case['id']:<13} {results}   ({spent:.0f} phút)", flush=True)

        asyncio.run(batch.run_cases(todo, make_clients, make_graph(), settings.bench_timeout_seconds,
                                    settings.outputs_dir, on_done))

    summary = batch.summarize(benchmark.list_history(settings.outputs_dir), {c["id"]: c for c in selected})
    print_summary(summary)
    out = settings.outputs_dir / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGhi {out}")


if __name__ == "__main__":
    main()
