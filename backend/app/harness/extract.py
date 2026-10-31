"""Văn bản -> Extraction: chia chunk, gọi LLM từng chunk bằng prompt 3 lớp, parse rồi gộp.

Chunk chạy lần lượt (model local chỉ xử lý 1 yêu cầu một lúc, và API ngoài hay giới hạn tốc độ).
Một chunk lỗi (mạng, model trả rỗng...) không làm hỏng cả tài liệu: lỗi được ghi vào báo cáo và
chunk đó bị bỏ qua; chỉ khi MỌI chunk đều lỗi mới ném lỗi.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.harness.merge import merge_extractions
from app.harness.parse import Extraction, parse_records
from app.harness.prompts.extract_graph import build_prompt


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Chia theo đoạn (dòng trống), gom các đoạn liền nhau tới `max_chars`. Đoạn dài hơn nữa thì
    chia theo dòng, dòng dài hơn nữa thì cắt cứng — không bao giờ làm mất nội dung."""
    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            pieces.append(paragraph)
            continue
        for line in paragraph.splitlines():
            line = line.strip()
            pieces.extend(line[i:i + max_chars] for i in range(0, len(line), max_chars))

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


@dataclass
class ExtractionResult:
    extraction: Extraction
    text_units: dict[str, str]  # chunk_id -> văn bản chunk (để truy vết)
    raw: dict[str, str]  # chunk_id -> output thô của model
    report: dict[str, Any] = field(default_factory=dict)


def _report(extraction: Extraction, chunks: int, errors: list[str], truncated: list[str],
            usage: dict[str, int]) -> dict[str, Any]:
    return {
        "chunks": chunks,
        "entities": len(extraction.entities),
        "relationships": len(extraction.relationships),
        "claims": len(extraction.claims),
        "skipped": extraction.skipped,
        "errors": errors,
        "truncated_chunks": truncated,
        **usage,
    }


def extract_from_raw(raw: dict[str, str], text_units: dict[str, str]) -> ExtractionResult:
    """Dựng Extraction từ output thô đã có (không gọi LLM): `chunk_id -> output`."""
    parts = [parse_records(output, chunk_id) for chunk_id, output in raw.items()]
    extraction = merge_extractions(parts)
    return ExtractionResult(extraction, text_units, raw,
                            _report(extraction, len(raw), [], [], {"tokens": 0}))


async def extract_text(
    text: str, client: Any, *, doc_id: str, chunk_chars: int, max_tokens: int,
    on_chunk: Callable[[int, int], None] | None = None,
) -> ExtractionResult:
    """`client.complete(prompt, max_tokens)` -> {"text", "usage", "truncated"} (xem LLMClient)."""
    chunks = chunk_text(text, chunk_chars)
    if not chunks:
        raise ValueError("Văn bản trống")
    text_units: dict[str, str] = {}
    raw: dict[str, str] = {}
    parts: list[Extraction] = []
    errors: list[str] = []
    truncated: list[str] = []
    tokens = 0
    for index, chunk in enumerate(chunks, 1):
        chunk_id = f"{doc_id}_c{index:03d}"
        text_units[chunk_id] = chunk
        try:
            reply = await client.complete(build_prompt(chunk), max_tokens)
        except Exception as err:  # noqa: BLE001 — lỗi 1 chunk không được làm hỏng cả tài liệu
            errors.append(f"{chunk_id}: {err or type(err).__name__}")
        else:
            raw[chunk_id] = reply["text"]
            parts.append(parse_records(reply["text"], chunk_id))
            if reply.get("truncated"):
                truncated.append(chunk_id)
            usage = reply.get("usage") or {}
            tokens += int(usage.get("total_tokens") or 0)
        if on_chunk:
            on_chunk(index, len(chunks))
    if not parts:
        raise RuntimeError("Mọi chunk đều lỗi: " + "; ".join(errors))
    extraction = merge_extractions(parts)
    return ExtractionResult(extraction, text_units, raw,
                            _report(extraction, len(chunks), errors, truncated, {"tokens": tokens}))
