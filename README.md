# Hopwise

> Liệu có thể dạy một mô hình quyết định đi đúng đường trên một Knowledge Graph, nhanh và rẻ hơn một LLM thông thường, mà vẫn chính xác không kém?

**Hopwise** là một thử nghiệm xoay quanh câu hỏi đó. Ý tưởng cốt lõi:
**Jev** — mô hình "System One" của TypeSafe, trả về quyết định có kiểu kèm xác suất thay vì sinh văn bản — để truy vấn một **Knowledge Graph**. Ở mỗi node, model được hỏi *"cạnh nào nên đi tiếp để tìm thông tin trả lời câu hỏi?"*, và quyết định đó được so sánh với việc giao hẳn câu hỏi cho một LLM
thông thường (GPT, Claude, Gemini...) trên cùng bài toán — đối chiếu độ chính xác, tốc độ phản hồi và chi phí giữa hai cách tiếp cận.

## Đóng góp

| Nội dung | Trạng thái |
|---|---|
| Bộ dữ liệu Knowledge Graph crawl từ nguồn thật (Wikidata, SEC EDGAR) |  Có sẵn trong `data/` |
| Biểu đồ benchmark Jev so với các LLM khác (vẽ bằng TikZ, xuất ảnh) |  Chưa triển khai — xem [TODO.md](TODO.md) |
| Hướng dẫn xây một Knowledge Graph — cách các node quan hệ với nhau |  Chưa có trong bản này — xem [TODO.md](TODO.md) |

## Cấu trúc dự án

```
data/                   Knowledge Graph đã crawl (Wikidata, SEC EDGAR)
scripts/                Script crawl và kiểm tra dữ liệu
skills/typesafe-ai/     Tài liệu tham khảo để build với TypeSafe/Jev
frontend/               React + Tailwind + Iconify, phong cách neo-brutalism — chưa triển khai
backend/                API phục vụ frontend — chưa triển khai
.env.example            Mẫu biến môi trường (OpenRouter, TypeSafe, Kev, Neo4j)
```

## Tài liệu

| File | Nội dung |
|---|---|
| [GUIDE.md](GUIDE.md) | Cách chạy script và chạy toàn bộ project |
| [VERSION.md](VERSION.md) | Lộ trình các phiên bản |
| [TODO.md](TODO.md) | Những phần đã lên kế hoạch nhưng chưa có code |

## License

Mã nguồn: chưa chọn license chính thức. Dữ liệu trong `data/`: xem
[`data/README.md`](data/README.md) (Wikidata CC0, SEC EDGAR public domain).
