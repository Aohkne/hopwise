# Hopwise

Benchmarking typed-decision models (Jev, Kev) against LLMs on knowledge-graph
traversal — which node to visit, which edge to follow — measured on hand-built
Vietnamese-domain graphs in Neo4j.

## Ý tưởng

[TypeSafe's Jev](https://typesafe.ai) là một "System One model": thay vì sinh
văn bản như LLM thường, nó nhận vào `state` + một tập câu hỏi có kiểu
(`Choice` / `Score` / `Noul`) và trả về quyết định kèm xác suất đã hiệu chỉnh.
Project này thử dùng Jev (và [Kev](https://github.com/jaredpalmer/kev) — bản
mã nguồn mở tương thích API, chạy free) làm "bộ não" quyết định đường đi khi
truy vấn một Knowledge Graph: ở mỗi node, hỏi model "cạnh nào nên đi tiếp để
tìm thông tin trả lời câu hỏi?", rồi so sánh độ chính xác/tốc độ/chi phí với
việc dùng LLM thông thường (GPT, Claude, Gemini...) cho cùng quyết định.

## Cấu trúc

```
data/                 Dữ liệu đồ thị (node/edge) crawl từ Wikidata + SEC EDGAR
  football_vn.json      Bóng đá Việt Nam: ĐTQG + V.League 1
  vinfast.json           VinFast: công ty, HĐQT, model xe
  README.md              Nguồn, độ phủ field, hạn chế đã biết
scripts/
  wikidata_client.py    Helper SPARQL/Commons dùng chung
  crawl_football.py     Crawl domain bóng đá
  crawl_vinfast.py      Crawl domain VinFast (+ parse HĐQT từ SEC 20-F)
  verify_data.py        Kiểm tra toàn vẹn graph + link ảnh sống
skills/typesafe-ai/     Skill hướng dẫn build với TypeSafe (tài liệu tham khảo)
.env.example           Biến môi trường cần thiết (OpenRouter, TypeSafe, Kev, Neo4j)
```

## Bắt đầu

```bash
cp .env.example .env   # điền OPENROUTER_API_KEY hoặc TYPESAFE_API_KEY

python3 scripts/crawl_football.py
python3 scripts/crawl_vinfast.py
python3 scripts/verify_data.py
```

Xem `data/README.md` để biết chi tiết nguồn dữ liệu, độ phủ từng field, và
những hạn chế đã biết (ví dụ: logo CLB bóng đá không có sẵn public domain).

## Trạng thái

- [x] Crawl + verify dữ liệu 2 domain (bóng đá VN, VinFast)
- [ ] Loader Neo4j từ JSON
- [ ] Bộ test-case ground truth cho traversal
- [ ] Harness so sánh Jev / Kev / LLM

## License

Mã nguồn trong repo: chưa chọn license chính thức. Dữ liệu trong `data/`:
xem `data/README.md` (Wikidata CC0, SEC EDGAR public domain).
