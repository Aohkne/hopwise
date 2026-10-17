"""Test endpoint GET /api/v1/graph/domains/{domain} — mock neo4j_client nên
không cần Neo4j chạy (và không đụng server đang chạy của người dùng)."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import neo4j_client

client = TestClient(app)


def test_domain_graph_returns_nodes_and_edges(monkeypatch) -> None:
    monkeypatch.setattr(
        neo4j_client,
        "get_domain_graph",
        lambda domain: {
            "nodes": [
                {"id": "a", "label": "Company", "caption": "A"},
                {"id": "b", "label": "CarModel", "caption": None},
            ],
            "edges": [{"source": "a", "target": "b", "kind": "MANUFACTURES"}],
        },
    )
    response = client.get("/api/v1/graph/domains/vinfast")
    assert response.status_code == 200
    body = response.json()
    assert [n["id"] for n in body["nodes"]] == ["a", "b"]
    assert body["edges"] == [{"source": "a", "target": "b", "kind": "MANUFACTURES"}]


def test_unknown_domain_is_404(monkeypatch) -> None:
    monkeypatch.setattr(
        neo4j_client, "get_domain_graph", lambda domain: {"nodes": [], "edges": []}
    )
    assert client.get("/api/v1/graph/domains/nope").status_code == 404
