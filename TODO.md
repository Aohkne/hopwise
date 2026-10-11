# Việc chưa làm

Khung thư mục của `backend/`, `frontend/`, Docker và CI đã dựng xong (chạy
được, build được, test pass) — xem [GUIDE.md](GUIDE.md). Logic nghiệp vụ
bên trong vẫn chưa triển khai, liệt kê dưới đây.

## Hoàn thiện bản 1.0.0

- [ ] **Loader Neo4j** — nạp `data/*.json` vào Neo4j bằng `MERGE` theo `id`,
  chạy lại nhiều lần không tạo trùng.
- [ ] **Bộ test-case ground truth** — mỗi test case gồm câu hỏi, node xuất
  phát, đường đi đúng kỳ vọng và đáp án đúng, cho cả hai domain hiện có.
- [ ] **`backend/app/services/decision_models/jev.py`** — gọi OpenRouter
  `/alpha/decisions` thật (format request/response đã biết, xem docstring
  trong file).
- [ ] **`backend/app/services/decision_models/kev.py`** — gọi server Kev
  local (`POST /v1/systemone`).
- [ ] **`backend/app/services/decision_models/llm.py`** — convert
  `questions` thành prompt tự nhiên cho LLM thường, parse JSON trả về.
- [ ] **`backend/app/services/traversal.py`** — thuật toán traversal: điều
  kiện dừng, beam search (`BEAM_WIDTH`), giới hạn `MAX_HOPS`.
- [ ] **`backend/app/routers/decisions.py` và `benchmark.py`** — hiện trả
  `501`, cần nối với `traversal.py` khi logic trên xong.
- [ ] **Frontend**: `GraphView.tsx` hiển thị graph thật, `Dashboard.tsx` cho
  chọn domain + chạy benchmark, `BenchmarkResult.tsx` hiển thị bảng/biểu đồ
  so sánh — hiện cả ba chỉ là placeholder gọi `TODO` trong code.
- [ ] **Biểu đồ benchmark** — vẽ bằng TikZ, xuất ảnh, nhúng vào phần "Đóng
  góp" của README.md.
- [ ] **Tài liệu xây Knowledge Graph** — giải thích cách các node quan hệ
  với nhau trong `data/football_vn.json` và `data/vinfast.json`: loại node,
  loại cạnh, và vì sao chọn Wikidata/SEC làm nguồn.

## Bản 2.0.0

- [ ] Cơ chế tạo cạnh giữa hai node dựa trên **một fact cụ thể**, có thể
  truy vết lại nguồn — thay cho cách nối theo quan hệ cấu trúc thô hiện tại
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`...).

## Khác

- [ ] Chọn license chính thức cho mã nguồn.
