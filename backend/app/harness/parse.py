"""Parse đầu ra tuple của prompt trích xuất (xem prompts/templates/extract_graph.md).

    ("entity"<|>tên<|>loại<|>mô_tả)
    ("relationship"<|>nguồn<|>đích<|>mô_tả<|>độ_mạnh)
    ("claim"<|>chủ_thể<|>khách_thể<|>loại<|>trạng_thái<|>ngày_bđ<|>ngày_kt<|>điều_kiện<|>mô_tả<|>nguồn)

Model hay bọc output trong ```code fence```, thêm tiêu đề markdown hoặc lời dẫn, nên parser quét
cả văn bản tìm record thay vì đòi đúng định dạng từng dòng. Record sai số trường bị bỏ và ghi
vào `Extraction.skipped` (không đoán, không sửa). `NONE` -> None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DELIM = "<|>"
NONE = "NONE"

# Một record kết thúc ở dấu ")" đứng ngay trước "##", "<|COMPLETE|>", record kế tiếp, hết code
# fence hoặc hết văn bản — nhờ vậy mô tả được phép chứa dấu ngoặc đơn.
_RECORD = re.compile(
    r'\(\s*"(entity|relationship|claim)"\s*<\|>(.*?)\)'
    r'(?=\s*(?:##|<\|COMPLETE\|>|\(\s*"(?:entity|relationship|claim)"|```|\Z))',
    re.DOTALL,
)

_FIELDS = {"entity": 3, "relationship": 4, "claim": 9}


@dataclass
class Entity:
    name: str
    type: str
    description: str
    text_unit_ids: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    source: str
    target: str
    description: str
    strength: int | None
    text_unit_ids: list[str] = field(default_factory=list)


@dataclass
class Claim:
    subject: str
    object: str | None
    type: str
    status: str
    start: str | None
    end: str | None
    condition: str | None
    description: str
    source_text: str
    text_unit_ids: list[str] = field(default_factory=list)


@dataclass
class Extraction:
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # record bị bỏ (kèm lý do)


def _clean(value: str) -> str:
    return " ".join(value.split())


def _optional(value: str) -> str | None:
    text = _clean(value)
    return None if not text or text.upper() == NONE else text


def _strength(value: str) -> int | None:
    try:
        return max(1, min(10, int(float(_clean(value)))))
    except ValueError:
        return None


def parse_records(text: str, text_unit_id: str) -> Extraction:
    """Mọi record trong `text`, gắn `text_unit_id` (chunk sinh ra chúng) để truy vết."""
    result = Extraction()
    unit = [text_unit_id]
    for match in _RECORD.finditer(text):
        kind, body = match.group(1), match.group(2)
        parts = body.split(DELIM)
        expected = _FIELDS[kind]
        if len(parts) < expected:
            result.skipped.append(f"{kind}: thiếu trường ({len(parts)}/{expected}): {_clean(body)[:80]}")
            continue
        # Mô tả/nguồn là trường cuối, có thể lỡ chứa "<|>" -> gộp phần dư lại.
        parts = parts[: expected - 1] + [DELIM.join(parts[expected - 1:])]
        if kind == "entity":
            name = _clean(parts[0])
            if not name:
                result.skipped.append("entity: tên rỗng")
                continue
            result.entities.append(Entity(name, _clean(parts[1]).upper(), _clean(parts[2]), list(unit)))
        elif kind == "relationship":
            source, target = _clean(parts[0]), _clean(parts[1])
            if not source or not target:
                result.skipped.append(f"relationship: thiếu đầu mút: {_clean(body)[:80]}")
                continue
            result.relationships.append(
                Relationship(source, target, _clean(parts[2]), _strength(parts[3]), list(unit))
            )
        else:
            subject = _clean(parts[0])
            if not subject:
                result.skipped.append(f"claim: thiếu chủ thể: {_clean(body)[:80]}")
                continue
            result.claims.append(Claim(
                subject=subject, object=_optional(parts[1]), type=_clean(parts[2]).upper(),
                status=_clean(parts[3]).upper(), start=_optional(parts[4]), end=_optional(parts[5]),
                condition=_optional(parts[6]), description=_clean(parts[7]),
                source_text=_clean(parts[8]), text_unit_ids=list(unit),
            ))
    return result
