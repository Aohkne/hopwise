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

**1. Neo4j** (Docker, ở thư mục gốc repo), rồi nạp dữ liệu:

```bash
docker compose up -d
cd backend && uv run python load_data.py
```

`load_data.py` dùng `MERGE` nên chạy lại bao nhiêu lần cũng không tạo trùng.

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

## Benchmark

Tab **Benchmark**: nhập câu hỏi (VD "Xe VF8 của công ty nào?") rồi bấm **Chạy**.
Jev và LLM chạy **song song**, mỗi model tự:

1. chọn domain → 2. chọn loại node → 3. chọn node bắt đầu (chia lô nếu loại đó
quá 250 node) → 4. đi theo cạnh (hai chiều) cho tới khi tự kết luận đã tới đáp án.

Mỗi model tối đa `BENCH_TIMEOUT_SECONDS` (mặc định 300 giây = 5 phút); có nút
**Dừng**. Kết quả: `tìm ra`, `không tìm ra` (đã đi hết node liên quan), `quá 5
phút`, `đã dừng` hoặc `lỗi` (VD thiếu API key, hết credit).

Mỗi hàng model: bên trái là graph các node đã đi qua (số = thứ tự), bên phải có
tab **Status** và **Node đã đi qua** (bấm node bên graph thì dòng đó được viền).
Tab **Lịch sử** xem lại các lượt cũ.

Chạy xong, kết quả ghi vào `outputs/` (đã gitignore):

| File | Nội dung |
|---|---|
| `outputs/runs.csv` | mỗi model 1 dòng/lượt: câu hỏi, trạng thái, đáp án, thời gian, số lần gọi, tokens, chi phí |
| `outputs/run_<id>_trace.csv` | từng bước của từng model: pha, quyết định, node, cạnh đã đi, độ trễ |

Model LLM trong dropdown lấy từ `BASELINE_MODELS` trong `.env`, dạng
`<hãng>/<model>` (hãng: `openai`, `google`, `deepseek`). LLM gọi **thẳng API của
hãng** (không qua OpenRouter) bằng `OPENAI_API_KEY` / `GOOGLE_API_KEY` /
`DEEPSEEK_API_KEY`; lỗi tạm thời (429/5xx) được thử lại tối đa 3 lần. API hãng
không trả chi phí nên cột `cost` của LLM là 0. OpenRouter giờ chỉ dùng cho Jev.

Mỗi hàng model hiện **phiên bản thật** đang chạy: Jev lấy từ response OpenRouter
(VD `typesafe/jev-1.13-20260917`), LLM là tên model đang chọn. Cột `model_version` cũng được ghi vào `outputs/runs.csv`.

### Test & lint

```bash
# backend
cd backend && uv run pytest -q && uv run ruff check .

# frontend
cd frontend && npm run test && npm run lint && npm run build
```

CI chạy các lệnh này tự động khi có thay đổi trong `data/`, `scripts/`,
`backend/` hoặc `frontend/` — xem `.github/workflows/`.
