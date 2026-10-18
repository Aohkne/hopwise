"""Nạp file JSON graph (xem data/README.md) vào Neo4j.

Dùng `MERGE` theo `id` nên chạy lại nhiều lần không tạo node/cạnh trùng.
Gom theo label/type rồi dùng `UNWIND` để mỗi lần nạp chỉ cần vài chục query
thay vì một query cho từng node/cạnh (có thể lên tới hàng nghìn).

Label và relationship type không thể parameterize trong Cypher nên phải
nội suy trực tiếp vào chuỗi query — `_validate_identifier` chặn mọi giá trị
không phải identifier hợp lệ trước khi nội suy, dù nguồn dữ liệu hiện tại
luôn là file do scripts/crawl_*.py tự sinh, không phải input người dùng.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from app.config import get_settings
from app.services.neo4j_client import get_driver

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Label/relationship type không hợp lệ: {name!r}")
    return name


def load_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    settings = get_settings()
    driver = get_driver(settings)

    by_label: dict[str, list[dict]] = collections.defaultdict(list)
    for node in data["nodes"]:
        by_label[node["label"]].append({"id": node["id"], "props": node["properties"]})
    domain = data["domain"]

    by_type: dict[str, list[dict]] = collections.defaultdict(list)
    for edge in data["edges"]:
        by_type[edge["type"]].append(
            {"from_id": edge["from"], "to_id": edge["to"], "props": edge.get("properties", {})}
        )

    with driver.session(database=settings.neo4j_database) as session:
        for label in by_label:
            _validate_identifier(label)
            session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id)")

        for label, nodes in by_label.items():
            session.run(
                f"""
                UNWIND $nodes AS node
                MERGE (n:{label} {{id: node.id}})
                SET n += node.props
                SET n.domains = CASE WHEN $domain IN coalesce(n.domains, [])
                    THEN n.domains ELSE coalesce(n.domains, []) + [$domain] END
                """,
                nodes=nodes,
                domain=domain,
            )

        for etype, edges in by_type.items():
            _validate_identifier(etype)
            session.run(
                f"""
                UNWIND $edges AS edge
                MATCH (a {{id: edge.from_id}}), (b {{id: edge.to_id}})
                MERGE (a)-[r:{etype}]->(b)
                SET r += edge.props
                SET r.domains = CASE WHEN $domain IN coalesce(r.domains, [])
                    THEN r.domains ELSE coalesce(r.domains, []) + [$domain] END
                """,
                edges=edges,
                domain=domain,
            )

    return {
        "nodes": len(data["nodes"]),
        "edges": len(data["edges"]),
        "by_label": {label: len(v) for label, v in by_label.items()},
        "by_edge_type": {etype: len(v) for etype, v in by_type.items()},
    }
