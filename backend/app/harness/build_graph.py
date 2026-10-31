"""Extraction -> JSON graph cùng schema với data/*.json (xem data/README.md), để
`graph_loader.load_file`, `scripts/verify_data.py` và frontend dùng lại không cần sửa.

Ánh xạ:
  Entity       -> node, label theo loại (Organization, Product, Geo, Event, Person, Program)
  Relationship -> cạnh RELATED_TO {description, weight, text_unit_ids, source_docs}
  Claim        -> node Claim + cạnh HAS_CLAIM (chủ thể -> claim) và ABOUT (claim -> khách thể)

Claim là node chứ không phải cạnh: loader `MERGE (a)-[r:TYPE]->(b)` gộp mọi cạnh cùng loại giữa
một cặp node, nên nhiều fact giữa cùng 2 entity (VD nhiều đợt giảm giá) sẽ mất nếu là cạnh.

Truy vết: mọi node/cạnh mang `text_unit_ids`; JSON có `text_units` (chunk_id -> văn bản gốc) và
claim có thêm `source_text` (đoạn trích nguyên văn mà model dẫn).
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.harness.merge import norm_key
from app.harness.parse import Extraction

ENTITY_LABELS = {
    "ORGANIZATION": "Organization", "PRODUCT": "Product", "GEO": "Geo",
    "EVENT": "Event", "PERSON": "Person", "PROGRAM": "Program",
}
DEFAULT_LABEL = "Entity"  # loại ngoài danh sách của prompt: giữ node, không đoán loại
RELATION = "RELATED_TO"


def slug(text: str) -> str:
    """Chữ thường, giữ nguyên chữ có dấu (giống id trong data/*.json), ký tự khác -> `_`."""
    return re.sub(r"\W+", "_", norm_key(text)).strip("_")


def doc_id_of(name: str) -> str:
    return slug(re.sub(r"\.[A-Za-z0-9]+$", "", name)) or "doc"


def entity_id(name: str) -> str:
    return "ent_" + (slug(name) or hashlib.sha1(name.encode()).hexdigest()[:12])


def claim_id(subject: str, obj: str | None, ctype: str, start: str | None, end: str | None,
             condition: str | None) -> str:
    key = "|".join([norm_key(subject), norm_key(obj), ctype, start or "", end or "", norm_key(condition)])
    return "claim_" + hashlib.sha1(key.encode()).hexdigest()[:12]


def _props(**values: Any) -> dict:
    """Bỏ giá trị rỗng: Neo4j không lưu null và JSON gọn hơn."""
    return {k: v for k, v in values.items() if v not in (None, "", [])}


def build_document(extraction: Extraction, text_units: dict[str, str], *, domain: str,
                   doc_name: str, title: str | None = None) -> dict:
    """Graph của MỘT tài liệu. Dùng `merge_documents` để gộp vào graph đã có của domain."""
    docs = [doc_name]
    nodes: list[dict] = []
    edges: list[dict] = []
    ids = {norm_key(e.name): entity_id(e.name) for e in extraction.entities}

    for e in extraction.entities:
        nodes.append({
            "id": ids[norm_key(e.name)],
            "label": ENTITY_LABELS.get(e.type, DEFAULT_LABEL),
            "properties": _props(name=e.name, description=e.description, entity_type=e.type,
                                 source="document", source_docs=docs, text_unit_ids=e.text_unit_ids),
        })
    for r in extraction.relationships:
        edges.append({
            "from": ids[norm_key(r.source)], "to": ids[norm_key(r.target)], "type": RELATION,
            "properties": _props(description=r.description,
                                 weight=None if r.strength is None else round(r.strength / 10, 2),
                                 source_docs=docs, text_unit_ids=r.text_unit_ids),
        })
    for c in extraction.claims:
        cid = claim_id(c.subject, c.object, c.type, c.start, c.end, c.condition)
        nodes.append({
            "id": cid, "label": "Claim",
            "properties": _props(description=c.description, claim_type=c.type, status=c.status,
                                 start_date=c.start, end_date=c.end, condition=c.condition,
                                 source_text=c.source_text, source="document", source_docs=docs,
                                 text_unit_ids=c.text_unit_ids),
        })
        edges.append({"from": ids[norm_key(c.subject)], "to": cid, "type": "HAS_CLAIM", "properties": {}})
        if c.object:
            edges.append({"from": cid, "to": ids[norm_key(c.object)], "type": "ABOUT", "properties": {}})

    return _finish({
        "domain": domain,
        "title": title or domain,
        "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": [{"name": doc_name, "type": "document"}],
        "nodes": nodes, "edges": edges, "text_units": dict(text_units),
    })


def _union(a: list, b: list) -> list:
    return list(dict.fromkeys([*a, *b]))


def merge_documents(existing: dict | None, new: dict) -> dict:
    """Gộp graph mới vào graph đã có của cùng domain, theo id node / (from, to, type) cạnh.

    Node đã có giữ nguyên label (Neo4j `MERGE (n:Label {id})` sẽ tạo node trùng id nếu label đổi);
    mô tả dài hơn thắng; danh sách nguồn được hợp lại.
    """
    if existing is None:
        return new
    if existing["domain"] != new["domain"]:
        raise ValueError(f"Khác domain: {existing['domain']} / {new['domain']}")

    nodes = {n["id"]: n for n in existing["nodes"]}
    for node in new["nodes"]:
        known = nodes.get(node["id"])
        if known is None:
            nodes[node["id"]] = node
            continue
        _merge_props(known["properties"], node["properties"])

    edges = {(e["from"], e["to"], e["type"]): e for e in existing["edges"]}
    for edge in new["edges"]:
        known = edges.get((edge["from"], edge["to"], edge["type"]))
        if known is None:
            edges[(edge["from"], edge["to"], edge["type"])] = edge
            continue
        _merge_props(known["properties"], edge["properties"])

    sources = existing.get("sources", [])
    for source in new.get("sources", []):
        if source not in sources:
            sources = [*sources, source]
    return _finish({
        **existing, "extracted_at": new["extracted_at"], "sources": sources,
        "nodes": list(nodes.values()), "edges": list(edges.values()),
        "text_units": {**existing.get("text_units", {}), **new.get("text_units", {})},
    })


def _merge_props(into: dict, other: dict) -> None:
    for key in ("source_docs", "text_unit_ids"):
        if key in other:
            into[key] = _union(into.get(key, []), other[key])
    for key, value in other.items():
        if key in ("source_docs", "text_unit_ids"):
            continue
        if key not in into or (key == "description" and len(str(value)) > len(str(into[key]))):
            into[key] = value
        elif key == "weight":
            into[key] = max(into[key], value)


def _finish(doc: dict) -> dict:
    """Thống kê theo định dạng data/*.json (scripts/verify_data.py đọc `stats`)."""
    doc["stats"] = {
        "nodes": len(doc["nodes"]), "edges": len(doc["edges"]),
        "by_label": dict(Counter(n["label"] for n in doc["nodes"])),
        "by_edge_type": dict(Counter(e["type"] for e in doc["edges"])),
    }
    return doc
