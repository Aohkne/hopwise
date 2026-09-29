# Dữ liệu nguồn cho Knowledge Graph

Hai domain tiếng Việt dùng để benchmark khả năng ra quyết định traversal của
**Jev (TypeSafe System One)** so với các LLM khác, trên graph Neo4j.

Toàn bộ dữ liệu được **crawl từ API công khai**, không có giá trị nào viết tay.
Mỗi node đều mang `source`, `source_url`, `crawled_at` để truy vết ngược.

Crawl lần gần nhất: **28/09/2026**.

## Tạo lại dữ liệu

```bash
python3 scripts/crawl_football.py   # ~8 phút (nhiều lô SPARQL, có sleep giữa các lô)
python3 scripts/crawl_vinfast.py    # ~1 phút
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

**Nguồn:** Wikidata `Q56660561` (CC0) + **SEC EDGAR 20-F** (public domain, CIK `0001913510`,
bản nộp ngày **30/04/2026**).

Wikidata **không có** dữ liệu hội đồng quản trị VinFast (`P3320`, `P169` đều trống),
nên HĐQT lấy từ mục *"Directors and Senior Management"* trong báo cáo thường niên
20-F nộp cho SEC — nguồn pháp lý chính thức, chính xác hơn mọi bài báo.

| Thống kê | Số lượng |
|---|---|
| Node | 32 (Company 1, Person 8, CarModel 21, Organization 1, Place 1) |
| Cạnh | 33 |

**Cạnh:** `MANUFACTURES` (21), `BOARD_MEMBER_OF` (7), `SUBSIDIARY_OF`, `HEADQUARTERED_IN`,
`FOUNDED`, `CEO_OF`, `SAME_AS` (mỗi loại 1).

**Dữ liệu công ty:** thành lập 06/2017 · trụ sở Hải Phòng · công ty mẹ Vingroup ·
website vinfastauto.com · niêm yết Nasdaq mã VFS · **3 link logo SVG** (đã kiểm tra sống).

**HĐQT (từ 20-F 2026):** Pham Nhat Vuong (Managing Director & CEO), Le Thi Thu Thuy
(Chairwoman), Ling Chung Yee Roy (Independent), Tham Chee Soon (Independent),
Nguyen Thi Van Trinh, Nguyen Thi Lan Anh (Director & CFO), Pham Nhat Quan Anh —
6/7 người có kèm tiểu sử trích từ chính báo cáo.

---

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
9. **Dữ liệu Wikidata do cộng đồng đóng góp** → có thể lỗi thời hoặc thiếu. Mọi node giữ
   `wikidata_id` để đối chiếu lại.

## Kiểm chứng đã thực hiện

- ✅ Không có node `id` trùng; mọi cạnh đều trỏ tới node tồn tại; không có cạnh trùng lặp.
- ✅ Mọi node đều có `description` và `source`.
- ✅ **30/30 link ảnh mẫu ngẫu nhiên trả HTTP 200** (đã sửa bug double-encoding `%2520`).
- ✅ Đối chiếu thủ công 5 cầu thủ ngẫu nhiên: ngày sinh khớp 100% với Wikidata gốc.
- ✅ Đối chiếu HĐQT VinFast với bảng gốc trong 20-F: khớp cả 7 người (tên, tuổi, chức danh).

## Giấy phép

| Nguồn | Giấy phép |
|---|---|
| Wikidata | CC0 (public domain) |
| Wikimedia Commons (ảnh) | Tuỳ từng file — kiểm tra trang file trước khi dùng lại công khai |
| SEC EDGAR | Public domain (tài liệu chính phủ Mỹ) |

Data chỉ lưu **URL ảnh**, không tải ảnh về.
