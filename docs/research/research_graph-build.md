# Research - Graph Build

> Tài liệu tổng hợp kết quả nghiên cứu. Chỉ điền nội dung khi đã nghiên cứu xong và được duyệt.

## Entity:

### Định nghĩa (3 điều kiện)

- ① **Tên thật** — có trong nguồn chính thức, không phải tên bịa
- ② **Chụp được** — có ảnh/đối tượng của chính nó, không phải khái niệm
- ③ **Cụ thể nhất** — không còn tên loại con bên dưới

### Bổ sung (từ nghiên cứu)

- **Entity vs Value:** Entity là node độc lập; Value là giá trị mô tả (30%, ngày)
- **Entity vs TAG:** TAG là tính chất (màu đỏ, ban đêm), không vào danh mục entity
- **Nâng cấp Value → Entity** khi cần query/traversal theo chính nó
- **Type + Group:** ontology 2 tầng (type chi tiết + group thô 9 loại)
- **Vòng đời:** staged → active → closed (đóng valid_to, KHÔNG xóa)
- **Alias:** tên tiếng Anh/viết tắt/tên cũ → aliases[], không tạo entity mới
- **Chống tên bịa:** tuyệt đối không để AI tự liệt kê, phải có nguồn xác thực

### Trường (field) của Entity

| Trường | Loại | Ý nghĩa | Ví dụ |
|---|---|---|---|
| `id` | str | Định danh duy nhất | `vf3` |
| `name` | str | Tên chính (tên thật trong nguồn) | `VF3` |
| `type` | str | Loại chi tiết (cũng là tên file) | `vehicle_model` |
| `group` | str | Nhóm thô, 1 trong 9 | `product-model` |
| `description` | str | Mô tả từ nguồn đã dẫn (bắt buộc) | `Xe điện hatchback cỡ nhỏ của VinFast` |
| `valid_from` | str | Ngày bắt đầu hiệu lực | `2024-01-01` |
| `valid_to` | str/null | Ngày đóng (null = còn hoạt động) | `null` |
| `lifecycle.status` | str | Trạng thái: staged/active/closed | `active` |
| `aliases[]` | list | Tên tiếng Anh/viết tắt/tên cũ | `[{kind: "abbr", name: "VF 3"}]` |
| `sources[]` | list | Nguồn xác thực, có `verified_at` | `[{verified_at: "2024-01-01"}]` |
| `domain_owner` | str | Chủ sở hữu entity (một chủ) | `vinfast` |
| `anchor` | str | Khóa neo chống trùng (MST/tọa độ/mã) | `model_code: VF3` |
| `attributes` | dict | Thuộc tính tự do | `{seats: 5, range: 210}` |
| `visual_desc` | str | Nhận diện trong ảnh (auto-tag) | `Hatchback đỏ, đầu nhọn` |
| `redirects[]` | list | ID cũ khi gộp trùng (không xóa) | `[{from: "vf3_old"}]` |

### Ví dụ record hoàn chỉnh

```json
{
  "id": "vf3",
  "name": "VF3",
  "type": "vehicle_model",
  "group": "product-model",
  "description": "Xe điện hatchback cỡ nhỏ của VinFast, tham gia chương trình ưu đãi mùa xuân giảm 30%",
  "valid_from": "2024-01-01",
  "valid_to": null,
  "lifecycle.status": "active",
  "aliases": [{"kind": "abbr", "name": "VF 3"}],
  "sources": [{"verified_at": "2024-01-01"}],
  "domain_owner": "vinfast",
  "anchor": "model_code: VF3",
  "attributes": {"seats": 5, "range_km": 210}
}
```

## Qualifier:

### 1. Định nghĩa

**Qualifier = thông tin bổ sung gắn lên một edge, mà nếu bỏ đi thì nghĩa của edge đó SAI/THAY ĐỔI.**

> Tiêu chí quyết định: **Bỏ qualifier đi → fact sai phạm vi** → đó là qualifier.
> Bỏ đi mà fact vẫn đúng → đó KHÔNG phải qualifier.

### 2. Nơi lưu trữ

| Trường hợp | Quyết định | Lý do |
|---|---|---|
| **Mặc định** | Qualifier là **property trên edge** | Đơn giản, query nhanh, đúng bản chất |
| **Phức tạp** | Reify edge thành **node** | Khi cần query sâu theo chính qualifier đó |

### 3. Áp dụng cho case VF3

```cypher
(VF3:PRODUCT)-[:DISCOUNT {
    value: "30%",
    valid_from: "2026-01-15",   ← qualifier (thời gian)
    valid_to: "2026-01-20",     ← qualifier (thời gian)
    condition: "mua xe"         ← qualifier (điều kiện)
}]->(UudaiMuaXuan:PROMOTION)
```

### 4. Khi nào reify (biến edge → node)?

**Chỉ reify khi thỏa 1 trong 3:**
- Cần query/traverse theo chính qualifier đó (vd: "tìm mọi xe giảm giá trong T1/2026")
- Một qualifier được chia sẻ bởi nhiều edge
- Qualifier tự nó có qualifier con (hiếm)

**Ngược lại:** giữ làm property trên edge.

### 5. Schema chốt cho Qualifier

| Field | Loại | Ví dụ |
|---|---|---|
| `valid_from` | date | 2026-01-15 |
| `valid_to` | date/null | 2026-01-20 |
| `condition` | str | "mua xe" |
| `excludes` | str[] | (loại trừ, nếu có) |
| `method` | str | (cách xác định, nếu có) |

## Relationship / Claim:

### Relationship (quan hệ)

**Định nghĩa:**

> **Relationship = một phát biểu nối 2 node (entity) lại với nhau**, diễn tả quan hệ có hướng giữa chúng. Bản chất = **RDF triple**: `subject → predicate → object`. Là **cạnh (edge)** trong graph.

```
VF3 ──[PARTICIPATES_IN]──> Chương trình ưu đãi mùa xuân
```

**Điều kiện (khi nào được coi là 1 relationship):**

| # | Điều kiện | Ví dụ đạt | Ví dụ trượt |
|---|---|---|---|
| ① | **Có 2 node** để nối | VF3 + Chương trình | Chỉ có VF3 (1 node) |
| ② | **Có hướng** xác định | VF3 → Chương trình | Không rõ chiều |
| ③ | **Diễn tả quan hệ có nghĩa** | "VF3 giảm giá cho Chương trình" | "VF3 màu đỏ" (thuộc tính) |

> ⚠️ **Lưu ý:** Nếu chỉ có **1 node** + mô tả (màu đỏ, giá 300 triệu) → đó là **property/attribute**, KHÔNG phải relationship.

**Các trường chứa:**

| Trường | Loại | Ý nghĩa | Ví dụ |
|---|---|---|---|
| `source` | node | Node nguồn | `VF3` |
| `target` | node | Node đích | `Chương trình ưu đãi` |
| `type` | str | Loại quan hệ | `PARTICIPATES_IN`, `DISCOUNT` |
| `description` | str | Mô tả quan hệ | "VF3 tham gia chương trình" |
| `weight` | float | Độ mạnh (0-1) | `0.9` |
| `text_unit_ids` | str[] | Nguồn chunk (provenance) | `[chunk_123]` |

---

### Claim (phát biểu có kiểm chứng)

**Định nghĩa:**

> **Claim = một relationship được bổ sung trạng thái đúng/sai và ngữ cảnh**, dùng khi phát biểu đó **cần được kiểm chứng** (có thể ĐÚNG/SAI/Nghi ngờ). GraphRAG dùng "claim" vì LLM có thể hallucinate → cần trường `status` để xác thực.

```
VF3 ──[CLAIM]──> "được giảm 30%"
        │
        ├─ status: TRUE / FALSE / SUSPECTED
        ├─ start_date: 15/01/2026
        └─ end_date: 20/01/2026
```

> **Mối quan hệ:** Claim thực chất là **relationship + metadata kiểm chứng**.

**Điều kiện (khi nào được coi là 1 claim):**

| # | Điều kiện | Ví dụ |
|---|---|---|
| ① | Phát biểu **cần kiểm chứng đúng/sai** | "VF3 giảm 30%" (có thể đúng/sai) |
| ② | Cần lưu **trạng thái** (TRUE/FALSE/SUSPECTED) | Phát hiện tin giả, fraud |
| ③ | Có **nhiều nguồn mâu thuẫn** | Nguồn A: giảm 30%, nguồn B: 25% |

> ⚠️ **Ngược lại:** Nếu phát biểu **hiển nhiên đúng** (không cần kiểm chứng) → dùng **relationship thuần**, không cần claim.

**Các trường chứa:**

| Trường | Loại | Ý nghĩa | Ví dụ |
|---|---|---|---|
| `subject_id` | node | Entity thực hiện | `VF3` |
| `object_id` | node | Entity bị tác động | `Chương trình` |
| `type` | str | Loại phát biểu | `DISCOUNT_CLAIM` |
| `description` | str | Nội dung phát biểu | "VF3 được giảm 30%" |
| `status` | str | Trạng thái đúng/sai | `TRUE` / `FALSE` / `SUSPECTED` |
| `start_date` | date | Ngày bắt đầu | `2026-01-15` |
| `end_date` | date | Ngày kết thúc | `2026-01-20` |
| `source_text` | str | Đoạn văn chứa claim | "VF3 giảm 30%..." |
| `text_unit_id` | str | ID chunk nguồn | `chunk_123` |

---

### Ví dụ tổng hợp

**Relationship thuần (hiển nhiên đúng):**
```cypher
(VF3:PRODUCT)-[:PARTICIPATES_IN {
    description: "VF3 tham gia chương trình ưu đãi mùa xuân",
    weight: 0.9,
    text_unit_ids: ["chunk_123"]
}]->(UudaiMuaXuan:PROMOTION)
```

**Claim (cần kiểm chứng):**
```cypher
(VF3:PRODUCT)-[:HAS_CLAIM]->(c:Claim {
    type: "DISCOUNT_CLAIM",
    description: "VF3 được giảm 30% trong chương trình ưu đãi mùa xuân",
    status: "TRUE",
    start_date: "2026-01-15",
    end_date: "2026-01-20",
    source_text: "Khi mua xe VF3... giảm 30%...",
    text_unit_id: "chunk_123"
})-[:ABOUT]->(UudaiMuaXuan:PROMOTION)
```

### Tóm tắt

| Khái niệm | Số node | Trạng thái đúng/sai | Dùng khi |
|---|---|---|---|
| **Relationship** | 2 | Không cần | Hiển nhiên đúng |
| **Claim** | 1-2 | Bắt buộc (TRUE/FALSE/SUSPECTED) | Cần kiểm chứng |

## Prompt Extraction:

### 1. Prompt trích xuất Entity + Relationship (GraphRAG)

GraphRAG dùng **một prompt duy nhất** trích xuất cả entity lẫn relationship theo format tuple:

```
("entity"<|>TÊN<|>LOẠI<|>MÔ_TẢ)
("relationship"<|>NGUỒN<|>ĐÍCH<|>MÔ_TẢ<|>ĐỘ_MẠNH)
```

**Cấu trúc prompt:**
- **-Goal-**: mục tiêu (xác định entity + relationship)
- **-Steps-**: 3 bước (entity → relationship → output)
- **-Examples-**: few-shot (3 ví dụ mẫu)
- **-Real Data-**: `{entity_types}`, `{input_text}`

**Đặc điểm:**
- Output dạng **tuple phân cách** bằng `<|>` và `##`
- Có `relationship_strength` (score 1-10)
- Kết thúc bằng `<|COMPLETE|>`

### 2. Prompt trích xuất Claim (GraphRAG)

Claim prompt phức tạp hơn, có thêm **trạng thái đúng/sai**:

```
(<subject><|><object><|><claim_type><|><claim_status><|><start_date><|><end_date><|><description><|><source_text>)
```

**Khác biệt chính:**
- `claim_status`: **TRUE/FALSE/SUSPECTED**
- `claim_date`: khoảng thời gian (ISO-8601)
- `claim_source_text`: trích dẫn gốc từ văn bản

### 3. Vấn đề với prompt GraphRAG gốc

Prompt gốc **chỉ tách 2 lớp** (entity + relationship), **không tách fact có điều kiện**. Với case:

```
"Khi mua xe VF3 trong chương trình ưu đãi mùa xuân (15-20/01) thì giảm 30%"
```

Prompt gốc chỉ ra:
```
("relationship"<|>VF3<|>CHƯƠNG TRÌNH<|>VF3 giảm 30% trong chương trình<|>8)
```
→ **Mất thông tin**: thời gian (15-20/01), điều kiện (mua xe)

### 4. Giải pháp: Prompt 3 lớp

Cần prompt tách **3 lớp riêng biệt**:

| Lớp | Prompt hỏi | Output |
|---|---|---|
| **1. Entity** | "Xác định tất cả entity" | `("entity"<|>VF3<|>PRODUCT<|>...)` |
| **2. Relationship** | "Xác định quan hệ giữa các entity" | `("relationship"<|>VF3<|>CT<|>...<|>strength)` |
| **3. Claim/Fact** | "Xác định fact có điều kiện/thời gian" | `("claim"<|>VF3<|>CT<|>DISCOUNT<|>TRUE<|>15/01<|>20/01<|>mua xe<|>30%)` |

### 5. Best practices cho prompt extraction

| Kỹ thuật | Mục đích |
|---|---|
| **Few-shot examples** | Giảm hallucination, chuẩn hóa format |
| **Chain-of-Thought** | "Hãy phân tích từng bước trước khi kết luận" |
| **Entity types đóng** | Giới hạn `{entity_types}` để chuẩn hóa |
| **Output format cứng** | Tuple với delimiter cố định |
| **Merge + dedupe** | Prompt riêng để gộp fact trùng từ nhiều chunk |

### 6. Prompt merge + dedupe

Sau khi extract từ nhiều chunk, cần prompt **tổng hợp**:
- Gộp các entity cùng tên → 1 entity
- Gộp các relationship cùng cặp → 1 relationship
- Loại bỏ fact trùng lặp

### 7. Ví dụ prompt 3 lớp (tham khảo)

```
-Goal-
Trích xuất entity, relationship, và claim từ văn bản.

-Steps-
1. Xác định entity: ("entity"<|>tên<|>loại<|>mô_tả)
2. Xác định relationship: ("relationship"<|>nguồn<|>đích<|>mô_tả<|>độ_mạnh)
3. Xác định claim có điều kiện: ("claim"<|>chủ_thể<|>khách_thể<|>loại<|>trạng_thái<|>ngày_bđ<|>ngày_kt<|>mô_tả<|>nguồn)

-Real Data-
Entity_types: [PRODUCT, PROMOTION, PERSON]
Text: {input_text}
Output:
```

### Tóm tắt

| Prompt | Lớp | Output |
|---|---|---|
| **extract_graph** | Entity + Relationship | Tuple `<\|>` |
| **extract_claims** | Claim (có status) | Tuple `<\|>` + TRUE/FALSE |
| **3 lớp (đề xuất)** | Entity + Rel + Claim | Tách biệt 3 lớp |

## Framework & Tham khảo:
_(Chờ điền)_