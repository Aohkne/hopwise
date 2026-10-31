# Lộ trình phiên bản

## 1.0.0 — Dữ liệu và graph thô sơ

- **Bộ crawl dữ liệu**: `scripts/crawl_football.py` và
  `scripts/crawl_vinfast.py`, lấy dữ liệu thật từ Wikidata SPARQL và SEC
  EDGAR 20-F.
- **Knowledge Graph thô sơ**: các node được nối bằng thuật toán đơn giản —
  mỗi cạnh ánh xạ trực tiếp một quan hệ có sẵn trong nguồn (`PLAYED_FOR`,
  `BOARD_MEMBER_OF`...), chưa có bước suy luận ngữ nghĩa nào giữa các node.
- **So sánh System 1 và System 2**: đối chiếu Jev (System 1) với LLM
  thông thường (System 2) trên cùng bài toán traversal.
- CI/CD

## 2.0.0 — Nối node bằng fact (đang phát triển)

- Xây dựng cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**,
  thay vì chỉ nối theo quan hệ cấu trúc thô như ở bản 1.0.0 — mỗi cạnh có thể
  truy vết lại đúng fact đã sinh ra nó.
