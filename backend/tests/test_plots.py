"""Chuẩn bị dữ liệu cho biểu đồ benchmark (benchmarks/plot_results.py) — chỉ phần tính toán,
không biên dịch TikZ."""

from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks"))

import plot_results as pr

FIELDS = ["run_id", "started_at", "question", "case_id", "expected_answers", "model", "model_name",
          "model_version", "status", "answer_node_id", "answer_text", "correct", "elapsed_ms", "calls",
          "tokens", "cost", "domain", "label", "error"]


def write_runs(path, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def row(run, case, model, status, correct="", elapsed=1000, cost=0, when="2026-10-18T00:00:00"):
    return {"run_id": run, "started_at": when, "case_id": case, "model": model, "status": status,
            "correct": correct, "elapsed_ms": elapsed, "cost": cost}


def test_case_x_places_vinfast_after_football() -> None:
    assert pr.case_x("football-007") == 7 and pr.case_x("football-030") == 30
    assert pr.case_x("vinfast-001") == 31 and pr.case_x("vinfast-030") == 60


def test_correct_on_the_line_wrong_below_not_found_above(tmp_path) -> None:
    runs = tmp_path / "runs.csv"
    write_runs(runs, [
        row("r1", "football-001", "ollama", "found", "true"),      # đúng -> trên đường chéo
        row("r2", "football-002", "ollama", "found", "false"),     # sai -> lệch xuống dưới
        row("r3", "football-003", "ollama", "not_found"),          # không tìm thấy -> lệch lên trên
        row("r4", "football-004", "ollama", "timeout"),            # quá giờ cũng là không tìm thấy
        row("r5", "football-005", "ollama", "error"),              # lỗi -> không có chấm
        row("r6", "vinfast-001", "ollama", "found", "true"),
    ])
    points = pr.dots(pr.load_runs(runs), "ollama")
    assert points == [(1, 1), (2, 2 - pr.MISS), (3, 3 + pr.MISS), (4, 4 + pr.MISS), (31, 31)]


def test_three_models_are_separated_along_the_diagonal_not_off_it(tmp_path) -> None:
    runs = tmp_path / "runs.csv"
    write_runs(runs, [row("r1", "football-007", m, "found", "true") for m in ("jev", "ollama", "nvidia")])
    cases = pr.load_runs(runs)
    for model in ("jev", "ollama", "nvidia"):
        (x, y), = pr.dots(cases, model)
        assert x == y                                  # vẫn nằm đúng trên đường chéo
    assert len({pr.dots(cases, m)[0][0] for m in ("jev", "ollama", "nvidia")}) == 3  # nhưng không đè nhau


def test_errors_are_counted_but_never_drawn(tmp_path) -> None:
    runs = tmp_path / "runs.csv"
    write_runs(runs, [row("r1", "football-001", "nvidia", "found", "true"), row("r2", "football-002", "nvidia", "error")])
    cases = pr.load_runs(runs)
    assert len(pr.dots(cases, "nvidia")) == 1
    assert pr.averages(cases, "nvidia")["errors"] == 1


def test_averages_use_only_runs_that_reached_a_conclusion_and_latest_run_per_case(tmp_path) -> None:
    runs = tmp_path / "runs.csv"
    write_runs(runs, [
        row("old", "vinfast-001", "jev", "found", "false", elapsed=99000, when="2026-10-18T00:00:00"),
        row("new", "vinfast-001", "jev", "found", "true", elapsed=4000, cost=0.002, when="2026-10-18T01:00:00"),
        row("r2", "vinfast-002", "jev", "found", "false", elapsed=6000, cost=0.004),
        row("r3", "vinfast-003", "jev", "timeout", elapsed=300000, cost=0.006),  # không tính vào thời gian
    ])
    a = pr.averages(pr.load_runs(runs), "jev")
    assert a["n_answered"] == 2 and a["mean_time_s"] == 5.0          # (4 + 6) / 2; lượt cũ bị bỏ
    assert abs(a["mean_cost"] - 0.004) < 1e-9                        # trung bình trên cả 3 câu
    assert a["correct"] == 1 and a["total"] == 3


def test_tradeoff_rows_scale_each_metric_to_the_best_model(tmp_path) -> None:
    runs = tmp_path / "runs.csv"
    write_runs(runs, [
        row("r1", "football-001", "jev", "found", "true", elapsed=5000, cost=0.002),
        row("r1", "football-001", "ollama", "found", "false", elapsed=50000, cost=0),
        row("r1", "football-001", "nvidia", "found", "true", elapsed=100000, cost=0),
    ])
    acc, time, cost = pr.tradeoff_rows(pr.load_runs(runs))
    assert acc["norm"] == {"jev": 1.0, "ollama": 0.0, "nvidia": 1.0}   # 1/1, 0/1, 1/1 -> so với cao nhất
    assert time["norm"]["nvidia"] == 1.0 and time["norm"]["jev"] == 0.05
    assert cost["norm"] == {"jev": 1.0, "ollama": 0.0, "nvidia": 0.0}
    assert cost["text"]["ollama"] == "\\$0" and time["text"]["jev"] == "5,0\\,s"


def test_generated_tex_has_a_diagonal_reference_and_grouped_bars(tmp_path) -> None:
    runs = tmp_path / "runs.csv"
    write_runs(runs, [row("r1", "football-001", m, "error" if m == "nvidia" else "found", "true")
                      for m in ("jev", "ollama", "nvidia")])
    cases = pr.load_runs(runs)
    outcomes, bars = pr.outcomes_tex(cases), pr.latency_tex(cases)
    assert "coordinates {(0,0) (1,1)}" in outcomes           # đường chéo "đáp án đúng"
    for name in ("Jev", "Gemma 4 12B", "gpt-oss-20b"):
        assert name in outcomes and name in bars
    assert "jevblue" in outcomes and "gemmared" in outcomes and "gptyellow" in outcomes
    assert "hide y axis" in outcomes and "xtick={1,20,40,60}" in outcomes
    assert "Sai" not in outcomes and "Không tìm" not in outcomes   # không chú thích trên biểu đồ
    assert bars.count("ybar") >= 3 and bars.count("\\addplot+[ybar") == 3   # 3 chỉ số = 3 cột mỗi model
