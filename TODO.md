# Việc chưa làm

Khung thư mục của `backend/`, `frontend/`, Docker và CI đã dựng xong (chạy
được, build được, test pass) — xem [GUIDE.md](GUIDE.md). Logic nghiệp vụ
bên trong vẫn chưa triển khai, liệt kê dưới đây.

## Hoàn thiện bản 1.0.0

### Backend

- [x] **Neo4j**
  - [x] Loader: script nạp `data/*.json` vào Neo4j bằng `MERGE` theo `id`
    (theo batch, vì football có ~8000 node+cạnh). `backend/load_data.py`.
  - [x] `GET /api/v1/graph/domains/{domain}` — toàn bộ node + cạnh của 1 domain (node/cạnh được gắn `domains` lúc nạp).
  - [x] `GET /api/v1/graph/search?q=...&limit=...` — tìm node theo `description`, dùng để chọn node bắt đầu traversal ở frontend.
  - [x] `GET /api/v1/graph/nodes/{id}` — lấy chi tiết 1 node theo `id`.
  - [x] `GET /api/v1/graph/nodes/{id}/neighbors` — lấy mọi cạnh nối với 1 node (cả hai chiều, có `direction`), kèm node ở đầu kia.
- [x] **Model**
  - [x] `POST /api/v1/model/jev`: gọi Jev qua OpenRouter. Đã test thật, trả lời đúng.
  - [x] `POST /api/v1/model/llm`: gọi LLM thường (field `model` dạng `<nơi>/<model>`, VD `nvidia/openai/gpt-oss-20b`).
    Chỉ test bằng mock; chưa gọi thật Ollama / NVIDIA (cần `NVIDIA_API_KEY`, Ollama bật).
- [x] **Vòng lặp tìm kiếm** (`services/search.py`): model tự chọn domain → loại node →
  node bắt đầu (chia lô ≤250) → đi theo cạnh hai chiều, lưu node đã thăm + quay lui.
  `GET .../neighbors` giờ trả cả cạnh đi vào (`direction`).
- [x] **Bộ test-case ground truth** (`benchmarks/`) — 30 câu mỗi domain, sinh từ graph,
  chỉ chấm theo đáp án, tiếng Việt. Xem `benchmarks/README.md`.
- [x] **Chấm điểm bằng ground truth** — cột `case_id`, `expected_answers`, `correct` trong CSV;
  chọn câu mẫu ở trang Benchmark thì mỗi model được chấm đúng/sai.
- [x] **Chạy hàng loạt cả bộ câu hỏi** (`backend/run_cases.py`) và báo cáo accuracy / thời gian trung vị theo số bước.
- [x] **Tài liệu xây Knowledge Graph** — giải thích cách các node quan hệ
  với nhau trong `data/football_vn.json` và `data/vinfast.json`: loại node,
  loại cạnh, và vì sao chọn Wikidata/SEC làm nguồn.

### Frontend

- [x] Navbar với 2 mục: Graph và Benchmark.
  - [x] **Graph**: dropdown chọn domain (football, vinfast); không có ô
    tìm kiếm — tải và vẽ toàn bộ node/cạnh của domain (`react-force-graph-2d`)
    từ `GET /api/v1/graph/domains/{domain}`. Bấm node: card ảnh (ảnh mặc định nếu không có) + thông tin hiện góc phải trên trong khung graph. Nút "upload tài liệu" disable vì
    phụ thuộc cơ chế tạo cạnh bằng fact (Bản 2.0.0). Lưu ý: loader dùng
    `MERGE (a)-[r:TYPE]->(b)` nên các giai đoạn của cùng một cặp
    cầu thủ-CLB gộp thành 1 cạnh (4526 cạnh vẽ ra so với 4758 trong JSON).
  - [x] **Benchmark**: câu hỏi → Jev / Gemma 4 (Ollama) / gpt-oss-20b (NVIDIA) chạy song song (tối đa 5 phút
    mỗi model, có nút Dừng). Mỗi model 1 hàng: graph node đã đi qua + tab Status /
    Node đã đi qua; tab Lịch sử xem lại. Kết quả ghi `outputs/*.csv`.
- [x] **Biểu đồ benchmark** — vẽ bằng TikZ (`benchmarks/plot_results.py`), xuất ảnh, nhúng vào README.md.

## Bản 2.0.0

Mục tiêu: cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**, có thể
truy vết lại nguồn — thay cho cách nối theo quan hệ cấu trúc thô của bản 1.0.0
(`PLAYED_FOR`, `BOARD_MEMBER_OF`...). Graph được sinh từ **văn bản** (không crawl
thêm): LLM trích xuất Entity / Relationship / Claim theo prompt 3 lớp. Nghiên cứu
nền tảng nằm ở [`docs/research/`](docs/research/).

Quyết định thiết kế: Entity → node; Relationship → cạnh `RELATED_TO`; Claim →
node `Claim` nối bằng `HAS_CLAIM` / `ABOUT` (nhờ vậy loader `MERGE` không gộp
nhiều fact giữa cùng một cặp node); dữ liệu ghi vào domain riêng `vinfast_policy`
nên không ảnh hưởng 60 câu ground truth của bản 1.0.0.

### Backend

- [x] **Nghiên cứu → docs**: chuyển `hope-wise_done/` vào `docs/research/` (có
  README đánh dấu nghiên cứu); `prompt.md` thành
  `backend/app/harness/prompts/templates/extract_graph.md`.
- [x] **Prompt**: `backend/app/harness/prompts/extract_graph.py` đọc template `.md`
  và dựng prompt từ văn bản đầu vào.
- [x] **LLM trả text**: `LLMClient.complete()` (không ép JSON), chọn provider bằng
  `EXTRACT_PROVIDER` (mặc định NVIDIA gpt-oss-20b, hoặc Ollama).
- [x] **Trích xuất**: parse tuple `<|>` / `##`, chia chunk, gộp/dedupe
  entity-relationship-claim bằng code (`harness/parse.py`, `extract.py`).
- [x] **Dựng graph**: ánh xạ sang schema `data/*.json` kèm provenance
  (`text_unit_ids`, `source_text`) và `text_units` để truy vết (`harness/build_graph.py`).
- [x] **CLI**: `backend/extract_graph.py` (văn bản → `data/vinfast_policy.json` → Neo4j).
- [x] **API upload**: `POST /api/v1/graph/documents` + `GET .../documents/{id}` (job nền).
- [x] **Search**: mô tả cạnh vào lựa chọn của model, mô tả domain `vinfast_policy`.
- [x] **Test** (mock LLM) và dữ liệu `data/vinfast_policy.json` đầu tiên.

### Frontend

- [x] Domain `vinfast_policy` trong trang Graph; bật nút **Upload tài liệu**.
- [x] Card chi tiết node hiển thị thuộc tính của `Claim` (trạng thái, ngày, điều kiện, nguồn).

### Tài liệu

- [x] Cập nhật `README.md`, `GUIDE.md`, `data/README.md`, `backend/README.md`, `frontend/README.md`.

### Để sau bản 2.0.0

- [ ] Tránh chunk bị cắt cụt: tự chia đôi và trích xuất lại chunk hết `max_tokens` (hiện chỉ báo cáo).
- [ ] Prompt merge + dedupe bằng LLM (hiện gộp bằng code).
- [ ] Loại quan hệ có tên cho `RELATED_TO` (prompt hiện chỉ trả mô tả).
- [ ] Liên kết entity của `vinfast_policy` với node Wikidata trong domain `vinfast` (`anchor` / `aliases`).
- [ ] Chạy lại benchmark trên graph có `vinfast_policy`.

## Khác

- [x] Chọn license chính thức cho mã nguồn (Apache-2.0, xem `LICENSE`).
