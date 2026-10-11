"""Crawl domain 2: VinFast.

Hai nguồn:
  - Wikidata (Q56660561): thông tin công ty, logo, model xe, công ty mẹ, trụ sở.
  - SEC EDGAR 20-F (CIK 0001913510): HỘI ĐỒNG QUẢN TRỊ — Wikidata KHÔNG có dữ liệu này
    (P3320/P169 đều trống), nên phải lấy từ báo cáo thường niên nộp cho SEC.

Nguyên tắc: parser 20-F phải fail loudly nếu không tìm thấy bảng. Tuyệt đối không
fallback sang danh sách hardcode — dữ liệu sai còn tệ hơn không có dữ liệu.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wikidata_client import USER_AGENT, commons_url, entity_json, qid_of, slug, sparql  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "vinfast.json"

VINFAST = "Q56660561"
SEC_UA = "JEV-KG-Research khoalh.dev@gmail.com"  # SEC bắt buộc có email trong User-Agent
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK0001913510.json"
CRAWLED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# SEC: hội đồng quản trị
# --------------------------------------------------------------------------- #

def latest_20f_url() -> tuple[str, str]:
    """Trả (url, ngày nộp) của bản 20-F mới nhất."""
    req = urllib.request.Request(SEC_SUBMISSIONS, headers={"User-Agent": SEC_UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    recent = data["filings"]["recent"]
    for form, date, acc, doc in zip(
        recent["form"], recent["filingDate"], recent["accessionNumber"], recent["primaryDocument"]
    ):
        if form == "20-F":  # bỏ qua bản sửa đổi 20-F/A
            acc_nodash = acc.replace("-", "")
            return f"https://www.sec.gov/Archives/edgar/data/1913510/{acc_nodash}/{doc}", date
    raise RuntimeError("Không tìm thấy bản 20-F nào trong hồ sơ SEC của VinFast")


def _cells(row_html: str) -> list[str]:
    out = []
    for cell in re.findall(r"<t[dh]\b.*?>(.*?)</t[dh]>", row_html, re.S | re.I):
        text = re.sub(r"<[^>]+>", " ", cell)
        text = html.unescape(text).replace("​", " ")
        text = re.sub(r"\s+", " ", text).strip()
        out.append(text)
    return [c for c in out if c]


def fetch_board(url: str) -> list[dict]:
    """Parse bảng 'Directors and Senior Management' trong 20-F."""
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        doc = resp.read().decode("utf-8", errors="ignore")

    anchor = doc.find("Directors and Senior Management")
    if anchor == -1:
        raise RuntimeError("Không tìm thấy mục 'Directors and Senior Management' trong 20-F")

    start = doc.find("<table", anchor)
    end = doc.find("</table>", start)
    if start == -1 or end == -1:
        raise RuntimeError("Không tìm thấy bảng HĐQT sau mục 'Directors and Senior Management'")

    board: list[dict] = []
    for row in re.findall(r"<tr\b.*?>(.*?)</tr>", doc[start : end + 8], re.S | re.I):
        cells = _cells(row)
        # Hàng hợp lệ: [tên, tuổi (2 chữ số), chức danh]
        if len(cells) == 3 and re.fullmatch(r"\d{2}", cells[1]):
            board.append({"name": cells[0], "age": int(cells[1]), "title": cells[2]})

    if not board:
        raise RuntimeError("Parse được bảng nhưng không trích được dòng thành viên nào — cấu trúc 20-F đã đổi")

    # Tiểu sử: đoạn văn bắt đầu bằng "<Tên>." sau bảng
    flat = re.sub(r"<[^>]+>", " ", doc[end : end + 40000])
    flat = re.sub(r"\s+", " ", html.unescape(flat).replace("​", " "))
    for member in board:
        m = re.search(re.escape(member["name"]) + r"\.\s+(M[rs]\.?s?\b.{80,900}?)(?=[A-Z][a-z]+ [A-Z][a-z]+.{0,30}\. M[rs]|$)", flat)
        if m:
            member["bio"] = m.group(1).strip()
    return board


# --------------------------------------------------------------------------- #
# Wikidata
# --------------------------------------------------------------------------- #

def claim_values(entity: dict, prop: str) -> list:
    """Phẳng hoá claim: entity -> QID, time -> chuỗi ISO, quantity -> số, còn lại giữ nguyên."""
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        v = c["mainsnak"].get("datavalue", {}).get("value")
        if v is None:
            continue
        if isinstance(v, dict):
            v = v.get("id") or v.get("time") or v.get("amount") or v.get("text") or v
        out.append(v)
    return out


def fetch_car_models() -> list[dict]:
    return sparql(f"""
        SELECT DISTINCT ?model ?nameVi ?nameEn ?inception ?image WHERE {{
          ?model wdt:P176|wdt:P1716 wd:{VINFAST} .
          OPTIONAL {{ ?model rdfs:label ?nameVi . FILTER(LANG(?nameVi) = "vi") }}
          OPTIONAL {{ ?model rdfs:label ?nameEn . FILTER(LANG(?nameEn) = "en") }}
          OPTIONAL {{ ?model wdt:P571 ?inception }}
          OPTIONAL {{ ?model wdt:P18 ?image }}
        }}
    """)


def label_of(qid: str) -> dict:
    rows = sparql(f"""
        SELECT ?nameVi ?nameEn WHERE {{
          OPTIONAL {{ wd:{qid} rdfs:label ?nameVi . FILTER(LANG(?nameVi) = "vi") }}
          OPTIONAL {{ wd:{qid} rdfs:label ?nameEn . FILTER(LANG(?nameEn) = "en") }}
        }} LIMIT 1
    """)
    r = rows[0] if rows else {}
    return {"vi": r.get("nameVi"), "en": r.get("nameEn")}


def dedupe_edges(edges: list[dict]) -> list[dict]:
    """Loại cạnh trùng hoàn toàn (cùng from/to/type/properties)."""
    seen, out = set(), []
    for e in edges:
        key = (e["from"], e["to"], e["type"], json.dumps(e.get("properties", {}), sort_keys=True))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt để so khớp tên giữa nguồn SEC (không dấu) và Wikidata (có dấu)."""
    decomposed = unicodedata.normalize("NFD", text)
    no_marks = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return no_marks.replace("đ", "d").replace("Đ", "D").lower().strip()


def same_person(a: str, b: str) -> bool:
    """So khớp tên bỏ dấu, không phụ thuộc thứ tự từ (Pham Nhat Vuong ~ Phạm Nhật Vượng)."""
    if not a or not b:
        return False
    return sorted(strip_accents(a).split()) == sorted(strip_accents(b).split())


def year_month(wd_time: str) -> str:
    """+2017-06-00T00:00:00Z -> 06/2017 (Wikidata dùng 00 cho phần không xác định)."""
    m = re.match(r"\+(\d{4})-(\d{2})-(\d{2})", wd_time)
    if not m:
        return wd_time
    y, mo, d = m.groups()
    if d != "00":
        return f"{d}/{mo}/{y}"
    if mo != "00":
        return f"{mo}/{y}"
    return y


def main() -> None:
    print("1/4 Lấy entity VinFast từ Wikidata...")
    ent = entity_json(VINFAST)

    inception_raw = claim_values(ent, "P571")
    logos = claim_values(ent, "P154")
    parent_q = (claim_values(ent, "P749") or [None])[0]
    hq_q = (claim_values(ent, "P159") or [None])[0]
    founder_q = (claim_values(ent, "P112") or [None])[0]
    industry_q = (claim_values(ent, "P452") or [None])[0]
    legal_q = (claim_values(ent, "P1454") or [None])[0]
    website = (claim_values(ent, "P856") or [None])[0]

    print("2/4 Lấy model xe...")
    models = fetch_car_models()
    print(f"    -> {len(models)} model")

    print("3/4 Lấy HĐQT từ SEC 20-F...")
    sec_url, sec_date = latest_20f_url()
    print(f"    -> 20-F nộp ngày {sec_date}")
    board = fetch_board(sec_url)
    print(f"    -> {len(board)} thành viên HĐQT/ban điều hành")

    print("4/4 Dựng graph...")
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(nid: str, label: str, props: dict) -> str:
        props = {k: v for k, v in props.items() if v not in (None, "", [], {})}
        props.setdefault("crawled_at", CRAWLED_AT)
        nodes[nid] = {"id": nid, "label": label, "properties": props}
        return nid

    def wd_props(qid: str) -> dict:
        return {"wikidata_id": qid, "source": "wikidata",
                "source_url": f"https://www.wikidata.org/wiki/{qid}"}

    # --- Công ty VinFast ---
    hq = label_of(hq_q) if hq_q else {}
    industry = label_of(industry_q) if industry_q else {}
    legal = label_of(legal_q) if legal_q else {}
    founded = year_month(inception_raw[0]) if inception_raw else None

    company_id = slug(VINFAST, "vinfast")
    add(company_id, "Company", {
        "name": "VinFast",
        "name_en": "VinFast Auto Ltd.",
        "founded": founded,
        "founded_year": founded.split("/")[-1] if founded else None,
        "logo_urls": [commons_url(f) for f in logos],
        "website": website,
        "headquarters": hq.get("vi") or hq.get("en"),
        "industry": industry.get("vi") or industry.get("en"),
        "legal_form": legal.get("vi") or legal.get("en"),
        "stock_ticker": "VFS (Nasdaq)",
        "sec_cik": "0001913510",
        "description": f"VinFast — hãng xe của Việt Nam, thành lập {founded}, "
                       f"trụ sở tại {hq.get('vi') or hq.get('en')}, niêm yết trên Nasdaq với mã VFS.",
        **wd_props(VINFAST),
    })

    # --- Công ty mẹ, trụ sở ---
    if parent_q:
        p = label_of(parent_q)
        pid = add(slug(parent_q, "vingroup"), "Organization", {
            "name": p.get("vi") or p.get("en"),
            "description": f"{p.get('vi') or p.get('en')} — công ty mẹ của VinFast.",
            **wd_props(parent_q),
        })
        edges.append({"from": company_id, "to": pid, "type": "SUBSIDIARY_OF", "properties": {}})

    if hq_q:
        hid = add(slug(hq_q, hq.get("vi") or "hq"), "Place", {
            "name": hq.get("vi") or hq.get("en"),
            "description": f"{hq.get('vi') or hq.get('en')} — nơi đặt trụ sở VinFast.",
            **wd_props(hq_q),
        })
        edges.append({"from": company_id, "to": hid, "type": "HEADQUARTERED_IN", "properties": {}})

    # --- Người sáng lập (Wikidata) ---
    founder_nid = None
    if founder_q:
        f = label_of(founder_q)
        founder_nid = add(slug(founder_q, f.get("vi") or "founder"), "Person", {
            "name": f.get("vi") or f.get("en"),
            "name_en": f.get("en"),
            "role": "Người sáng lập",
            "description": f"{f.get('vi') or f.get('en')} — người sáng lập VinFast.",
            **wd_props(founder_q),
        })
        edges.append({"from": founder_nid, "to": company_id, "type": "FOUNDED", "properties": {}})

    # --- HĐQT từ SEC ---
    for member in board:
        nid = slug("sec", member["name"])
        is_ceo = "CEO" in member["title"] or "Chief Executive" in member["title"]
        add(nid, "Person", {
            "name": member["name"],
            "age": member["age"],
            "title": member["title"],
            "bio": member.get("bio"),
            "is_independent": "Independent" in member["title"],
            "description": f"{member['name']}, {member['age']} tuổi — {member['title']} của VinFast.",
            "source": "sec_20f",
            "source_url": sec_url,
            "source_filing_date": sec_date,
            "crawled_at": CRAWLED_AT,
        })
        edges.append({"from": nid, "to": company_id, "type": "BOARD_MEMBER_OF",
                      "properties": {"title": member["title"]}})
        if is_ceo:
            edges.append({"from": nid, "to": company_id, "type": "CEO_OF", "properties": {}})

        # Entity resolution: node SEC (tên không dấu) và node Wikidata (tên có dấu)
        # có thể là cùng một người — nối SAME_AS thay vì để graph có 2 node trùng.
        if founder_nid and same_person(member["name"], nodes[founder_nid]["properties"]["name"]):
            edges.append({"from": nid, "to": founder_nid, "type": "SAME_AS",
                          "properties": {"note": "cùng một người, hai nguồn khác nhau"}})

    # --- Model xe ---
    for m in models:
        mq = qid_of(m["model"])
        mname = m.get("nameVi") or m.get("nameEn") or mq
        inception = m.get("inception")
        mid = add(slug(mq, mname), "CarModel", {
            "name": mname,
            "name_en": m.get("nameEn"),
            "launch_year": inception[:4] if inception else None,
            "image_url": commons_url(m["image"]) if m.get("image") else None,
            "description": f"{mname} — mẫu xe do VinFast sản xuất"
                           + (f", ra mắt năm {inception[:4]}." if inception else "."),
            **wd_props(mq),
        })
        edges.append({"from": company_id, "to": mid, "type": "MANUFACTURES", "properties": {}})

    import collections
    edges = dedupe_edges(edges)
    by_label = collections.Counter(n["label"] for n in nodes.values())
    by_type = collections.Counter(e["type"] for e in edges)
    doc = {
        "domain": "vinfast",
        "title": "VinFast — hãng xe, hội đồng quản trị và dòng sản phẩm",
        "crawled_at": CRAWLED_AT,
        "sources": [
            {"name": "Wikidata", "url": f"https://www.wikidata.org/wiki/{VINFAST}", "license": "CC0"},
            {"name": "SEC EDGAR 20-F", "url": sec_url, "filing_date": sec_date, "license": "public domain"},
        ],
        "stats": {"nodes": len(nodes), "edges": len(edges),
                  "by_label": dict(by_label), "by_edge_type": dict(by_type)},
        "nodes": sorted(nodes.values(), key=lambda n: (n["label"], n["id"])),
        "edges": edges,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n Ghi {OUT}")
    print(f"   Nodes: {len(nodes)} {dict(by_label)}")
    print(f"   Edges: {len(edges)} {dict(by_type)}")


if __name__ == "__main__":
    main()
