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
  - [x] `POST /api/v1/model/llm`: gọi LLM thường (chọn model qua field `model`).
    Đã test thật với model free trên OpenRouter, trả lời đúng.
- [x] **Vòng lặp tìm kiếm** (`services/search.py`): model tự chọn domain → loại node →
  node bắt đầu (chia lô ≤250) → đi theo cạnh hai chiều, lưu node đã thăm + quay lui.
  `GET .../neighbors` giờ trả cả cạnh đi vào (`direction`).
- [ ] **Bộ test-case ground truth** — mỗi test case gồm câu hỏi, node xuất
  phát, đường đi đúng kỳ vọng và đáp án đúng, cho cả hai domain hiện có.
- [ ] **Tài liệu xây Knowledge Graph** — giải thích cách các node quan hệ
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
  - [x] **Benchmark**: câu hỏi → Jev / LLM chạy song song (tối đa 5 phút
    mỗi model, có nút Dừng). Mỗi model 1 hàng: graph node đã đi qua + tab Status /
    Node đã đi qua; tab Lịch sử xem lại. Kết quả ghi `outputs/*.csv`.
- [ ] **Biểu đồ benchmark** — vẽ bằng TikZ, xuất ảnh, nhúng vào phần "Đóng góp" của README.md.

## Bản 2.0.0

- [ ] Cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**, có thể
  truy vết lại nguồn — thay cho cách nối theo quan hệ cấu trúc thô hiện tại
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`...).

## Khác

- [ ] Chọn license chính thức cho mã nguồn.
