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
    """Lấy mọi cạnh nối với 1 node theo CẢ HAI chiều, kèm node ở đầu kia.

    Phải lấy cả chiều vào: VD `VinFast -[MANUFACTURES]-> VF 8` thì từ VF 8 chỉ
    có cạnh đi vào — chỉ lấy chiều ra sẽ kẹt ngay khi hỏi "VF 8 của hãng nào".
    `direction` = "out" nếu cạnh đi ra từ node này, "in" nếu đi vào.
    """
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            """
            MATCH (n {id: $id})-[r]-(m)
            RETURN type(r) AS edge_type, properties(r) AS edge_props,
                   m.id AS target_id, labels(m)[0] AS target_label,
                   m.description AS target_description,
                   CASE WHEN startNode(r) = n THEN "out" ELSE "in" END AS direction
            """,
            id=node_id,
        )
        return [dict(record) for record in records]


def list_domains() -> list[str]:
    """Các domain đã nạp (mỗi node mang danh sách `domains`, xem graph_loader)."""
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        records = session.run("MATCH (n) UNWIND n.domains AS d RETURN DISTINCT d ORDER BY d")
        return [r["d"] for r in records]


def list_labels(domain: str) -> list[dict]:
    """Các loại node (label) trong 1 domain kèm số lượng."""
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            """
            MATCH (n) WHERE $d IN n.domains
            RETURN labels(n)[0] AS label, count(*) AS count ORDER BY label
            """,
            d=domain,
        )
        return [dict(r) for r in records]


def list_nodes(domain: str, label: str) -> list[dict]:
    """Mọi node của 1 label trong 1 domain (id + description), sắp theo id cho ổn định.

    label không parameterize được trong Cypher, nên lọc bằng labels(n) thay vì
    nội suy vào chuỗi query.
    """
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            """
            MATCH (n) WHERE $d IN n.domains AND $label IN labels(n)
            RETURN n.id AS id, labels(n)[0] AS label, n.description AS description
            ORDER BY n.id
            """,
            d=domain,
            label=label,
        )
        return [dict(r) for r in records]


def get_domain_graph(domain: str) -> dict:
    """Toàn bộ node + cạnh thuộc 1 domain (được gắn `domains` lúc nạp, xem
    graph_loader). Chỉ trả field cần để vẽ — không trả toàn bộ properties
    (football có ~3000 node, trả hết sẽ rất nặng)."""
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        nodes = session.run(
            """
            MATCH (n) WHERE $d IN n.domains
            RETURN n.id AS id, labels(n)[0] AS label,
                   coalesce(n.name, n.name_vi, n.description) AS caption
            """,
            d=domain,
        )
        node_rows = [dict(r) for r in nodes]
        edges = session.run(
            """
            MATCH (a)-[r]->(b) WHERE $d IN r.domains
            RETURN a.id AS source, b.id AS target, type(r) AS kind
            """,
            d=domain,
        )
        edge_rows = [dict(r) for r in edges]
    return {"nodes": node_rows, "edges": edge_rows}


def search_nodes(q: str, limit: int = 20) -> list[dict]:
    """Tìm node theo `description` (field mọi node đều có, xem data/README.md).

    Dùng cho ô tìm kiếm ở frontend để chọn node bắt đầu traversal — người
    dùng không thể tự biết `id` dạng QID để gõ trực tiếp.
    """
    settings = get_settings()
    driver = get_driver(settings)
    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            """
            MATCH (n)
            WHERE n.description IS NOT NULL AND toLower(n.description) CONTAINS toLower($q)
            RETURN n.id AS id, labels(n)[0] AS label, n.description AS description
            LIMIT $limit
            """,
            q=q,
            limit=limit,
        )
        return [dict(record) for record in records]
