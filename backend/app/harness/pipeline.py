"""Văn bản -> graph của một domain: trích xuất, gộp vào `data/<domain>.json`, nạp Neo4j.

Dùng chung cho CLI (`extract_graph.py`) và API upload (`routers/graph.py`).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.harness.build_graph import build_document, doc_id_of, merge_documents
from app.harness.enrich import attach_images
from app.harness.extract import ExtractionResult, chunk_text, extract_from_raw, extract_text
from app.services import graph_loader

DOMAIN_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")  # thành tên file data/<domain>.json -> chặn "../"
DEFAULT_DOMAIN = "vinfast_policy"


def make_extractor(provider: str | None = None) -> Any:
    """Client LLM đọc văn bản theo EXTRACT_PROVIDER (hoặc `provider` nếu truyền)."""
    provider = provider or get_settings().extract_provider
    if provider == "nvidia":
        from app.services.decision_models.nvidia import NvidiaClient
        return NvidiaClient()
    if provider == "ollama":
        from app.services.decision_models.ollama import OllamaClient
        return OllamaClient()
    raise ValueError(f"EXTRACT_PROVIDER không hợp lệ: {provider!r} (nvidia | ollama)")


def check_domain(domain: str) -> str:
    if not DOMAIN_RE.fullmatch(domain):
        raise ValueError(f"Tên domain không hợp lệ: {domain!r} (chữ thường, số, `_`; bắt đầu bằng chữ)")
    return domain


def read_domain(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_domain(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_raw(result: ExtractionResult, outputs_dir: Path, domain: str, doc_id: str) -> Path:
    """Output thô của model (để chạy lại bằng --from-raw, hoặc xem model đã trả gì)."""
    path = outputs_dir / "extract" / f"{domain}_{doc_id}_raw.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def ingest_document(
    name: str, text: str, *, domain: str = DEFAULT_DOMAIN, client: Any | None = None,
    raw: dict[str, str] | None = None, load: bool = True,
    on_chunk: Callable[[int, int], None] | None = None,
) -> dict:
    """Trích xuất `text` (tài liệu tên `name`) rồi gộp vào graph của `domain`.

    `raw` (chunk_id -> output của model) thì dựng lại từ đó, không gọi LLM. Trả báo cáo: số
    entity/relationship/claim, record bị bỏ, chunk lỗi, và `loaded` (thống kê nạp Neo4j) nếu `load`.
    """
    settings = get_settings()
    check_domain(domain)
    doc_id = doc_id_of(name)
    if raw is not None:
        chunks = chunk_text(text, settings.extract_chunk_chars)
        # Output thô lưu từ lần chạy trước có cùng cách chia chunk -> khớp từng đoạn; nếu không
        # khớp (VD file mẫu viết tay) thì mỗi chunk trỏ về cả văn bản, vẫn truy vết được.
        units = dict(zip(raw, chunks, strict=True)) if len(chunks) == len(raw) else {cid: text for cid in raw}
        result = extract_from_raw(raw, units)
    else:
        result = await extract_text(
            text, client or make_extractor(), doc_id=doc_id, chunk_chars=settings.extract_chunk_chars,
            max_tokens=settings.extract_max_tokens, on_chunk=on_chunk,
        )
        save_raw(result, settings.outputs_dir, domain, doc_id)

    path = settings.data_dir / f"{domain}.json"
    new = build_document(result.extraction, result.text_units, domain=domain, doc_name=name,
                         title=f"Tri thức trích xuất từ văn bản ({domain})")
    images = attach_images(new, settings.data_dir / "vinfast.json")
    merged = merge_documents(read_domain(path), new)
    write_domain(merged, path)

    report = {**result.report, "domain": domain, "images": images, "doc": name, "file": str(path),
              "graph": merged["stats"]}
    if load:
        # Driver Neo4j chạy đồng bộ: đưa sang thread để không chặn event loop (API đang phục vụ).
        report["loaded"] = await asyncio.to_thread(graph_loader.load_file, path)
    return report
