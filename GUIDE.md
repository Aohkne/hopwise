# Hướng dẫn

## Script crawl dữ liệu

Yêu cầu Python 3.10+; các script chỉ dùng thư viện chuẩn, không cần cài gì
thêm.

```bash
# Điền OPENROUTER_API_KEY hoặc TYPESAFE_API_KEY nếu cần
cp .env.example .env   
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

- `verify_data.py` thoát với mã lỗi khác 0 nếu phát hiện vấn đề - ví dụ node
- `id` trùng, cạnh trỏ tới node không tồn tại, hoặc link ảnh chết. Chạy lại
sau khi sửa.

- Chi tiết từng field, nguồn dữ liệu và hạn chế đã biết: xem
[`data/README.md`](data/README.md).

## Chạy toàn bộ project

`frontend/` và `backend/` **chưa triển khai** (xem [TODO.md](TODO.md)), nên
hiện tại project chỉ dùng được ở mức pipeline dữ liệu như trên. Hướng dẫn
chạy đầy đủ (bật backend, mở frontend) sẽ được bổ sung khi hai phần này
hoàn thiện.
