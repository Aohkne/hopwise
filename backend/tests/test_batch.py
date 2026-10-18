"""Chạy hàng loạt ground truth: client/graph giả, không gọi mạng, không cần Neo4j."""

from __future__ import annotations

import asyncio

from app.services import batch, benchmark
from tests.test_search import FakeGraph, NeverAnswersClient, SmartClient

CASES = [
    {"id": "vinfast-001", "domain": "vinfast", "question": "Xe VF8 của công ty nào?",
     "answers": ["vinfast"], "hops": 1},
    {"id": "vinfast-002", "domain": "vinfast", "question": "Xe VF8 của công ty nào? (sai đáp án)",
     "answers": ["vingroup"], "hops": 2},
]


def smart_clients():
    return {k: SmartClient() for k in benchmark.MODEL_KEYS}


def test_runs_every_case_in_turn_and_grades_it(tmp_path) -> None:
    seen = []
    runs = asyncio.run(batch.run_cases(CASES, smart_clients, FakeGraph(), 5, tmp_path,
                                       lambda i, case, run: seen.append((i, case["id"]))))
    assert seen == [(1, "vinfast-001"), (2, "vinfast-002")]
    assert [r["case_id"] for r in runs] == ["vinfast-001", "vinfast-002"]
    assert {r["correct"] for r in runs[0]["models"].values()} == {True}
    assert {r["correct"] for r in runs[1]["models"].values()} == {False}
    assert batch.completed_case_ids(tmp_path) == {"vinfast-001", "vinfast-002"}


def test_rerun_skips_cases_that_already_have_results(tmp_path) -> None:
    asyncio.run(batch.run_cases(CASES[:1], smart_clients, FakeGraph(), 5, tmp_path))
    runs = asyncio.run(batch.run_cases(CASES, smart_clients, FakeGraph(), 5, tmp_path))
    assert [r["case_id"] for r in runs] == ["vinfast-002"]  # vinfast-001 đã có, không chạy lại


def test_summary_counts_outcomes_by_group_and_median_time(tmp_path) -> None:
    def mixed():
        return {"jev": SmartClient(), "ollama": NeverAnswersClient(), "nvidia": SmartClient()}

    asyncio.run(batch.run_cases(CASES, mixed, FakeGraph(), 5, tmp_path))
    summary = batch.summarize(benchmark.list_history(tmp_path), {c["id"]: c for c in CASES})

    jev = summary["jev"]
    assert jev["cases"] == 2
    assert jev["groups"]["all"]["correct"] == 1 and jev["groups"]["all"]["wrong"] == 1
    assert jev["groups"]["hops:1"]["correct"] == 1 and jev["groups"]["hops:2"]["wrong"] == 1
    assert jev["groups"]["domain:vinfast"]["correct"] == 1
    assert jev["median_correct_ms"] is not None and set(jev["median_correct_ms_by_hops"]) == {1}
    assert jev["model_version"] == "fake-smart-v1"
    # model không bao giờ kết luận -> "không tìm ra", không phải "sai"
    assert summary["ollama"]["groups"]["all"]["not_found"] == 2
    assert summary["ollama"]["median_correct_ms"] is None


def test_summary_uses_the_latest_run_of_each_case(tmp_path) -> None:
    def lost():
        return {k: NeverAnswersClient() for k in benchmark.MODEL_KEYS}

    asyncio.run(batch.run_cases(CASES[:1], lost, FakeGraph(), 5, tmp_path))
    # chạy lại thủ công (bỏ qua cơ chế skip) với client đúng -> lượt mới nhất được tính
    asyncio.run(batch.run_cases(CASES[:1], smart_clients, FakeGraph(), 5, tmp_path / "x"))
    rows = benchmark.list_history(tmp_path) + benchmark.list_history(tmp_path / "x")
    summary = batch.summarize(rows, {c["id"]: c for c in CASES})
    assert summary["jev"]["cases"] == 1 and summary["jev"]["groups"]["all"]["correct"] == 1
