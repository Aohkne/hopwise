# Ground truth cho benchmark

Bộ câu hỏi + đáp án đúng để chấm Jev và LLM. **Không có câu hỏi hay đáp án nào viết
tay**: mọi thứ được sinh từ `data/*.json` theo các mẫu trong `templates.py`.

```bash
python3 benchmarks/generate_cases.py --preview   # xem 60 câu, không ghi file
python3 benchmarks/generate_cases.py             # ghi benchmarks/cases/*.json
python3 benchmarks/verify_cases.py               # kiểm tra, exit 1 nếu có lỗi (chạy trong CI)
```

Chỉ cần Python 3.10+, không có thư viện ngoài. Cùng graph + cùng `--seed` thì luôn ra cùng
bộ câu hỏi. **Crawl lại dữ liệu thì phải sinh lại**, `verify_cases.py` sẽ báo lỗi nếu quên.

## Cách một câu được tạo

Mỗi mẫu = một node neo + một chuỗi cạnh cố định. Ví dụ `v_made_country`:

```
Mẫu xe {VF 6} --(sản xuất bởi)--> Nhà máy --(đặt tại)--> Địa điểm --(thuộc)--> Quốc gia
"Mẫu xe VF 6 được sản xuất ở nhà máy thuộc quốc gia nào?"   ->   Ấn Độ
```

Câu chỉ được giữ khi **mỗi bước đi đều ra đúng 1 thực thể** (đáp án duy nhất và tính ra
được từ graph), và qua các kiểm tra:

- tên node neo không trùng thực thể nào khác trong domain, tên đáp án cũng vậy
- câu hỏi **không chứa tên đáp án** (kể cả tên tiếng Anh/viết tắt)
- đường đi không quay về node cũ
- không chứa node trong `EXCLUDED_NODES` (người duyệt đã loại, kèm lý do)

Các node trùng nhau qua cạnh `SAME_AS` (VD ông Phạm Nhật Vượng có node Wikidata và node SEC)
được coi là **một** thực thể; mọi node đó đều nằm trong `answers`.

## Một test case

```json
{
  "id": "vinfast-030",
  "question": "Mẫu xe VF 6 được sản xuất ở nhà máy thuộc quốc gia nào?",
  "answers": ["Q881_country_ấn_độ"],
  "answer_text": "Ấn Độ",
  "hops": 3,
  "tags": ["incoming-edge"],
  "template": "v_made_country",
  "anchors": ["Q..._vinfast_vf_6"],
  "reference_path": [{"node": "...", "edge": null}, {"node": "...", "edge": "PRODUCES (in)"}]
}
```

| Trường | Dùng để |
|---|---|
| `answers` | **chấm điểm**: đúng khi node model trả về nằm trong danh sách (các node cùng một thực thể) |
| `answer_text`, `id`, `question` | hiển thị, khoá câu, nội dung đưa cho model |
| `hops`, `tags` | báo cáo theo độ khó. `tags`: `incoming-edge`, `hub-node`, `edge-filter`, `former` |
| `template`, `anchors`, `params` | để `verify_cases.py` dựng lại câu và phát hiện lệch |
| `reference_path` | đường đi ngắn nhất theo graph, **không dùng để chấm** |

Đầu file ghi `graph.crawled_at` và số node/cạnh của graph lúc sinh.

## Giới hạn cần biết

- **Thế giới đóng:** "đáp án duy nhất" nghĩa là duy nhất *trong knowledge base*, vì
  benchmark cho model chỉ dùng KB. "Cầu thủ nào từng thi đấu cho câu lạc bộ X?" có đáp án
  vì KB chỉ có một cầu thủ của X, dù ngoài đời X có nhiều cầu thủ.
- **Football:** nhiều câu về câu lạc bộ/cầu thủ nước ngoài, vì graph có 1.282 CLB và chỉ
  26 là V.League 1. Mỗi mẫu ưu tiên câu gắn với Việt Nam trước.
- **VinFast:** graph nhỏ (146 node) nên bộ 30 câu lặp nhiều quan hệ địa lý (nhà máy, quốc gia,
  công ty đăng ký). Thêm dữ liệu thì thêm được mẫu mới.
- **Mẫu `v_incorp_parent`** luôn ra đáp án VinFast (mọi công ty con trực tiếp đều là con
  của VinFast) nên câu này dễ đoán.
- Chỉ **một node đáp án** mỗi câu; chưa có câu hỏi dạng liệt kê hay hỏi thuộc tính (tuổi,
  công suất).

## Lưu ý từ bản 2.0.0

Domain `vinfast_policy` (graph sinh từ văn bản, xem [GUIDE.md](../GUIDE.md)) **không nằm trong bộ 60
câu**: câu hỏi và đáp án vẫn sinh từ `data/football_vn.json` và `data/vinfast.json`. Tuy nhiên khi
domain này đã nạp vào Neo4j, bước "chọn domain" của model có thêm một lựa chọn thứ ba, nên chạy
lại 60 câu có thể cho kết quả khác chút so với `results/2026-10-18/` (chạy khi Neo4j chưa nạp
`vinfast_policy`). Muốn so sánh công bằng với kết quả cũ, chạy benchmark trước khi nạp domain mới.
