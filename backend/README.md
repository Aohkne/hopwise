# Backend

FastAPI cho `frontend/`: đọc Knowledge Graph từ Neo4j, chạy benchmark Jev / Gemma (Ollama) /
gpt-oss (NVIDIA), và (bản 2.0.0) trích xuất graph từ văn bản bằng LLM.

## Chạy

```bash
docker compose up -d   # Neo4j, chạy ở thư mục gốc repo
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

`GET http://localhost:8000/health` phải trả `{"status": "ok"}`. Chi tiết nạp dữ liệu, chạy
benchmark và trích xuất: xem [GUIDE.md](../GUIDE.md).

## Test & lint

```bash
uv run python -m pytest -q
uv run ruff check .
```

Mọi test dùng client/graph giả hoặc `httpx.MockTransport`: không gọi mạng, không cần Neo4j.

## Cấu trúc

```
app/
  main.py                FastAPI app, CORS, include routers
  config.py              Đọc .env (pydantic Settings)
  routers/
    graph.py               Đọc graph; POST /graph/documents nhận tài liệu để trích xuất
    model.py               Gọi trực tiếp Jev / LLM
    benchmark.py           Chạy 3 model song song, tiến độ, dừng, lịch sử
  services/
    neo4j_client.py        Driver singleton + truy vấn đọc
    graph_loader.py        Nạp data/*.json vào Neo4j (MERGE theo id)
    search.py              Vòng lặp tìm đáp án trên graph, dùng chung cho 3 model
    benchmark.py, batch.py, ground_truth.py
    decision_models/       jev.py, llm.py (decide + complete), ollama.py, nvidia.py
  harness/               Bản 2.0.0: văn bản -> graph
    prompts/templates/extract_graph.md   Prompt trích xuất 3 lớp (Entity / Relationship / Claim)
    prompts/extract_graph.py             Đọc template, điền văn bản
    parse.py               Output tuple `<|>` / `##` -> Entity / Relationship / Claim
    merge.py               Gộp và dedupe kết quả nhiều chunk
    extract.py             Chia chunk + gọi LLM từng chunk
    build_graph.py         Extraction -> JSON cùng schema data/*.json (+ provenance)
    pipeline.py            Trích xuất -> data/<domain>.json -> Neo4j (dùng chung CLI và API)
    jobs.py                Job nền cho upload tài liệu
  models/schemas.py      Pydantic schema dùng chung
load_data.py             CLI nạp data/*.json vào Neo4j
run_cases.py             CLI chạy cả bộ 60 câu ground truth
extract_graph.py         CLI trích xuất graph từ văn bản
```

## API

| Endpoint | Việc làm |
|---|---|
| `GET /api/v1/graph/domains/{domain}` | Toàn bộ node + cạnh của domain |
| `GET /api/v1/graph/search`, `/nodes/{id}`, `/nodes/{id}/neighbors` | Tìm node, chi tiết, cạnh hai chiều |
| `POST /api/v1/graph/documents` | `{name, text, domain?}` -> job trích xuất chạy nền |
| `GET /api/v1/graph/documents/{id}` | Tiến độ job (`running` / `done` / `error`) và báo cáo |
| `POST /api/v1/model/jev`, `/model/llm` | Gọi trực tiếp một model |
| `/api/v1/benchmark/*` | `models`, `cases`, `runs`, `history` |
