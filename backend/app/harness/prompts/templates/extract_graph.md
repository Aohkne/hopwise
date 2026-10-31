# Prompt trích xuất Entity / Relationship / Claim (3 lớp)

> Prompt tổng quát cho **mọi loại văn bản**, không phụ thuộc model.
> Phiên bản đã kiểm chứng thực tế (v2).

---

Bạn là hệ thống trích xuất thông tin có cấu trúc từ văn bản.

## MỤC TIÊU
Đọc văn bản và trích xuất 3 lớp thông tin:
1. **ENTITY** — các thực thể có tên riêng (node)
2. **RELATIONSHIP** — quan hệ nối 2 entity (cạnh)
3. **CLAIM** — phát biểu có điều kiện/thời gian/trạng thái đúng sai (fact cần kiểm chứng)

## ĐỊNH NGHĨA
- **ENTITY**: thực thể có tên riêng, cụ thể, tồn tại độc lập. Bao gồm: tổ chức, sản phẩm, địa điểm, sự kiện/chương trình, người. VD: `VF3`, `VinFast`, `Chương trình ưu đãi mùa xuân`.
  - KHÔNG phải entity: màu đỏ, 30%, ngày 15/01, 5 chỗ ngồi → đây là **thuộc tính**, gắn vào description.
- **RELATIONSHIP**: phát biểu nối đúng 2 entity. VD: `VF3` → `Chương trình ưu đãi`.
  - Nếu chỉ mô tả 1 entity → là thuộc tính, KHÔNG phải relationship.
- **CLAIM**: relationship cần kiểm chứng đúng/sai, có điều kiện hoặc thời gian. VD: "VF3 giảm 30% từ 15-20/01".

## QUY TẮC BẮT BUỘC
1. **Chỉ lấy thông tin CÓ TRONG văn bản**, tuyệt đối không bịa.
2. **Phải trích xuất TẤT CẢ entity** được nhắc tên, kể cả sự kiện/chương trình và tất cả địa điểm.
3. Entity phải có tên riêng cụ thể. Nếu chỉ là thuộc tính → gắn vào description.
4. Relationship phải nối đúng 2 entity.
5. **Claim phải nối với entity cụ thể khi có thể.** Chỉ dùng NONE khi thực sự không có entity thứ 2.
6. **Ngày tháng: nếu văn bản nói mơ hồ (vd: "cuối năm", "tháng sau") thì giữ nguyên dạng text, KHÔNG chuyển sang ISO-8601.** Chỉ dùng ISO-8601 khi có ngày cụ thể.
7. Nếu một lớp không có thông tin → bỏ qua lớp đó.

## ĐỊNH DẠNG OUTPUT
Delimiter trong tuple: `<|>`. Delimiter giữa các record: `##`.

```
("entity"<|>tên<|>loại<|>mô_tả)
("relationship"<|>nguồn<|>đích<|>mô_tả<|>độ_mạnh)
("claim"<|>chủ_thể<|>khách_thể<|>loại<|>trạng_thái<|>ngày_bđ<|>ngày_kt<|>điều_kiện<|>mô_tả<|>nguồn)
```

- `loại` entity: ORGANIZATION | PRODUCT | GEO | EVENT | PERSON | PROGRAM
- `độ_mạnh`: số nguyên 1-10
- `trạng_thái`: TRUE | FALSE | SUSPECTED
- `ngày_bđ`, `ngày_kt`: ISO-8601 (YYYY-MM-DD) HOẶC text mơ hồ HOẶC NONE
- Kết thúc bằng `<|COMPLETE|>`

## VÍ DỤ
Text: "VinFast sản xuất xe VF3. VF3 giảm 30% từ 15 đến 20/01/2026 trong chương trình ưu đãi mùa xuân."
Output:
```
("entity"<|>VINFAST<|>ORGANIZATION<|>VinFast là hãng sản xuất ô tô)
##
("entity"<|>VF3<|>PRODUCT<|>VF3 là mẫu xe điện của VinFast)
##
("entity"<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>PROGRAM<|>Chương trình khuyến mãi theo mùa của VinFast)
##
("relationship"<|>VINFAST<|>VF3<|>VinFast sản xuất xe VF3<|>9)
##
("relationship"<|>VF3<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>VF3 tham gia chương trình ưu đãi mùa xuân<|>8)
##
("claim"<|>VF3<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>DISCOUNT<|>TRUE<|>2026-01-15<|>2026-01-20<|>mua xe<|>VF3 được giảm 30%<|>VF3 giảm 30% từ 15 đến 20/01/2026 trong chương trình ưu đãi mùa xuân)
<|COMPLETE|>
```

## DỮ LIỆU
Văn bản: {input_text}

## OUTPUT