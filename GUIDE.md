# Hướng dẫn

## Chạy script crawl dữ liệu

Yêu cầu Python 3.10+; các script chỉ dùng thư viện chuẩn, không cần cài gì
thêm.

```bash
cp .env.example .env   # điền OPENROUTER_API_KEY hoặc TYPESAFE_API_KEY nếu cần
```

| Script | Việc làm | Thời gian |
|---|---|---|
| `scripts/crawl_football.py` | Crawl bóng đá Việt Nam (ĐTQG + V.League 1) từ Wikidata → `data/football_vn.json` | ~8 phút |
| `scripts/crawl_vinfast.py` | Crawl VinFast từ Wikidata + SEC EDGAR 20-F → `data/vinfast.json` | ~1 phút |
| `scripts/verify_data.py` | Kiểm tra toàn vẹn graph và link ảnh | ~1 phút |

```bash
python3 scripts/crawl_football.py
python3 scripts/crawl_vinfast.py
python3 scripts/verify_data.py
```

`verify_data.py` thoát với mã lỗi khác 0 nếu phát hiện vấn đề — ví dụ node
`id` trùng, cạnh trỏ tới node không tồn tại, hoặc link ảnh chết. Chạy lại
sau khi sửa.

Chi tiết từng field, nguồn dữ liệu và hạn chế đã biết: xem
[`data/README.md`](data/README.md).

## Chạy toàn bộ project

Khung `backend/` và `frontend/` đã dựng xong (chạy được, build được) nhưng
logic quyết định/traversal thật vẫn chưa có — xem [TODO.md](TODO.md).

**1. Neo4j** (Docker):

```bash
docker compose up -d
```

**2. Backend** (FastAPI, terminal khác):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Kiểm tra: `curl http://localhost:8000/health` → `{"status": "ok"}`.

**3. Frontend** (React + Vite, terminal khác):

```bash
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173` — request tới `/api/*` được Vite proxy sang
backend ở `:8000` (xem `frontend/vite.config.ts`).

### Test & lint

```bash
# backend
cd backend && uv run pytest -q && uv run ruff check .

# frontend
cd frontend && npm run test && npm run lint && npm run build
```

CI chạy các lệnh này tự động khi có thay đổi trong `data/`, `scripts/`,
`backend/` hoặc `frontend/` — xem `.github/workflows/`.
