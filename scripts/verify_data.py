"""Kiểm tra chất lượng data đã crawl trước khi đưa vào Neo4j.

Chạy: python3 scripts/verify_data.py
"""

from __future__ import annotations

import collections
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wikidata_client import check_url_alive  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
SAMPLE_URLS = 30

ok = True


def fail(msg: str) -> None:
    global ok
    ok = False
    print(f"  ❌ {msg}")


def check(path: pathlib.Path) -> dict:
    global ok
    print(f"\n=== {path.name} ===")
    doc = json.loads(path.read_text(encoding="utf-8"))
    nodes, edges = doc["nodes"], doc["edges"]
    print(f"  nodes={len(nodes)}  edges={len(edges)}")
    print(f"  by_label: {doc['stats']['by_label']}")
    print(f"  by_edge_type: {doc['stats']['by_edge_type']}")

    # 1. id trùng
    ids = [n["id"] for n in nodes]
    dupes = [i for i, c in collections.Counter(ids).items() if c > 1]
    if dupes:
        fail(f"{len(dupes)} node id trùng: {dupes[:5]}")
    else:
        print("  ✅ Không có node id trùng")

    # 2. toàn vẹn tham chiếu
    idset = set(ids)
    dangling = [e for e in edges if e["from"] not in idset or e["to"] not in idset]
    if dangling:
        fail(f"{len(dangling)} cạnh trỏ tới node không tồn tại, ví dụ: {dangling[0]}")
    else:
        print("  ✅ Mọi cạnh đều trỏ tới node tồn tại")

    # 3. cạnh trùng hoàn toàn
    sig = [(e["from"], e["to"], e["type"], json.dumps(e.get("properties", {}), sort_keys=True)) for e in edges]
    dup_edges = sum(c - 1 for c in collections.Counter(sig).values() if c > 1)
    if dup_edges:
        print(f"  ⚠️  {dup_edges} cạnh trùng lặp hoàn toàn (nên dedupe)")
    else:
        print("  ✅ Không có cạnh trùng lặp")

    # 4. node cô lập
    touched = {e["from"] for e in edges} | {e["to"] for e in edges}
    isolated = idset - touched
    print(f"  ℹ️  {len(isolated)} node cô lập (không có cạnh nào)")

    # 5. mọi node phải có description + source
    no_desc = [n["id"] for n in nodes if not n["properties"].get("description")]
    no_src = [n["id"] for n in nodes if not n["properties"].get("source")]
    if no_desc:
        fail(f"{len(no_desc)} node thiếu description (cần cho state của Jev): {no_desc[:3]}")
    else:
        print("  ✅ Mọi node đều có description")
    if no_src:
        fail(f"{len(no_src)} node thiếu source: {no_src[:3]}")
    else:
        print("  ✅ Mọi node đều có source truy vết")

    # 6. độ phủ field
    per_label: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    totals: collections.Counter = collections.Counter()
    for n in nodes:
        totals[n["label"]] += 1
        for k, v in n["properties"].items():
            if v not in (None, "", [], {}) and not k.startswith("_") and k not in ("source", "crawled_at"):
                per_label[n["label"]][k] += 1
    print("  --- độ phủ field ---")
    for label, cnt in sorted(per_label.items()):
        tot = totals[label]
        interesting = {k: v for k, v in cnt.items()
                       if k in ("dob", "image_url", "logo_urls", "logo_url", "position",
                                "nationality", "wikipedia_url", "founded_year", "bio", "title", "launch_year")}
        if interesting:
            parts = [f"{k} {v}/{tot} ({v * 100 // tot}%)" for k, v in sorted(interesting.items())]
            print(f"    {label:14} {', '.join(parts)}")

    return doc


def check_images(docs: list[dict]) -> None:
    print(f"\n=== Kiểm tra link ảnh (mẫu ngẫu nhiên {SAMPLE_URLS}) ===")
    urls = []
    for doc in docs:
        for n in doc["nodes"]:
            for key in ("image_url", "logo_url"):
                if n["properties"].get(key):
                    urls.append((n["id"], n["properties"][key]))
            for u in n["properties"].get("logo_urls", []):
                urls.append((n["id"], u))
    print(f"  Tổng số URL ảnh trong data: {len(urls)}")
    if not urls:
        return
    random.seed(42)
    sample = random.sample(urls, min(SAMPLE_URLS, len(urls)))
    dead = []
    for nid, url in sample:
        if not check_url_alive(url):
            dead.append((nid, url))
    alive = len(sample) - len(dead)
    print(f"  ✅ Sống: {alive}/{len(sample)} ({alive * 100 // len(sample)}%)")
    for nid, url in dead:
        fail(f"URL chết: {nid} -> {url}")


def main() -> None:
    docs = [check(p) for p in sorted(DATA.glob("*.json"))]
    check_images(docs)
    print("\n" + ("=" * 50))
    print("KẾT QUẢ: " + ("✅ ĐẠT" if ok else "❌ CÓ LỖI CẦN SỬA"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
