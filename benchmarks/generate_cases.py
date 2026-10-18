"""Sinh bộ test case ground truth từ Knowledge Graph.

Chạy:  python3 benchmarks/generate_cases.py [--per-domain 30] [--seed 42] [--preview]

Mỗi domain ra `benchmarks/cases/<domain>.json`. Câu hỏi, đáp án và đường đi đều
tính từ data/<domain>.json theo các mẫu trong templates.py; không có giá trị nào
viết tay. Cùng graph + cùng seed luôn ra cùng bộ câu hỏi.

Cách chọn (để 30 câu không bị dồn vào một kiểu):
  - chia theo số bước ~ 1/3 một bước, 2/5 hai bước, 4/15 ba bước
  - mỗi mức, lấy luân phiên giữa các mẫu câu hỏi
  - mỗi node neo tối đa 1 câu, mỗi đáp án tối đa 3 câu
  - football: trong cùng một mẫu, ưu tiên câu gắn với Việt Nam
Thiếu ở mức nào thì bù từ mức khác.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from kg import KG  # noqa: E402
from templates import TEMPLATES, candidates, vietnam_related  # noqa: E402

CASES_DIR = pathlib.Path(__file__).parent / "cases"
MAX_PER_ANSWER = 3  # tối đa số câu có cùng đáp án trong một domain


def quotas(total: int) -> dict[int, int]:
    h1 = round(total * 10 / 30)
    h3 = round(total * 8 / 30)
    return {1: h1, 2: total - h1 - h3, 3: h3}


def pick(kg: KG, pools: dict[str, list[dict]], want: int, used_anchor: set, answer_count: dict,
         prefer_vietnam: bool, seen_pairs: set, strict: bool = True) -> list[dict]:
    """Lấy `want` câu từ các pool (mỗi pool = 1 mẫu), luân phiên giữa các mẫu.

    strict: mỗi mẫu chỉ lấy 1 câu cho mỗi đáp án (tránh 2 câu gần như giống hệt nhau).
    """
    chosen: list[dict] = []
    queues = {}
    for tid, pool in pools.items():
        if prefer_vietnam:  # sort ổn định: câu gắn với Việt Nam lên trước, giữ nguyên thứ tự ngẫu nhiên
            pool = sorted(pool, key=lambda c: not vietnam_related(kg, c))
        queues[tid] = list(pool)
    progressed = True
    while len(chosen) < want and progressed:
        progressed = False
        for tid in list(queues):
            if len(chosen) >= want:
                break
            queue = queues[tid]
            while queue:
                case = queue.pop(0)
                anchor, answer = case["anchors"][0], case["answers"][0]
                pair = (tid, answer)
                if kg.key(anchor) in used_anchor or answer_count.get(answer, 0) >= MAX_PER_ANSWER:
                    continue
                if strict and pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                used_anchor.add(kg.key(anchor))
                answer_count[answer] = answer_count.get(answer, 0) + 1
                chosen.append(case)
                progressed = True
                break
    return chosen


def generate(domain: str, total: int, seed: int) -> dict:
    kg = KG.load(domain)
    rng = random.Random(f"{domain}:{seed}")
    by_hops: dict[int, dict[str, list[dict]]] = {1: {}, 2: {}, 3: {}}
    for tpl in TEMPLATES[domain]:
        pool = candidates(kg, tpl)
        if pool:
            rng.shuffle(pool)
            by_hops[tpl.hops][tpl.id] = pool

    used_anchor: set[str] = set()
    answer_count: dict[str, int] = {}
    seen_pairs: set[tuple[str, str]] = set()
    prefer = domain == "football_vn"
    chosen: dict[int, list[dict]] = {}
    for hops, want in quotas(total).items():
        chosen[hops] = pick(kg, by_hops[hops], want, used_anchor, answer_count, prefer, seen_pairs)

    # bù phần thiếu: trước hết từ các mức khác, rồi mới nới luật "1 câu/đáp án/mẫu"
    missing = total - sum(len(v) for v in chosen.values())
    for strict in (True, False):
        for hops in (3, 2, 1):
            if missing <= 0:
                break
            extra = pick(kg, by_hops[hops], missing, used_anchor, answer_count, prefer, seen_pairs, strict)
            chosen[hops] += extra
            missing -= len(extra)

    cases = [c for hops in (1, 2, 3) for c in sorted(chosen[hops], key=lambda c: c["template"])]
    for i, case in enumerate(cases, 1):
        case["id"] = f"{domain.split('_')[0]}-{i:03d}"
    cases = [{"id": c.pop("id"), **c} for c in cases]  # id lên đầu cho dễ đọc

    return {
        "domain": domain,
        "graph": {
            "file": f"data/{domain}.json",
            "crawled_at": kg.doc["crawled_at"],
            "nodes": len(kg.doc["nodes"]),
            "edges": len(kg.doc["edges"]),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-domain", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--preview", action="store_true", help="chỉ in câu hỏi, không ghi file")
    args = parser.parse_args()

    for domain in TEMPLATES:
        doc = generate(domain, args.per_domain, args.seed)
        cases = doc["cases"]
        hops = {h: sum(1 for c in cases if c["hops"] == h) for h in (1, 2, 3)}
        print(f"\n=== {domain}: {len(cases)} câu (1 bước {hops[1]}, 2 bước {hops[2]}, 3 bước {hops[3]}) ===")
        if len(cases) < args.per_domain:
            print(f"  ⚠️  chỉ sinh được {len(cases)}/{args.per_domain} câu hợp lệ")
        if args.preview:
            for c in cases:
                print(f"  {c['id']} [{c['hops']}] {c['question']}\n          -> {c['answer_text']}   ({c['template']})")
            continue
        CASES_DIR.mkdir(exist_ok=True)
        out = CASES_DIR / f"{domain}.json"
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  ghi {out.relative_to(CASES_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
