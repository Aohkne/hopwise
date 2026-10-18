"""Kiểm tra bộ test case ground truth còn khớp Knowledge Graph hiện tại.

Chạy:  python3 benchmarks/verify_cases.py        (exit 1 nếu có lỗi)

Với mỗi câu, script DỰNG LẠI câu đó từ graph (cùng mẫu, cùng node neo) rồi so với
file. Nhờ vậy bắt được: graph đã crawl lại mà bộ câu hỏi chưa sinh lại, file bị sửa
tay, đáp án không còn duy nhất, hay câu hỏi lộ tên đáp án.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from kg import KG  # noqa: E402
from templates import BY_ID, TEMPLATES, build_case  # noqa: E402

CASES_DIR = pathlib.Path(__file__).parent / "cases"
REQUIRED = ("id", "question", "answers", "answer_text", "hops", "tags", "template", "anchors",
            "reference_path")
# các trường phải khớp với kết quả dựng lại từ graph
REBUILT = ("question", "answers", "answer_text", "hops", "tags", "reference_path")


def verify_doc(kg: KG, doc: dict) -> tuple[list[str], list[str]]:
    """Trả về (lỗi, cảnh báo) của 1 file case."""
    errors: list[str] = []
    warnings: list[str] = []

    if doc.get("domain") != kg.domain:
        errors.append(f"domain trong file là {doc.get('domain')!r}, mong đợi {kg.domain!r}")
    g = doc.get("graph", {})
    if g.get("crawled_at") != kg.doc["crawled_at"]:
        errors.append(f"graph đã crawl lại ({kg.doc['crawled_at']}) nhưng bộ câu hỏi sinh từ bản "
                      f"{g.get('crawled_at')} — chạy lại generate_cases.py")
    if (g.get("nodes"), g.get("edges")) != (len(kg.doc["nodes"]), len(kg.doc["edges"])):
        errors.append(f"số node/cạnh lệch: file ghi {g.get('nodes')}/{g.get('edges')}, "
                      f"graph có {len(kg.doc['nodes'])}/{len(kg.doc['edges'])}")

    cases = doc.get("cases", [])
    for label, values in (("id", [c.get("id") for c in cases]),
                          ("câu hỏi", [c.get("question") for c in cases])):
        for value, n in Counter(values).items():
            if n > 1:
                errors.append(f"{label} bị trùng {n} lần: {value!r}")

    for c in cases:
        cid = c.get("id", "?")
        missing = [f for f in REQUIRED if f not in c]
        if missing:
            errors.append(f"{cid}: thiếu trường {missing}")
            continue
        tpl = BY_ID.get(c["template"])
        if tpl is None or tpl.domain != kg.domain:
            errors.append(f"{cid}: mẫu {c['template']!r} không tồn tại cho domain {kg.domain}")
            continue
        unknown = [i for i in c["anchors"] + c["answers"] + [p["node"] for p in c["reference_path"]]
                   if i not in kg.nodes]
        if unknown:
            errors.append(f"{cid}: node không có trong graph: {unknown[:3]}")
            continue
        rebuilt = build_case(kg, tpl, c["anchors"][0], c.get("params", {}))
        if rebuilt is None:
            errors.append(f"{cid}: không dựng lại được từ graph (đáp án không còn duy nhất, tên "
                          f"trùng, hoặc lộ đáp án trong câu hỏi): {c['question']}")
            continue
        for field in REBUILT:
            if rebuilt[field] != c[field]:
                errors.append(f"{cid}: trường {field!r} lệch graph — file: {c[field]!r}, "
                              f"graph: {rebuilt[field]!r}")

    hops = Counter(c.get("hops") for c in cases)
    if not cases:
        errors.append("không có câu hỏi nào")
    elif len(hops) < 3:
        warnings.append(f"chỉ có {len(hops)} mức số bước: {dict(hops)}")
    return errors, warnings


def main() -> None:
    ok = True
    for domain in TEMPLATES:
        path = CASES_DIR / f"{domain}.json"
        print(f"\n=== {domain} ===")
        if not path.exists():
            print(f"  ❌ thiếu {path.name} — chạy generate_cases.py")
            ok = False
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        errors, warnings = verify_doc(KG.load(domain), doc)
        cases = doc.get("cases", [])
        print(f"  {len(cases)} câu; số bước: {dict(sorted(Counter(c['hops'] for c in cases).items()))}; "
              f"mẫu: {len({c['template'] for c in cases})}")
        for w in warnings:
            print(f"  ⚠️  {w}")
        for e in errors:
            print(f"  ❌ {e}")
        if not errors:
            print("   Mọi câu dựng lại được từ graph, đáp án duy nhất, không lộ tên đáp án")
        ok &= not errors
    print("\n" + "=" * 50)
    print("KẾT QUẢ: " + (" ĐẠT" if ok else "❌ CÓ LỖI CẦN SỬA"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
