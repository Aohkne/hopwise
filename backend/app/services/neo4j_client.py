"""Wrapper mỏng quanh driver Neo4j chính thức.

Chỉ chứa các truy vấn đọc dữ liệu cơ bản (lấy node, lấy neighbor). Thuật
toán traversal/benchmark nằm ở `services/traversal.py`, không đặt ở đây.
"""

from __future__ import annotations

from neo4j import Driver, GraphDatabase

from app.config import Settings, get_settings

_driver: Driver | None = None


def get_driver(settings: Settings | None = None) -> Driver:
    """Driver singleton — tạo một lần, dùng lại cho mọi request."""
    global _driver
    if _driver is None:
        s = settings or get_settings()
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def get_node(node_id: str) -> dict | None:
    """Lấy 1 node theo `id` (property, không phải element id nội bộ của Neo4j)."""
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        record = session.run(
            "MATCH (n {id: $id}) RETURN n, labels(n) AS labels", id=node_id
        ).single()
        if record is None:
            return None
        node = dict(record["n"])
        return {"id": node_id, "label": record["labels"][0], "properties": node}


def get_neighbors(node_id: str) -> list[dict]:
    """Lấy mọi cạnh đi ra từ 1 node, kèm node đích — dùng cho bước Choice ở mỗi hop."""
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            """
            MATCH (n {id: $id})-[r]->(m)
            RETURN type(r) AS edge_type, properties(r) AS edge_props,
                   m.id AS target_id, labels(m)[0] AS target_label,
                   m.description AS target_description
            """,
            id=node_id,
        )
        return [dict(record) for record in records]
