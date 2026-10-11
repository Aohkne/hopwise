# Việc chưa làm

Mọi mục dưới đây đã được phác thảo trong [README.md](README.md) /
[VERSION.md](VERSION.md) nhưng chưa có một dòng code nào.

## Hoàn thiện bản 1.0.0

- [ ] **Loader Neo4j** — nạp `data/*.json` vào Neo4j bằng `MERGE` theo `id`,
  chạy lại nhiều lần không tạo trùng.
- [ ] **Bộ test-case ground truth** — mỗi test case gồm câu hỏi, node xuất
  phát, đường đi đúng kỳ vọng và đáp án đúng, cho cả hai domain hiện có.
- [ ] **Harness so sánh System 1 và System 2** — cùng một câu hỏi và cùng một
  graph, chạy qua Jev, qua [Kev](https://github.com/jaredpalmer/kev) (bản
  mã nguồn mở tương thích API), và qua LLM thông thường (GPT, Claude, Gemini
  qua OpenRouter); đo accuracy, latency và chi phí của từng bên.
- [ ] **Biểu đồ benchmark** — vẽ bằng TikZ, xuất ảnh, nhúng vào phần "Đóng
  góp" của README.md.
- [ ] **Tài liệu xây Knowledge Graph** — giải thích cách các node quan hệ
  với nhau trong `data/football_vn.json` và `data/vinfast.json`: loại node,
  loại cạnh, và vì sao chọn Wikidata/SEC làm nguồn.

## Bản 2.0.0

- [ ] Cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**, có thể
  truy vết lại nguồn — thay cho cách nối theo quan hệ cấu trúc thô hiện tại
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`...).

## Frontend (`frontend/`)

- [ ] Khởi tạo React + Tailwind CSS + [Iconify](https://iconify.design/).
- [ ] Áp dụng phong cách **neo-brutalism**: border rõ nét kết hợp box-shadow,
  nhưng bo góc nhẹ (`border-radius: 8px`) thay vì vuông hoàn toàn như
  neo-brutalism truyền thống.
- [ ] Giao diện xem Knowledge Graph và kết quả benchmark.

## Backend (`backend/`)

- [ ] API phục vụ frontend: truy vấn Neo4j, gọi Jev/Kev/LLM để chạy
  traversal theo yêu cầu, trả kết quả benchmark.

## Khác

- [ ] Chọn license chính thức cho mã nguồn.
