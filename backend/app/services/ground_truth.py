"""Đọc bộ câu hỏi ground truth (benchmarks/cases/*.json, sinh bởi
benchmarks/generate_cases.py) để chấm đúng/sai các lượt benchmark."""

from __future__ import annotations

import json
from pathlib import Path


def load_cases(cases_dir: Path) -> dict[str, dict]:
    """id câu -> case (kèm `domain`). Thư mục chưa có thì trả rỗng."""
    cases: dict[str, dict] = {}
    for path in sorted(cases_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for case in doc.get("cases", []):
            cases[case["id"]] = {**case, "domain": doc["domain"]}
    return cases


def summarize(cases_dir: Path) -> list[dict]:
    """Danh sách gọn cho dropdown ở frontend (không lộ đáp án)."""
    return [
        {"id": c["id"], "domain": c["domain"], "question": c["question"], "hops": c["hops"]}
        for c in load_cases(cases_dir).values()
    ]
