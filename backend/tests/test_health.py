"""Smoke test: app phải boot được và /health phải trả 200.

Không cần Neo4j chạy — route /health không đụng tới driver.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
