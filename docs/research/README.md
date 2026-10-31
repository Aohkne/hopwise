# Nghiên cứu: xây Knowledge Graph từ văn bản

> **Đây là tài liệu nghiên cứu, không phải code chạy.** Nó là nền tảng cho bản 2.0.0
> ("nối node bằng fact", xem [VERSION.md](../../VERSION.md)). Phần triển khai nằm ở
> `backend/app/harness/`.

| File | Nội dung |
|---|---|
| [research_graph-build.md](research_graph-build.md) | Kết quả nghiên cứu: định nghĩa Entity, Qualifier, Relationship vs Claim, prompt trích xuất 3 lớp |
| [research-todo.md](research-todo.md) | Danh sách câu hỏi nghiên cứu đã trả lời (phần "Framework & Tham khảo" vẫn chưa điền) |
| [samples/data/](samples/data/) | Văn bản mẫu để thử trích xuất (`sample.txt`, thông báo chính sách VinFast 09/2026) |
| [samples/output/](samples/output/) | Kết quả trích xuất mẫu do một LLM điền theo prompt, dùng làm fixture cho test của parser |

Prompt đã kiểm chứng (v2) nằm ở
[`backend/app/harness/prompts/templates/extract_graph.md`](../../backend/app/harness/prompts/templates/extract_graph.md)
và được code đọc trực tiếp lúc chạy. Các file mẫu trong `samples/output/` còn nhắc tới đường dẫn cũ
(`prompt.md`, `data/sample.txt`) — giữ nguyên như lúc nghiên cứu.

## Nghiên cứu → code

| Quyết định trong nghiên cứu | Triển khai ở bản 2.0.0 |
|---|---|
| Entity là node có tên riêng; giá trị (30%, ngày) là thuộc tính | Entity → node (`Organization`, `Product`, `Geo`, `Event`, `Person`, `Program`) |
| Relationship nối đúng 2 entity, có `weight` và `text_unit_ids` | Cạnh `RELATED_TO` {`description`, `weight`, `text_unit_ids`} |
| Claim = relationship + trạng thái đúng/sai + điều kiện/thời gian | Node `Claim` nối bằng `HAS_CLAIM` / `ABOUT` |
| Provenance: truy về chunk gốc | `text_unit_ids`, `source_text` và `text_units` trong file JSON |
| Dedupe entity/relationship/claim từ nhiều chunk | Gộp bằng code (`harness/extract.py`) |
