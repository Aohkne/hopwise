# Dữ liệu nguồn cho Knowledge Graph

Hai domain crawl (`football_vn`, `vinfast`) và một domain trích xuất từ văn bản (`vinfast_policy`, bản 2.0.0) dùng để benchmark khả năng ra quyết định traversal của
**Jev (TypeSafe System One)** so với các LLM khác, trên graph Neo4j.

Dữ liệu của `football_vn` và `vinfast` được **crawl từ API công khai**, không có giá trị nào viết tay (xem `vinfast_policy` bên dưới cho dữ liệu sinh từ văn bản).
Mỗi node đều mang `source`, `source_url`, `crawled_at` để truy vết ngược.

Crawl lần gần nhất: **17/10/2026** (vinfast.json).

## Tạo lại dữ liệu

```bash
python3 scripts/crawl_football.py   # ~8 phút (nhiều lô SPARQL, có sleep giữa các lô)
python3 scripts/crawl_vinfast.py    # ~2 phút (Wikidata + 4 bản 20-F từ SEC)
python3 scripts/verify_data.py      # kiểm tra chất lượng, exit 1 nếu có lỗi
```

Chỉ cần Python 3.10+, không có dependency ngoài thư viện chuẩn.

## Định dạng

```json
{
  "domain": "...", "crawled_at": "...", "sources": [...], "stats": {...},
  "nodes": [ { "id": "Q123_ten_node", "label": "Player", "properties": { ... } } ],
  "edges": [ { "from": "...", "to": "...", "type": "PLAYED_FOR", "properties": {...} } ]
}
```

- `id` = `{QID}_{tên rút gọn}` → `MERGE` vào Neo4j idempotent, chạy lại không tạo trùng.
- `description` = câu mô tả sinh **từ chính các field đã crawl**, không thêm nhận định.
  Đây là phần sẽ đưa vào `state` khi hỏi Jev lúc traversal.
- `_completeness` = tỉ lệ field có dữ liệu (0–1), để lọc node đủ thông tin khi benchmark.

---

## `football_vn.json` — Bóng đá Việt Nam

**Nguồn:** Wikidata SPARQL (CC0) + ảnh từ Wikimedia Commons.

**Phạm vi:** cầu thủ thuộc ĐTQG Việt Nam (`Q270689`) hoặc từng khoác áo CLB
V.League 1 (`Q209080`), cùng CLB, HLV, sân vận động, nơi sinh và danh hiệu.

| Thống kê | Số lượng |
|---|---|
| Node | 3.134 |
| Cạnh | 4.758 |
| Player / Club / Place / Coach / Competition / NationalTeam | 547 / 1.282 / 1.228 / 28 / 48 / 1 |

**Cạnh:** `PLAYED_FOR` (2.970, có `start_year`/`end_year`/`matches` khi Wikidata có),
`HOME_VENUE` (1.056), `BORN_IN` (540), `MEMBER_OF_NATIONAL_TEAM` (137), `WON` (48), `COACHES` (7).

**Độ phủ field:**

| Label | Field | Độ phủ |
|---|---|---|
| Player | `dob` | 547/547 (100%) |
| Player | `position` | 539/547 (98%) |
| Player | `nationality` | 535/547 (97%) |
| Player | `wikipedia_url` | 352/547 (64%) |
| Player | `image_url` | 156/547 (28%) |
| Club | `founded_year` | 1.154/1.282 (90%) |
| Club | `logo_url` | 213/1.282 (16%) |
| Coach | `nationality` | 28/28 (100%) |

---

## `vinfast.json` — VinFast

**Nguồn:** Wikidata (CC0) + **SEC EDGAR** (public domain, CIK `0001913510`): các báo cáo
thường niên **20-F năm tài chính 2023, 2024, 2025** và Exhibit 8.1 của bản 2025
(nộp ngày **30/04/2026**).

Wikidata gần như không có dữ liệu doanh nghiệp VinFast (HĐQT `P3320`/`P169` trống, xe
chỉ có loại xe và ảnh), nên phần lớn graph lấy từ 20-F — nguồn pháp lý chính thức.

| Thống kê | Số lượng |
|---|---|
| Node | 146 (Company 61, CarModel 30, Country 15, Person 10, VehicleClass 8, Place 5, Factory 5, Organization 3, Region 3, Brand 3, ProductLine 3) |
| Cạnh | 225 |

**Cạnh:** SUBSIDIARY_OF 35, MANUFACTURES 33, RELATED_PARTY_OF 28, INCORPORATED_IN 24, SOLD_IN 22, IS_A 20, BELONGS_TO_BRAND 16, LOCATED_IN 10, BOARD_MEMBER_OF 7, SHAREHOLDER_OF 6, PRODUCES 6, OPERATES 5, HAS_BRAND 3, FOUNDED 2, FORMER_BOARD_MEMBER_OF 2, BASED_ON 2, HEADQUARTERED_IN 1, CEO_OF 1, SAME_AS 1, CFO_OF 1.

| Dữ liệu | Nguồn trong 20-F | Node / cạnh |
|---|---|---|
| HĐQT và ban điều hành **qua 3 năm** (có người *từng* là thành viên) | bảng *Directors and Senior Management* của từng bản 20-F | `Person`, `BOARD_MEMBER_OF`, `FORMER_BOARD_MEMBER_OF`, `CEO_OF`, `CFO_OF` |
| 24 công ty con + nơi đăng ký | Exhibit 8.1 | `Company`, `Country`, `SUBSIDIARY_OF`, `INCORPORATED_IN` |
| % sở hữu trực tiếp của 2 công ty con | chú thích sơ đồ cơ cấu | thuộc tính `direct_ownership_pct` (kèm `evidence`) |
| Cổ đông lớn (Vingroup 50,7%, VIG 32,9%, Asian Star 14,3%, ông Phạm Nhật Vượng 97,8%) | bảng *Beneficially Owned* | `SHAREHOLDER_OF` (kèm `shares`, `pct`) |
| 28 công ty bên liên quan (Vinhomes, Vinpearl, VinAI, V-Green...) | bảng *Related parties* | `RELATED_PARTY_OF` (kèm `relationship`) |
| 3 thương hiệu VF / Green / Lạc Hồng | đoạn *"three distinct brands"* | `Brand`, `HAS_BRAND`, `BELONGS_TO_BRAND` |
| Mẫu xe chưa có trên Wikidata (VF MPV 7, VF Wild, Lạc Hồng, dòng Green, EC Van...) + dòng e-bus/e-scooter/e-bike | danh sách gạch đầu dòng `● VF 3 — ...` | `CarModel`, `ProductLine`, `MANUFACTURES` |
| Thị trường bán từng mẫu xe | câu *"currently offer this model in..."* | `SOLD_IN` (kèm `evidence`) |
| Herio Green dựa trên VF 5, Nerio Green dựa trên VF e34 | câu *"developed based on..."* | `BASED_ON` (kèm `evidence`) |
| 5 nhà máy (Hải Phòng, Hà Tĩnh, Subang, Thoothukudi, North Carolina) | mục *Our Properties and Manufacturing Facilities* | `Factory`, `OPERATES`, `LOCATED_IN`, `PRODUCES` |
| Công ty con khác của Vingroup | Wikidata `P749` / `P355` | `Company`, `SUBSIDIARY_OF` |
| Loại xe (sedan, hatchback...) | Wikidata `P31` / `P279` | `VehicleClass`, `IS_A` |

**Hai mức độ tin cậy:**
- **Từ bảng** (HĐQT, công ty con, cổ đông, bên liên quan, Wikidata): trích trực tiếp.
- **Từ văn xuôi** (thương hiệu, thị trường, nhà máy, `BASED_ON`): trích bằng mẫu câu cố
  định, **nguyên văn câu gốc lưu ở thuộc tính `evidence`** để đối chiếu. Mẫu câu không khớp
  (20-F đổi cách viết) thì crawler **dừng với lỗi**, không tự điền.

## `vinfast_policy.json` — Chính sách bán hàng VinFast (trích xuất từ văn bản, bản 2.0.0)

**Nguồn:** không crawl. Graph sinh từ văn bản bằng LLM (gpt-oss-20b qua NVIDIA NIM) theo prompt 3 lớp
[`extract_graph.md`](../backend/app/harness/prompts/templates/extract_graph.md); cách chạy ở
[GUIDE.md](../GUIDE.md#trích-xuất-graph-từ-văn-bản-bản-200). Hiện gồm hai tài liệu mẫu trong
[`docs/research/samples/data/`](../docs/research/samples/data/): đoạn tin `sample.txt` và *Thông báo Chính
sách thúc đẩy bán hàng Ô tô điện VinFast* (mã 20260926).

| Loại | Cách tạo | Ghi chú |
|---|---|---|
| `Organization`, `Product`, `Geo`, `Event`, `Person`, `Program` (node) | Entity có tên riêng trong văn bản | `Entity` nếu model trả loại ngoài danh sách |
| `RELATED_TO` (cạnh) | Relationship nối 2 entity | `description`, `weight` (= độ mạnh 1–10 / 10), `text_unit_ids` |
| `Claim` (node) | Fact có điều kiện / thời gian / trạng thái | `status` (TRUE / FALSE / SUSPECTED), `start_date`, `end_date`, `condition`, `source_text`, `claim_type` |
| `HAS_CLAIM`, `ABOUT` (cạnh) | `Entity -HAS_CLAIM-> Claim -ABOUT-> Entity` | `ABOUT` bỏ qua khi claim không có khách thể |

**Khác dữ liệu crawl:**
- Claim là *node* chứ không phải cạnh: loader dùng `MERGE (a)-[r:TYPE]->(b)`, sẽ gộp mọi cạnh cùng loại
  giữa một cặp node, làm mất các fact như nhiều đợt giảm giá cho cùng một xe.
- `id` entity = `ent_` + tên chuẩn hóa (VD `ent_vf3`), id claim = `claim_` + hash nội dung. Cùng tên
  entity ở hai tài liệu là cùng node; chạy lại cùng tài liệu không tạo trùng.
- **Truy vết:** mọi node/cạnh có `source_docs` (tên file) và `text_unit_ids`; file có `text_units`
  (`chunk_id -> đoạn văn gốc`). Claim có thêm `source_text`, đoạn trích nguyên văn model dẫn.
- Ngày mơ hồ ("cuối năm 2026") giữ nguyên dạng text, chỉ ngày cụ thể mới ở dạng ISO-8601.
- Không có `source_url`, `crawled_at`; thay bằng `extracted_at` ở cấp file. `image_url` không do model
  trích xuất: khi upload, entity có tên trùng một mẫu xe ở `data/vinfast.json` (VD "VF 8" ↔ "VinFast VF 8")
  được gắn `image_url` (bản thu nhỏ 640px) và `image_source` (id node Wikidata) — xem `app/harness/enrich.py`.
  Chỉ khớp đúng tên; entity không khớp thì không có ảnh.

**Hạn chế đã biết:**
- Chất lượng phụ thuộc model. Lần chạy hiện có (2 tài liệu): 60 entity, 45 relationship, 24 claim cho
  thông báo chính sách, trong khi bản trích xuất mẫu do người điền (`docs/research/samples/output/`)
  có 45 / 40 / 59. Nguyên nhân chính: **1 trong 6 đoạn bị cắt cụt** vì gpt-oss dùng hết
  `EXTRACT_MAX_TOKENS` (8192) cho bước suy luận nên đoạn đó không ra claim nào, và 4 record sai định
  dạng bị bỏ (báo cáo của CLI liệt kê từng record). Tăng `EXTRACT_MAX_TOKENS` hoặc giảm
  `EXTRACT_CHUNK_CHARS` rồi chạy lại.
- Relationship chỉ có mô tả, chưa có loại: mọi cạnh là `RELATED_TO`.
- Entity chưa được liên kết với node Wikidata của domain `vinfast` (VD "VF 3" ở hai nơi là hai node khác nhau).
- Còn 9 node không có cạnh (entity được nhắc nhưng model không nối).
- Gộp entity chỉ dựa trên tên đã chuẩn hóa (chữ thường, bỏ khoảng trắng thừa); "VF 3" và "VF3" là hai node.
  Model đôi khi viết **sai chính tả** tên (đã gặp: `ĐẠI LÝ VINFATSH HÀ NỘI`, `PHẦM NHẬT VƯỢNG`), khi đó cùng một
  thực thể thành node thứ hai. Cần bước gộp theo độ giống nhau hoặc LLM (xem TODO) và nên rà lại sau mỗi lần upload.

## Hạn chế đã biết

Ghi rõ để không hiểu nhầm chất lượng dữ liệu:

1. **Logo CLB bóng đá thiếu nhiều** — chỉ 16% CLB có `logo_url`. Logo CLB thường có
   bản quyền, host cục bộ trên Wikipedia chứ không lên Commons nên `P154` trống.
   Trường này **để trống chứ không bịa**. Yêu cầu "logo" chỉ đáp ứng đầy đủ cho VinFast.
2. **Ảnh cầu thủ chỉ 28%** — Wikidata đơn giản là chưa có ảnh cho phần lớn cầu thủ VN.
3. **Chỉ 7 cạnh `COACHES`** — property `P6087` (coach of sports team) rất ít được điền
   cho bóng đá VN; `P286` (head coach) thì trống hoàn toàn. Đây là giới hạn của Wikidata,
   không phải lỗi crawl. 28 node Coach vẫn có đủ thông tin cá nhân.
4. **Thành tựu chỉ ở cấp CLB/đội tuyển** (`WON`, 48 cạnh) — danh hiệu cá nhân của cầu thủ
   (VD Quả bóng vàng VN) không tồn tại dạng structured trên Wikidata, chỉ nằm ở mục
   "Danh hiệu" dạng văn xuôi trên Wikipedia. Đã quyết định **không parse văn xuôi** để
   giữ độ chính xác tuyệt đối.
5. **1.282 CLB gồm cả CLB nước ngoài** mà cầu thủ trong phạm vi từng đầu quân. Giữ lại
   vì làm graph phong phú hơn cho traversal; lọc bằng `in_vleague1: true` (26 CLB) nếu cần.
6. **547 cầu thủ gồm cả ngoại binh** đang thi đấu V.League. Lọc bằng field `nationality`.
7. **2 node không có tên** (`Q20548442`, `Q48956636`) — Wikidata không có nhãn ở bất kỳ
   ngôn ngữ nào cho 2 entity này. Giữ QID làm tên.
8. **Người vừa là cầu thủ vừa là HLV** được giữ làm 1 node `Player` kèm cờ `also_coach: true`
   thay vì tách đôi.
9. **VinFast — văn xuôi 20-F có thể mâu thuẫn nhau**: Hải Phòng ghi "khánh thành 2019" ở mục
   nhà máy nhưng "2018" ở mục tổng quan. Crawler lấy theo mục nhà máy, `evidence` giữ câu gốc.
10. **VinFast — `VF e34` và `VinFast VF31` có thể là một**: Wikidata đặt tên `VF31` cho
    entity có ảnh VF e34, còn 20-F gọi là `VF e34`. Chưa gộp vì không có bằng chứng chắc chắn.
11. **VinFast — Nerio Green, VF e34 chỉ có tên + phân khúc**: 20-F không có mục mô tả riêng.
12. **VinFast — chỉ 2/24 công ty con có `direct_ownership_pct`**: sơ đồ cơ cấu của 20-F là
    hình ảnh, chỉ có 2 công ty được nêu % trong chú thích.
13. **Dữ liệu Wikidata do cộng đồng đóng góp** → có thể lỗi thời hoặc thiếu. Mọi node giữ
   `wikidata_id` để đối chiếu lại.

## Kiểm chứng đã thực hiện

-  Không có node `id` trùng; mọi cạnh đều trỏ tới node tồn tại; không có cạnh trùng lặp.
-  Mọi node đều có `description` và `source`.
-  **30/30 link ảnh mẫu ngẫu nhiên trả HTTP 200** (đã sửa bug double-encoding `%2520`).
-  Đối chiếu thủ công 5 cầu thủ ngẫu nhiên: ngày sinh khớp 100% với Wikidata gốc.
-  Đối chiếu HĐQT VinFast với bảng gốc trong 20-F: khớp cả 7 người (tên, tuổi, chức danh).
-  Đối chiếu số liệu VinFast mở rộng với 20-F FY2025: tỷ lệ cổ phần 4 cổ đông, công suất nhà máy
   Hà Tĩnh/Subang/Hải Phòng/Thoothukudi, thị trường của VF 6, % sở hữu 2 công ty con, HĐQT 2023 — khớp.

## Giấy phép

| Nguồn | Giấy phép |
|---|---|
| Wikidata | CC0 (public domain) |
| Wikimedia Commons (ảnh) | Tuỳ từng file — kiểm tra trang file trước khi dùng lại công khai |
| SEC EDGAR | Public domain (tài liệu chính phủ Mỹ) |

Data chỉ lưu **URL ảnh**, không tải ảnh về.
