# Việc chưa làm

Khung thư mục của `backend/`, `frontend/`, Docker và CI đã dựng xong (chạy
được, build được, test pass) — xem [GUIDE.md](GUIDE.md). Logic nghiệp vụ
bên trong vẫn chưa triển khai, liệt kê dưới đây.

## Hoàn thiện bản 1.0.0

### Backend

- [x] **Neo4j**
  - [x] Loader: script nạp `data/*.json` vào Neo4j bằng `MERGE` theo `id`
    (theo batch, vì football có ~8000 node+cạnh). `backend/load_data.py`.
  - [x] `GET /api/v1/graph/search?q=...&limit=...` — tìm node theo `description`, dùng để chọn node bắt đầu traversal ở frontend.
  - [x] `GET /api/v1/graph/nodes/{id}` — lấy chi tiết 1 node theo `id`.
  - [x] `GET /api/v1/graph/nodes/{id}/neighbors` — lấy toàn bộ cạnh đi ra từ 1 node, kèm node đích.
- [x] **Model**
  - [x] `POST /api/v1/model/jev`: gọi Jev qua OpenRouter. Đã test thật, trả lời đúng.
  - [x] `POST /api/v1/model/kev`: gọi Kev (local, tự host). Code xong, fail rõ ràng
    (502) khi chưa bật server Kev — chưa test được happy path vì chưa host Kev.
  - [x] `POST /api/v1/model/llm`: gọi LLM thường (chọn model qua field `model`).
    Đã test thật với model free trên OpenRouter, trả lời đúng.
- [ ] **Bộ test-case ground truth** — mỗi test case gồm câu hỏi, node xuất
  phát, đường đi đúng kỳ vọng và đáp án đúng, cho cả hai domain hiện có.
- [ ] **Tài liệu xây Knowledge Graph** — giải thích cách các node quan hệ
  với nhau trong `data/football_vn.json` và `data/vinfast.json`: loại node,
  loại cạnh, và vì sao chọn Wikidata/SEC làm nguồn.

### Frontend

- [ ] Navbar với 2 mục: Graph và Benchmark.
  - [x] **Graph**: dropdown chọn 1 trong các domain có sẵn (football,
    vinfast). Có thêm lựa chọn "upload tài liệu" để tự xây graph mới — phần này phụ thuộc cơ chế tạo cạnh bằng fact (xem Bản 2.0.0), **hiện
    chưa có nên disable** trên UI. Sơ đồ node-cạnh thật (`react-force-graph-2d`,
    style neo-brutalism) đã nối với `/api/v1/graph/search|nodes`, mở rộng
    theo từng hop khi click. Lưu ý: tìm kiếm chưa lọc theo domain vì backend
    chưa gắn nhãn domain cho
    node.
  - [ ] **Benchmark**: 1 thanh search + 3 panel (Jev / Kev (local) / LLM — dropdown chọn model). UI đã dựng, chưa nối API thật.
- [ ] **Biểu đồ benchmark** — vẽ bằng TikZ, xuất ảnh, nhúng vào phần "Đóng góp" của README.md.

## Bản 2.0.0

- [ ] Cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**, có thể
  truy vết lại nguồn — thay cho cách nối theo quan hệ cấu trúc thô hiện tại
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`...).

## Khác

- [ ] Chọn license chính thức cho mã nguồn.
