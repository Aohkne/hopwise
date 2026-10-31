"""Gộp kết quả trích xuất của nhiều chunk thành một, bằng code (không gọi LLM).

- entity cùng tên (sau chuẩn hóa) -> 1: giữ loại phổ biến nhất, mô tả dài nhất, hợp nguồn chunk
- relationship cùng cặp (có hướng) -> 1: độ mạnh lớn nhất, nối các mô tả khác nhau
- claim trùng (chủ thể, khách thể, loại, ngày bắt đầu/kết thúc, điều kiện) -> 1
- relationship/claim có đầu mút không phải entity đã biết, hoặc nối entity với chính nó -> bỏ
  và ghi vào `skipped` (không tự tạo entity mới: prompt yêu cầu entity phải được liệt kê)
"""

from __future__ import annotations

import unicodedata
from collections import Counter

from app.harness.parse import Claim, Entity, Extraction, Relationship


def norm_key(name: str | None) -> str:
    """Khóa so khớp tên: NFC + casefold + gộp khoảng trắng."""
    return " ".join(unicodedata.normalize("NFC", name or "").casefold().split())


def _union(*lists: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for items in lists:
        seen.update(dict.fromkeys(items))
    return list(seen)


def merge_extractions(parts: list[Extraction]) -> Extraction:
    merged = Extraction(skipped=[s for p in parts for s in p.skipped])

    # --- entity ---
    types: dict[str, Counter] = {}
    entities: dict[str, Entity] = {}
    for entity in (e for p in parts for e in p.entities):
        key = norm_key(entity.name)
        types.setdefault(key, Counter())[entity.type] += 1
        known = entities.get(key)
        if known is None:
            entities[key] = Entity(entity.name, entity.type, entity.description, list(entity.text_unit_ids))
            continue
        if len(entity.description) > len(known.description):
            known.description = entity.description
        known.text_unit_ids = _union(known.text_unit_ids, entity.text_unit_ids)
    for key, entity in entities.items():
        entity.type = types[key].most_common(1)[0][0]
    merged.entities = list(entities.values())

    # --- relationship ---
    relationships: dict[tuple[str, str], Relationship] = {}
    for rel in (r for p in parts for r in p.relationships):
        source, target = norm_key(rel.source), norm_key(rel.target)
        if source not in entities or target not in entities:
            merged.skipped.append(f"relationship {rel.source} -> {rel.target}: entity không tồn tại")
            continue
        if source == target:
            merged.skipped.append(f"relationship {rel.source} -> chính nó")
            continue
        known = relationships.get((source, target))
        if known is None:
            relationships[(source, target)] = Relationship(
                entities[source].name, entities[target].name, rel.description, rel.strength,
                list(rel.text_unit_ids),
            )
            continue
        if rel.description and rel.description not in known.description:
            known.description = "; ".join(filter(None, [known.description, rel.description]))
        strengths = [s for s in (known.strength, rel.strength) if s is not None]
        known.strength = max(strengths) if strengths else None
        known.text_unit_ids = _union(known.text_unit_ids, rel.text_unit_ids)
    merged.relationships = list(relationships.values())

    # --- claim ---
    claims: dict[tuple, Claim] = {}
    for claim in (c for p in parts for c in p.claims):
        subject, obj = norm_key(claim.subject), norm_key(claim.object) if claim.object else None
        if subject not in entities or (obj is not None and obj not in entities):
            merged.skipped.append(f"claim {claim.type} {claim.subject} -> {claim.object}: entity không tồn tại")
            continue
        key = (subject, obj, claim.type, claim.start, claim.end, norm_key(claim.condition))
        known = claims.get(key)
        if known is None:
            claims[key] = Claim(
                subject=entities[subject].name, object=entities[obj].name if obj else None,
                type=claim.type, status=claim.status, start=claim.start, end=claim.end,
                condition=claim.condition, description=claim.description,
                source_text=claim.source_text, text_unit_ids=list(claim.text_unit_ids),
            )
            continue
        if len(claim.description) > len(known.description):
            known.description = claim.description
        if len(claim.source_text) > len(known.source_text):
            known.source_text = claim.source_text
        known.text_unit_ids = _union(known.text_unit_ids, claim.text_unit_ids)
    merged.claims = list(claims.values())
    return merged
