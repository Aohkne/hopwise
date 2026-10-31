# Output — Kết quả trích xuất Entity / Relationship / Claim

> File nguồn: `data/sample.txt`
> Prompt: `prompt.md`
> Người điền: **V-LLM**

---

## Kết quả trích xuất

```
("entity"<|>VINFAST<|>ORGANIZATION<|>VinFast là tập đoàn ô tô Việt Nam)
##
("entity"<|>VF3<|>PRODUCT<|>VF3 là mẫu xe điện của VinFast, ra mắt tháng 3/2026)
##
("entity"<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>PROGRAM<|>Chương trình ưu đãi mùa xuân của VinFast)
##
("entity"<|>HÀ NỘI<|>GEO<|>Hà Nội là địa điểm áp dụng chương trình)
##
("entity"<|>TP.HCM<|>GEO<|>TP.HCM là địa điểm áp dụng chương trình)
##
("entity"<|>INDONESIA<|>GEO<|>Indonesia là thị trường xuất khẩu dự kiến)
##
("entity"<|>PHẠM NHẬT VƯỢNG<|>PERSON<|>Phạm Nhật Vượng là tổng giám đốc VinFast)
##
("relationship"<|>VINFAST<|>VF3<|>VinFast sản xuất và ra mắt xe VF3<|>9)
##
("relationship"<|>VINFAST<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>VinFast tổ chức chương trình ưu đãi mùa xuân<|>8)
##
("relationship"<|>VF3<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>VF3 tham gia chương trình ưu đãi mùa xuân<|>9)
##
("relationship"<|>PHẠM NHẬT VƯỢNG<|>VINFAST<|>Phạm Nhật Vượng là tổng giám đốc VinFast<|>8)
##
("relationship"<|>VINFAST<|>INDONESIA<|>VinFast dự kiến xuất khẩu VF3 sang Indonesia<|>7)
##
("claim"<|>VF3<|>CHƯƠNG TRÌNH ƯU ĐÃI MÙA XUÂN<|>DISCOUNT<|>TRUE<|>2026-01-15<|>2026-01-20<|>mua xe<|>VF3 được giảm 30% so với giá niêm yết<|>Khách hàng mua xe VF3 trong thời gian từ ngày 15/01/2026 đến ngày 20/01/2026 sẽ được hưởng ưu đãi giảm giá 30%)
##
("claim"<|>VINFAST<|>INDONESIA<|>EXPORT_PLAN<|>SUSPECTED<|>NONE<|>cuối năm 2026<|>NONE<|>Kế hoạch xuất khẩu VF3 sang Indonesia có thể bị hoãn đến cuối năm 2026<|>một số chuyên gia nghi ngờ kế hoạch này có thể bị hoãn đến cuối năm 2026)
<|COMPLETE|>
```

---

## Thống kê

| Loại | Số lượng |
|---|---|
| Entity | 7 |
| Relationship | 5 |
| Claim | 2 |