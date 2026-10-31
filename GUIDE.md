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

## Trích xuất graph từ văn bản (bản 2.0.0)

Bản 2.0.0 dựng graph từ **văn bản** thay vì crawl: LLM đọc từng đoạn, trích xuất Entity /
Relationship / Claim theo prompt 3 lớp ([`extract_graph.md`](backend/app/harness/prompts/templates/extract_graph.md),
nghiên cứu nền ở [`docs/research/`](docs/research/)), rồi ghi vào `data/vinfast_policy.json`.

| Trong văn bản | Trong graph |
|---|---|
| Thực thể có tên riêng (tổ chức, sản phẩm, địa điểm, sự kiện, người, chương trình) | Node `Organization` / `Product` / `Geo` / `Event` / `Person` / `Program` |
| Quan hệ nối 2 thực thể | Cạnh `RELATED_TO` {`description`, `weight`, `text_unit_ids`} |
| Fact có điều kiện / thời gian / trạng thái đúng-sai | Node `Claim` {`status`, `start_date`, `end_date`, `condition`, `source_text`} nối `Entity -HAS_CLAIM-> Claim -ABOUT-> Entity` |

Mọi node/cạnh mang `text_unit_ids` (đoạn văn đã sinh ra nó); file JSON có `text_units` chứa chính
các đoạn đó, nên từ bất kỳ fact nào cũng truy được về nguồn.

**Cần:** `NVIDIA_API_KEY` trong `.env` (mặc định `EXTRACT_PROVIDER=nvidia`, gpt-oss-20b), hoặc
`EXTRACT_PROVIDER=ollama` để dùng Gemma local (xem phần Benchmark bên dưới để cấu hình Ollama).

```bash
cd backend
uv run python extract_graph.py ../docs/research/samples/data/sample.txt --no-load   # chỉ ghi JSON
uv run python extract_graph.py văn_bản.md                                           # ghi JSON + nạp Neo4j
```

- Chạy nhiều tài liệu vào cùng một domain thì graph được **gộp** (cùng tên entity là cùng node).
  `--domain` đổi domain (mặc định `vinfast_policy`), `--provider nvidia|ollama` đổi model.
- Output thô của model được lưu ở `outputs/extract/`. Dựng lại graph từ output có sẵn mà không gọi
  LLM: `--from-raw outputs/extract/vinfast_policy_sample_raw.json` (hoặc một file output viết theo
  định dạng tuple, như các mẫu trong `docs/research/samples/output/`).
- Cuối lệnh in báo cáo: số entity / relationship / claim, đoạn bị lỗi hoặc bị cắt cụt, record model
  trả sai định dạng nên bị bỏ.
- Một tài liệu dài mất vài phút (gpt-oss suy luận trước khi trả lời, ~1–3 phút mỗi đoạn 3.000 ký tự).

**Trên giao diện:** trang Graph → nút **Upload tài liệu** → chọn file `.txt` / `.md`. Backend chạy
job nền (`POST /api/v1/graph/documents`), trang hiện tiến độ rồi tự chuyển sang domain
`vinfast_policy` và tải lại graph. Cần backend + Neo4j đang chạy.

## Benchmark

Tab **Benchmark**: nhập câu hỏi (VD "Xe VF8 của công ty nào?") rồi bấm **Chạy**.
Ba model chạy **song song**: **Jev** (System 1, qua OpenRouter), **Gemma 4 12B** chạy local
bằng Ollama và **gpt-oss-20b** qua NVIDIA NIM (System 2). Mỗi model tự:

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
| `outputs/runs.csv` | mỗi model 1 dòng/lượt: câu hỏi, `case_id`, `expected_answers`, trạng thái, đáp án, `correct`, thời gian, số lần gọi, tokens, chi phí |
| `outputs/run_<id>_trace.csv` | từng bước của từng model: pha, quyết định, node, cạnh đã đi, độ trễ |

Hai model System 2 đều là LLM thường, gọi qua endpoint tương thích OpenAI và **không đi qua
OpenRouter** (OpenRouter chỉ dùng cho Jev). Lỗi tạm thời (429/5xx) được thử lại tối đa 3 lần.
Cả hai không trả chi phí nên cột `cost` là 0. Mỗi hàng model hiện **phiên bản đang chạy**: Jev
lấy từ response OpenRouter (VD `typesafe/jev-1.13-20260917`), Gemma hỏi từ Ollama (VD
`gemma4:12b · 11.9B · Q4_K_M`), gpt-oss là `NVIDIA_MODEL`. Cột `model_version` cũng được ghi vào
`outputs/runs.csv`.

### Cấu hình hai card System 2

Copy các biến trong `.env.example` sang `.env` (không commit `.env`):

| Card | Biến | Ghi chú |
|---|---|---|
| OLLAMA · LOCAL | `OLLAMA_BASE_URL`, `OLLAMA_MODEL=gemma4-12b-32k` | không cần API key |
| NVIDIA · API | `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL=openai/gpt-oss-20b` | key lấy ở https://build.nvidia.com |

Thiếu cấu hình thì chỉ hàng đó báo lỗi (kèm cách sửa), hai hàng kia vẫn chạy. Sửa `.env`
xong phải khởi động lại backend.

**Gemma 4 12B (Ollama):** ~8GB, chạy 100% GPU. Cần tạo **biến thể ngữ cảnh 32K**
một lần:

```bash
ollama serve                                   # nếu chưa chạy
ollama pull gemma4:12b
# tạo Modelfile 2 dòng rồi tạo biến thể (không tải lại gì)
printf 'FROM gemma4:12b\nPARAMETER num_ctx 32768\n' > Modelfile
ollama create gemma4-12b-32k -f Modelfile
```

rồi đặt `OLLAMA_MODEL=gemma4-12b-32k` trong `.env` (mặc định của `.env.example`).
- **Vì sao cần biến thể:** Ollama mặc định chỉ dùng ngữ cảnh **4096 token**. Câu có 250 lựa chọn dài
  khoảng 11.700 token, và model suy luận còn cần chỗ để "nghĩ". Prompt bị cắt (log:
  `truncating input prompt`) thì Ollama trả `500 no user query found in messages`, hoặc model dừng
  với `finish_reason=length` và nội dung rỗng. Với biến thể 32K, đo thật: 250 lựa chọn chạy ~26s,
  vẫn 100% GPU, không phải giảm `BENCH_CHUNK`.
- Gemma 4 là model suy luận nên mỗi lần gọi có thể "nghĩ" lâu. `OLLAMA_REASONING_EFFORT` (mặc định
  `low`) chỉnh mức này. Đo thật: mặc định ~16s/lần gọi, `low` ~18-30s, `none`
  ~1,4s (chưa kiểm tra độ chính xác). Giới hạn 5 phút vẫn áp như nhau cho mọi model.
- Backend không thử lại lỗi 5xx của Ollama (lỗi cố định, thử lại chỉ tốn thêm thời gian).

**gpt-oss-20b (NVIDIA):** gọi đúng như ví dụ của build.nvidia.com (`temperature=1`, `top_p=1`,
`max_tokens=4096`, không ép JSON mode). gpt-oss có bước suy luận riêng; nếu dùng hết 4096 token cho
suy luận mà chưa trả lời thì lượt gọi đó báo lỗi `finish_reason=length`.

### Chấm đúng/sai bằng ground truth

Chọn một câu ở ô **Câu hỏi mẫu (ground truth)** (bộ 60 câu trong `benchmarks/cases/`, xem
`benchmarks/README.md`) thì mỗi model được chấm. Sửa câu hỏi bằng tay thì lượt đó không chấm.
Ba cột trong CSV:

| Cột | Giá trị |
|---|---|
| `case_id` | VD `vinfast-008`; rỗng với câu gõ tay |
| `expected_answers` | các node đáp án đúng, nối bằng `\|` (các node cùng một thực thể) |
| `correct` | `true` nếu `answer_node_id` thuộc `expected_answers`, `false` nếu model tìm ra node sai, **rỗng** nếu model không đưa ra đáp án (không tìm ra, quá giờ, dừng, lỗi) hoặc câu gõ tay |

### Chạy cả bộ ground truth, vẽ biểu đồ, làm GIF

```bash
# 1. chạy 60 câu qua cả 3 model (lần lượt từng câu; dừng giữa chừng chạy lại sẽ bỏ qua câu đã xong)
cd backend && uv run python run_cases.py            # --domain vinfast | --ids vinfast-001 ...
uv run python run_cases.py --summary                # chỉ in bảng tổng hợp, ghi outputs/summary.json

# 2. biểu đồ TikZ (chấm đúng/sai quanh đường chéo, cột chính xác/thời gian/chi phí) -> docs/images/benchmark-*.png (cần `brew install tectonic poppler`)
cd .. && python3 benchmarks/plot_results.py

# 3. GIF minh hoạ -> docs/images/trace-*.gif (cần frontend + backend đang chạy, ffmpeg,
#    Playwright cài ở thư mục riêng: npm i playwright@1.49.1 && npx playwright install chromium)
python3 benchmarks/make_gifs.py --list               # xem câu ứng viên
python3 benchmarks/make_gifs.py --playwright <thư mục có node_modules/playwright>
```

`make_gifs.py` tự chọn câu mà **số node ít nhất trong 3 model là lớn nhất** (cả 3 GIF cùng một câu
hỏi, đều đi qua nhiều node), mở tab Lịch sử, chụp tab Status rồi bấm từng node trong tab "Node đã
đi qua". Không chạy câu nào trên giao diện trong lúc chạy hàng loạt — sẽ tranh Ollama và làm sai
thời gian đo.

### Test & lint

```bash
# backend
cd backend && uv run python -m pytest -q && uv run ruff check .

# frontend
cd frontend && npm run test && npm run lint && npm run build
```

CI chạy các lệnh này tự động khi có thay đổi trong `data/`, `scripts/`,
`backend/` hoặc `frontend/` — xem `.github/workflows/`.
