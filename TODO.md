# Việc chưa làm

Khung thư mục của `backend/`, `frontend/`, Docker và CI đã dựng xong (chạy
được, build được, test pass) — xem [GUIDE.md](GUIDE.md). Logic nghiệp vụ
bên trong vẫn chưa triển khai, liệt kê dưới đây.

## Hoàn thiện bản 1.0.0

### Backend

- [ ] **Neo4j**
  - [ ] Loader: script nạp `data/*.json` vào Neo4j bằng `MERGE` theo `id`
    (theo batch, vì football có ~8000 node+cạnh).
  - [ ] `GET /api/v1/graph/search?q=...&limit=...` — tìm node theo `description`, dùng để chọn node bắt đầu traversal ở frontend.
  - [ ] `GET /api/v1/graph/nodes/{id}` — lấy chi tiết 1 node theo `id`.
  - [ ] `GET /api/v1/graph/nodes/{id}/neighbors` — lấy toàn bộ cạnh đi ra từ 1 node, kèm node đích.
- [ ] **Model**
  - [ ] `POST /api/v1/model/jev`: gọi Jev qua OpenRouter.
  - [ ] `POST /api/v1/model/kev`: gọi Kev (local, tự host).
  - [ ] `POST /api/v1/model/llm`: gọi LLM thường (dropdown chọn model).
- [ ] **Bộ test-case ground truth** — mỗi test case gồm câu hỏi, node xuất
  phát, đường đi đúng kỳ vọng và đáp án đúng, cho cả hai domain hiện có.
- [ ] **Tài liệu xây Knowledge Graph** — giải thích cách các node quan hệ
  với nhau trong `data/football_vn.json` và `data/vinfast.json`: loại node,
  loại cạnh, và vì sao chọn Wikidata/SEC làm nguồn.

### Frontend

- [ ] Navbar với 2 mục: Graph và Benchmark.
  - [ ] **Graph**: dropdown chọn 1 trong các domain có sẵn (football,
    vinfast). Có thêm lựa chọn "upload tài liệu" để tự xây graph mới — phần này phụ thuộc cơ chế tạo cạnh bằng fact (xem Bản 2.0.0), **hiện
    chưa có nên disable** trên UI.
  - [ ] **Benchmark**: 1 thanh search + 3 panel (Jev / Kev (local) / LLM — dropdown chọn model).
- [ ] **Biểu đồ benchmark** — vẽ bằng TikZ, xuất ảnh, nhúng vào phần "Đóng góp" của README.md.

## Bản 2.0.0

- [ ] Cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**, có thể
  truy vết lại nguồn — thay cho cách nối theo quan hệ cấu trúc thô hiện tại
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`...).

## Khác

- [ ] Chọn license chính thức cho mã nguồn.
