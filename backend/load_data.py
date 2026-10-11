"""CLI: nạp data/*.json vào Neo4j.

Chạy (cần Neo4j đang chạy — `docker compose up -d` ở thư mục gốc):
    cd backend
    uv run python load_data.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from app.services.graph_loader import load_file

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    for path in sorted(DATA_DIR.glob("*.json")):
        print(f"Nạp {path.name}...")
        stats = load_file(path)
        print(f"  -> {stats['nodes']} node {stats['by_label']}")
        print(f"  -> {stats['edges']} cạnh {stats['by_edge_type']}")


if __name__ == "__main__":
    main()
