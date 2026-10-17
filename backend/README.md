# Backend

API cho `frontend/`: truy vấn Neo4j, gọi Jev/LLM để chạy traversal, trả
kết quả benchmark. Khung đã dựng xong (boot được, test pass), logic quyết
định/traversal thật vẫn là TODO — xem [TODO.md](../TODO.md) ở thư mục gốc.

## Chạy

```bash
docker compose up -d   # Neo4j, chạy ở thư mục gốc repo
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

`GET http://localhost:8000/health` phải trả `{"status": "ok"}`.

## Test & lint

```bash
uv run pytest -q
uv run ruff check .
```

## Cấu trúc

```
app/
  main.py                FastAPI app, CORS, include routers
  config.py              Đọc .env (pydantic Settings)
  routers/
    graph.py               Đã triển khai — đọc node/neighbor từ Neo4j
    decisions.py            TODO — POST /decide
    benchmark.py              TODO — POST/GET /benchmark
  services/
    neo4j_client.py         Đã triển khai — driver singleton + query cơ bản
    traversal.py              TODO — thuật toán traversal
    decision_models/
      jev.py, llm.py   TODO — gọi Jev/LLM thật
  models/schemas.py        Pydantic schema dùng chung
```
