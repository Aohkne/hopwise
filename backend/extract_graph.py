"""CLI: văn bản -> Knowledge Graph (bản 2.0.0). Trích xuất Entity / Relationship / Claim bằng LLM,
gộp vào data/<domain>.json rồi nạp Neo4j.

Chạy (cần key trong .env; nạp Neo4j cần `docker compose up -d` ở thư mục gốc):
    cd backend
    uv run python extract_graph.py ../docs/research/samples/data/sample.txt
    uv run python extract_graph.py văn_bản.md --domain vinfast_policy --provider ollama
    uv run python extract_graph.py văn_bản.md --no-load           # chỉ ghi JSON, không nạp Neo4j

Dựng lại từ output đã có, không gọi LLM (VD output thô trong outputs/extract/ hoặc mẫu nghiên cứu):
    uv run python extract_graph.py ../docs/research/samples/data/sample.txt \\
        --from-raw ../docs/research/samples/output/sample.md

Chạy nhiều tài liệu vào cùng một domain thì graph được gộp (cùng tên entity -> cùng node).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from app.harness.build_graph import doc_id_of
from app.harness.pipeline import DEFAULT_DOMAIN, ingest_document, make_extractor


def load_raw(path: pathlib.Path, doc_name: str) -> dict[str, str]:
    """`.json` = {chunk_id: output} (file trong outputs/extract/); file khác = một output duy nhất."""
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return {f"{doc_id_of(doc_name)}_c001": path.read_text(encoding="utf-8")}


def print_report(report: dict) -> None:
    graph = report["graph"]
    print(f"\n{report['doc']} -> domain {report['domain']} ({report['file']})")
    print(f"  trích xuất: {report['entities']} entity, {report['relationships']} relationship, "
          f"{report['claims']} claim từ {report['chunks']} chunk ({report.get('tokens', 0)} token)")
    print(f"  graph hiện tại: {graph['nodes']} node {graph['by_label']}")
    print(f"                  {graph['edges']} cạnh {graph['by_edge_type']}")
    for label, items in (("lỗi chunk", report["errors"]), ("chunk bị cắt cụt (hết max_tokens)", report["truncated_chunks"]),
                         ("record bị bỏ", report["skipped"])):
        if items:
            print(f"  ⚠ {label}: {len(items)}")
            for item in items[:10]:
                print(f"      - {item}")
    if "loaded" in report:
        print(f"  đã nạp Neo4j: {report['loaded']['nodes']} node, {report['loaded']['edges']} cạnh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=pathlib.Path, help="văn bản nguồn (.txt / .md)")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--provider", choices=["nvidia", "ollama"], help="mặc định EXTRACT_PROVIDER")
    parser.add_argument("--from-raw", type=pathlib.Path, help="dựng từ output có sẵn, không gọi LLM")
    parser.add_argument("--no-load", action="store_true", help="chỉ ghi data/<domain>.json")
    args = parser.parse_args()

    text = args.file.read_text(encoding="utf-8")
    raw = load_raw(args.from_raw, args.file.name) if args.from_raw else None
    client = None if raw is not None else make_extractor(args.provider)

    def progress(done: int, total: int) -> None:
        print(f"  chunk {done}/{total}", flush=True)

    report = asyncio.run(ingest_document(
        args.file.name, text, domain=args.domain, client=client, raw=raw,
        load=not args.no_load, on_chunk=progress,
    ))
    print_report(report)


if __name__ == "__main__":
    main()
