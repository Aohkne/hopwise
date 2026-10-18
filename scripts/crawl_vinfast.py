"""Crawl domain 2: VinFast.

Hai nguồn:
  - Wikidata (Q56660561): thông tin công ty, logo, model xe + loại xe, công ty mẹ
    Vingroup + các công ty con của Vingroup, trụ sở, tên tiếng Việt của quốc gia.
  - SEC EDGAR 20-F (CIK 0001913510) — báo cáo thường niên VinFast nộp cho SEC:
      * bảng "Directors and Senior Management" của MỌI bản 20-F thường niên
        (FY2023, FY2024, FY2025...) -> HĐQT hiện tại + người TỪNG ở HĐQT
      * Exhibit 8.1 -> danh sách công ty con + nơi đăng ký
      * bảng cổ đông lớn, bảng bên liên quan (related parties)
      * danh sách gạch đầu dòng: thương hiệu, mẫu xe, dòng sản phẩm khác
      * mục "Our Properties and Manufacturing Facilities" -> nhà máy

Nguyên tắc: mọi parser phải fail loudly khi không tìm thấy bảng/mẫu câu cần thiết.
Tuyệt đối không fallback sang dữ liệu hardcode — dữ liệu sai còn tệ hơn không có.
Phần lấy từ văn xuôi (nhà máy, thị trường, BASED_ON) luôn lưu kèm `evidence` là
nguyên văn câu trong 20-F để đối chiếu lại.
"""

from __future__ import annotations

import collections
import html
import json
import pathlib
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wikidata_client import _get, commons_url, entity_json, qid_of, slug, sparql  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "vinfast.json"

VINFAST = "Q56660561"
SEC_UA = "JEV-KG-Research khoalh.dev@gmail.com"  # SEC bắt buộc có email trong User-Agent
SEC_CIK = "1913510"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK0001913510.json"
SEC_ARCHIVE = f"https://www.sec.gov/Archives/edgar/data/{SEC_CIK}"
CRAWLED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

# Vùng (không phải quốc gia) xuất hiện trong danh sách thị trường của 20-F.
REGIONS = {"North America", "Europe", "Middle East", "Southeast Asia"}


# --------------------------------------------------------------------------- #
# SEC: tải tài liệu
# --------------------------------------------------------------------------- #

_CACHE: dict[str, str] = {}


def sec_get(url: str) -> str:
    """GET 1 tài liệu SEC (có retry, cache trong phiên). SEC giới hạn 10 req/s."""
    if url not in _CACHE:
        _CACHE[url] = _get(url, {"User-Agent": SEC_UA}, timeout=180).decode("utf-8", errors="ignore")
        time.sleep(0.2)
    return _CACHE[url]


def annual_20f_filings() -> list[dict]:
    """Mọi bản 20-F THƯỜNG NIÊN (kỳ báo cáo 31/12), mới nhất trước.

    Bỏ qua 20-F/A (bản sửa đổi) và bản 20-F 08/2023 — đó là "shell company report"
    nộp lúc niêm yết qua SPAC, không có bảng HĐQT cùng định dạng.
    """
    data = json.loads(sec_get(SEC_SUBMISSIONS))
    recent = data["filings"]["recent"]
    out = []
    for form, date, report, acc, doc in zip(
        recent["form"], recent["filingDate"], recent["reportDate"],
        recent["accessionNumber"], recent["primaryDocument"],
    ):
        if form == "20-F" and report.endswith("-12-31"):
            folder = f"{SEC_ARCHIVE}/{acc.replace('-', '')}"
            out.append({"url": f"{folder}/{doc}", "folder": folder, "filing_date": date,
                        "fiscal_year": int(report[:4])})
    if not out:
        raise RuntimeError("Không tìm thấy bản 20-F thường niên nào trong hồ sơ SEC của VinFast")
    return sorted(out, key=lambda f: f["fiscal_year"], reverse=True)


def _cells(row_html: str) -> list[str]:
    out = []
    for cell in re.findall(r"<t[dh]\b.*?>(.*?)</t[dh]>", row_html, re.S | re.I):
        text = re.sub(r"<[^>]+>", " ", cell)
        text = html.unescape(text).replace("​", " ")
        text = re.sub(r"\s+", " ", text).strip()
        out.append(text)
    return [c for c in out if c]


def _tables(doc: str) -> list[list[list[str]]]:
    """Mọi bảng trong tài liệu, mỗi bảng là list hàng (đã bỏ hàng rỗng)."""
    out = []
    for t in re.findall(r"<table\b.*?</table>", doc, re.S | re.I):
        rows = [c for r in re.findall(r"<tr\b.*?</tr>", t, re.S | re.I) if (c := _cells(r))]
        if rows:
            out.append(rows)
    return out


def flat_text(doc: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", doc)).replace("​", " ")
    return re.sub(r"\s+", " ", text)


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip(), maxsplit=1)[0].strip()


def sentence_of(text: str, start: int, end: int) -> str:
    """Nguyên văn câu chứa đoạn text[start:end] — dùng làm evidence."""
    a = max(text.rfind(". ", 0, start), text.rfind("● ", 0, start))
    b = text.find(". ", end)
    return text[a + 2 if a != -1 else 0 : b + 1 if b != -1 else len(text)].strip()


def strip_note(name: str) -> str:
    """'Tham Chee Soon (2)' -> 'Tham Chee Soon' (bỏ chú thích cuối tên)."""
    return re.sub(r"\s*\(\d+\)$", "", name).strip()


def split_list(text: str) -> list[str]:
    """'Vietnam, Indonesia and the Philippines' -> ['Vietnam', 'Indonesia', 'Philippines']."""
    parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", text)
    return [re.sub(r"^the\s+", "", p.strip()) for p in parts if p.strip()]


# --------------------------------------------------------------------------- #
# SEC: HĐQT / ban điều hành
# --------------------------------------------------------------------------- #

def fetch_board(url: str) -> list[dict]:
    """Parse bảng 'Directors and Senior Management' trong 1 bản 20-F."""
    doc = sec_get(url)

    anchor = doc.find("Directors and Senior Management")
    if anchor == -1:
        raise RuntimeError(f"Không tìm thấy mục 'Directors and Senior Management' trong {url}")

    start = doc.find("<table", anchor)
    end = doc.find("</table>", start)
    if start == -1 or end == -1:
        raise RuntimeError(f"Không tìm thấy bảng HĐQT sau mục 'Directors and Senior Management' ({url})")

    board: list[dict] = []
    for row in re.findall(r"<tr\b.*?>(.*?)</tr>", doc[start : end + 8], re.S | re.I):
        cells = _cells(row)
        # Hàng hợp lệ: [tên, tuổi (2 chữ số), chức danh]
        if len(cells) == 3 and re.fullmatch(r"\d{2}", cells[1]):
            board.append({"name": strip_note(cells[0]), "age": int(cells[1]), "title": cells[2]})

    if not board:
        raise RuntimeError(f"Parse được bảng nhưng không trích được thành viên nào — cấu trúc 20-F đã đổi ({url})")

    # Tiểu sử: đoạn văn bắt đầu bằng "<Tên>." sau bảng
    flat = re.sub(r"<[^>]+>", " ", doc[end : end + 40000])
    flat = re.sub(r"\s+", " ", html.unescape(flat).replace("​", " "))
    for member in board:
        m = re.search(re.escape(member["name"]) + r"\.\s+(M[rs]\.?s?\b.{80,900}?)(?=[A-Z][a-z]+ [A-Z][a-z]+.{0,30}\. M[rs]|$)", flat)
        if m:
            member["bio"] = m.group(1).strip()
    return board


def board_history(filings: list[dict]) -> list[dict]:
    """Gộp HĐQT của mọi năm: mỗi người 1 bản ghi, kèm các năm tài chính có mặt.

    Thông tin (tuổi, chức danh, tiểu sử) lấy từ bản 20-F MỚI NHẤT có tên người đó.
    """
    people: dict[str, dict] = {}
    for f in filings:  # mới nhất trước
        board = fetch_board(f["url"])
        print(f"    -> FY{f['fiscal_year']}: {len(board)} người")
        for m in board:
            key = strip_accents(m["name"])
            if key not in people:
                people[key] = {**m, "fiscal_years": [], "source_url": f["url"],
                               "source_filing_date": f["filing_date"], "as_of_year": f["fiscal_year"]}
            people[key]["fiscal_years"].append(f["fiscal_year"])
    latest = filings[0]["fiscal_year"]
    for p in people.values():
        p["fiscal_years"].sort()
        p["current"] = latest in p["fiscal_years"]
    return list(people.values())


# --------------------------------------------------------------------------- #
# SEC: công ty con, cổ đông, bên liên quan
# --------------------------------------------------------------------------- #

def fetch_subsidiaries(filing: dict) -> tuple[list[dict], str]:
    """Exhibit 8.1 'List of Subsidiaries': [{name, jurisdiction}]."""
    index = json.loads(sec_get(f"{filing['folder']}/index.json"))
    names = [it["name"] for it in index["directory"]["item"]
             if re.search(r"ex-?8(d1|\.1|1)?\.htm$", it["name"], re.I)]
    if not names:
        raise RuntimeError(f"Không tìm thấy Exhibit 8.1 (danh sách công ty con) trong {filing['folder']}")
    url = f"{filing['folder']}/{names[0]}"
    subs = []
    for rows in _tables(sec_get(url)):
        for r in rows:
            if len(r) == 3 and re.fullmatch(r"\d+\.?", r[0]):
                subs.append({"name": r[1], "jurisdiction": r[2]})
    if not subs:
        raise RuntimeError(f"Exhibit 8.1 không có dòng công ty con nào — định dạng đã đổi ({url})")
    return subs, url


def fetch_ownership_notes(text: str) -> list[dict]:
    """Chú thích sơ đồ cơ cấu tổ chức có ghi rõ tên công ty con + % sở hữu trực tiếp.

    Chú thích chỉ ghi "this subsidiary" (không có tên) bị bỏ qua — sơ đồ là hình ảnh.
    """
    out = []
    for m in re.finditer(r"We directly own ([\d.]+)% of (.+?) \(([^)]+)\)’s total outstanding share capital", text):
        out.append({"owner": None, "pct": float(m.group(1)), "sub": m.group(2),
                    "evidence": sentence_of(text, m.start(), m.end())})
    for m in re.finditer(r"Our subsidiary, (.+?), directly owns ([\d.]+)% of (.+?) \(([^)]+)\)’s total "
                         r"outstanding share capital", text):
        out.append({"owner": m.group(1), "pct": float(m.group(2)), "sub": m.group(3),
                    "evidence": sentence_of(text, m.start(), m.end())})
    return out


def alias_full_name(text: str, alias: str) -> str:
    """'References to “VIG” are to Vietnam Investment Group Joint Stock Company.'"""
    m = re.search(r"References to “" + re.escape(alias) + r"” are to (.+?)\. (?:References|In this)", text)
    if not m:
        raise RuntimeError(f"Không tìm thấy định nghĩa tên viết tắt “{alias}” trong 20-F")
    name = m.group(1).strip()
    return name + "." if re.search(r"\b(Ltd|Inc|Co|Corp)$", name) else name


def fetch_shareholders(doc: str) -> list[dict]:
    """Bảng 'Ordinary Shares Beneficially Owned': [{name, shares, pct, group}]."""
    for rows in _tables(doc):
        flat = [" ".join(r) for r in rows]
        if not any("Beneficially Owned" in f for f in flat[:3]) or not any("5% shareholders" in f for f in flat):
            continue
        out, group = [], None
        for r in rows:
            head = r[0]
            if head.startswith("5% shareholders"):
                group = "major"
            elif head.startswith("Directors and executive officers"):
                group = "insider"
            elif group and len(r) == 3 and not head.startswith("All directors"):
                shares, pct = r[1], r[2]
                if shares in ("—", "-"):
                    continue  # không nắm cổ phần
                out.append({"name": strip_note(head), "shares": int(shares.replace(",", "")),
                            "pct": "<1" if pct == "*" else pct, "group": group})
        if out:
            return out
    raise RuntimeError("Không tìm thấy bảng cổ đông (Beneficially Owned) trong 20-F")


def fetch_related_parties(doc: str) -> list[dict]:
    """Bảng 'Related parties | Relationship with the Group' (có thể chia nhiều bảng)."""
    out = []
    for rows in _tables(doc):
        if rows[0][:2] != ["Related parties", "Relationship with the Group"]:
            continue
        for r in rows[1:]:
            if len(r) != 2:
                continue
            name, alias = r[0], None
            m = re.match(r"(.+?)\s*\(“(.+?)”\)\s*$", name)
            if m:
                name, alias = m.group(1), m.group(2)
            out.append({"name": name, "alias": alias, "relationship": r[1]})
    if not out:
        raise RuntimeError("Không tìm thấy bảng bên liên quan (Related parties) trong 20-F")
    return out


# --------------------------------------------------------------------------- #
# SEC: thương hiệu, mẫu xe, dòng sản phẩm, nhà máy (văn bản gạch đầu dòng)
# --------------------------------------------------------------------------- #

def _bullets(segment: str) -> list[tuple[str, str]]:
    """'● VF 3 — a contemporary ...' -> [('VF 3', 'a contemporary ...')]."""
    out = []
    for b in segment.split("● ")[1:]:
        m = re.match(r"(.{1,40}?)\s*[—–]\s*(.+)", b, re.S)
        if m:
            out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def fetch_brands(text: str) -> dict:
    """3 thương hiệu + mẫu xe thuộc từng thương hiệu + phân khúc/BASED_ON dòng Green."""
    a = text.find("we market our EVs under three distinct brands")
    b = text.find("As of the date of this Annual Report", a)
    if a == -1 or b == -1:
        raise RuntimeError("Không tìm thấy đoạn 'we market our EVs under three distinct brands'")
    brands = {n: d for n, d in _bullets(text[a:b]) if n in ("VF", "Green", "Lac Hong")}
    if len(brands) != 3:
        raise RuntimeError(f"Đoạn thương hiệu không đủ 3 thương hiệu: {list(brands)}")

    m = re.search(r"Our EV models include the (.+?) under the VF brand, (.+?) under the Lac Hong brand, "
                  r"the Green brand, which includes (.+?), and the EC Van", text)
    if not m:
        raise RuntimeError("Không tìm thấy câu 'Our EV models include ... under the VF brand ...'")
    keep = re.compile(r"^(VF\b|Lac Hong\b|\w+ Green$)")
    members = {brand: [x for x in split_list(seg) if keep.match(x)]
               for brand, seg in zip(("VF", "Lac Hong", "Green"), m.groups())}

    segments = dict(re.findall(r"(\w+ Green) \(([A-Za-z0-9 -]{2,20})\)", text))
    based_on = []
    bm = re.search(r"the (\w+ Green) \([^)]+\) and (?:the )?(\w+ Green) \([^)]+\), which were developed "
                   r"based on the (VF [\w]+) and the (VF [\w]+), respectively", text)
    if bm:
        ev = sentence_of(text, bm.start(), bm.end())
        based_on = [(bm.group(1), bm.group(3), ev), (bm.group(2), bm.group(4), ev)]
    return {"brands": brands, "members": members, "segments": segments, "based_on": based_on,
            "members_evidence": sentence_of(text, m.start(), m.end())}


def fetch_models(text: str) -> tuple[list[dict], list[dict]]:
    """Mẫu xe (gạch đầu dòng 'VF 3 — ...' tới 'Other Products') và dòng sản phẩm khác."""
    a = text.find("● VF 3 —")
    b = text.find("Other Products", a)
    if a == -1 or b == -1:
        raise RuntimeError("Không tìm thấy danh sách mẫu xe ('● VF 3 —' ... 'Other Products') trong 20-F")
    models = []
    for name, desc in _bullets(text[a:b]):
        markets, ev = [], None
        mm = re.search(r"(?:currently offer this model in|currently available in) (.+?)"
                       r"(?:, (?:and )?(?:with|commenced)\b|\.)", desc)
        if mm:
            markets = split_list(mm.group(1))
            ev = sentence_of(desc, mm.start(), mm.end())
        based = re.search(r"developed based on the (VF [\w ]+?) model", desc)
        for n in re.split(r"\s+and\s+(?=Lac Hong)", name):  # "Lac Hong 900S and Lac Hong 800S"
            models.append({"name": n, "summary": first_sentence(desc), "markets": markets,
                           "markets_evidence": ev, "based_on": based.group(1) if based else None})
    lines = [{"name": n, "summary": first_sentence(d)}
             for n, d in _bullets(text[b : b + 8000]) if re.match(r"E-\w+$", n)]
    if not models or not lines:
        raise RuntimeError(f"Danh sách mẫu xe/dòng sản phẩm rỗng: {len(models)} xe, {len(lines)} dòng")
    return models, lines


# Mỗi nhà máy: mẫu câu BẮT BUỘC khớp (`located`) + mẫu tuỳ chọn để lấy thêm thông tin.
# Đây là đặc tả cách trích xuất chứ không phải dữ liệu: nếu 20-F không còn câu đó
# thì crawler dừng với lỗi, không tự điền.
FACTORY_SPECS = [
    {"key": "hai_phong", "place": "Hai Phong", "country": "Vietnam",
     "located": r"manufacturing facility is located in Hai Phong, Vietnam",
     "opened": r"Opened in (\d{4}), our automobile manufacturing facility in Hai Phong",
     "capacity": r"facility in Hai Phong currently has a maximum production capacity .{0,200}? of up to "
                 r"([\d,]+) vehicles per year"},
    {"key": "ha_tinh", "place": "Ha Tinh", "country": "Vietnam",
     "located": r"new factory in Ha Tinh, Vietnam",
     "opened": r"factory in Ha Tinh, Vietnam, which inaugurated in (\w+ \d{4})",
     "capacity": r"factory in Ha Tinh.{0,700}?In phase 1, the factory has a maximum capacity of up to "
                 r"([\d,]+) EVs per year",
     "produces": r"factory in Ha Tinh, Vietnam,[^.]*?production of the (.+?) models?\b"},
    {"key": "subang", "place": "Subang, West Java", "country": "Indonesia",
     "located": r"CKD manufacturing facility in Subang, West Java, Indonesia",
     "opened": r"In (\w+ \d{4}), we inaugurated a CKD manufacturing facility in Subang",
     "capacity": r"facility in Subang, West Java, Indonesia, with Phase 1 production capacity of "
                 r"approximately ([\d,]+) vehicles per year"},
    {"key": "thoothukudi", "place": "Thoothukudi, Tamil Nadu", "country": "India",
     "located": r"manufacturing facility in Thoothukudi, Tamil Nadu",
     "opened": r"In (\w+ \d{4}), we inaugurated this manufacturing facility at the SIPCOT",
     "capacity": r"initially focused on assembling the [^.]*? models and has a designed capacity of "
                 r"([\d,]+) vehicles per year",
     "produces": r"initially focused on assembling the (.+?) models"},
    {"key": "north_carolina", "place": "North Carolina", "country": "United States",
     "located": r"broke ground at our manufacturing facility in North Carolina",
     "planned_start": r"manufacturing facility in North Carolina[^.]*\. The facility is targeted to "
                      r"begin production in (\d{4})"},
]


def fetch_factories(text: str) -> list[dict]:
    out = []
    for spec in FACTORY_SPECS:
        m = re.search(spec["located"], text)
        if not m:
            raise RuntimeError(f"Không tìm thấy câu mô tả nhà máy '{spec['key']}' trong 20-F: {spec['located']}")
        f = {"key": spec["key"], "place": spec["place"], "country": spec["country"],
             "evidence": sentence_of(text, m.start(), m.end())}
        for field in ("opened", "capacity", "produces", "planned_start"):
            if field in spec and (fm := re.search(spec[field], text)):
                f[field] = fm.group(1)
        if "produces" in f:
            f["produces"] = split_list(f["produces"])
        out.append(f)
    return out


# --------------------------------------------------------------------------- #
# Wikidata
# --------------------------------------------------------------------------- #

LBL = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en". }'


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


# Class của Wikidata không phải "loại xe": Q3231690 "car model" là meta-class của mọi
# mẫu xe; Q478798 "hình ảnh" là dữ liệu gán nhầm trên 1 model.
NOT_VEHICLE_CLASSES = {"Q3231690", "Q478798"}


def fetch_vehicle_classes() -> list[dict]:
    """Loại xe của từng model: instance of (P31) / subclass of (P279)."""
    rows = sparql(f"""
        SELECT DISTINCT ?model ?cls ?clsLabel WHERE {{
          ?model wdt:P176|wdt:P1716 wd:{VINFAST} .
          ?model wdt:P31|wdt:P279 ?cls .
          {LBL}
        }}
    """)
    return [r for r in rows if qid_of(r["cls"]) not in NOT_VEHICLE_CLASSES]


def fetch_vingroup_subsidiaries(vingroup_q: str) -> list[dict]:
    return sparql(f"""
        SELECT DISTINCT ?s ?sLabel ?inception WHERE {{
          {{ ?s wdt:P749 wd:{vingroup_q} }} UNION {{ wd:{vingroup_q} wdt:P355 ?s }}
          FILTER(?s != wd:{VINFAST})
          OPTIONAL {{ ?s wdt:P571 ?inception }}
          {LBL}
        }}
    """)


def fetch_countries(names_en: list[str]) -> dict[str, dict]:
    """Tên quốc gia tiếng Anh (như trong 20-F) -> {qid, vi}. Chỉ khớp entity là quốc gia."""
    values = " ".join(f'"{n}"@en' for n in names_en)
    rows = sparql(f"""
        SELECT ?c ?en ?vi WHERE {{
          VALUES ?en {{ {values} }}
          ?c rdfs:label ?en ; wdt:P31 wd:Q6256 .
          OPTIONAL {{ ?c rdfs:label ?vi . FILTER(LANG(?vi) = "vi") }}
        }}
    """)
    return {r["en"]: {"qid": qid_of(r["c"]), "vi": r.get("vi")} for r in rows}


def label_of(qid: str) -> dict:
    rows = sparql(f"""
        SELECT ?nameVi ?nameEn WHERE {{
          OPTIONAL {{ wd:{qid} rdfs:label ?nameVi . FILTER(LANG(?nameVi) = "vi") }}
          OPTIONAL {{ wd:{qid} rdfs:label ?nameEn . FILTER(LANG(?nameEn) = "en") }}
        }} LIMIT 1
    """)
    r = rows[0] if rows else {}
    return {"vi": r.get("nameVi"), "en": r.get("nameEn")}


# --------------------------------------------------------------------------- #
# Tiện ích
# --------------------------------------------------------------------------- #

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


def model_key(name: str) -> str:
    """'VinFast VF 8' / 'VF 8' -> 'vf8' để khớp model giữa Wikidata và 20-F."""
    return re.sub(r"[^a-z0-9]", "", strip_accents(name).replace("vinfast", ""))


LEGAL_WORDS = {"jsc", "joint", "stock", "company", "cong", "ty", "co", "phan", "llc", "limited",
               "liability", "ltd", "inc", "pte", "corp"}


def company_key(name: str) -> str:
    """'Vinhomes JSC' ~ 'Công ty cổ phần Vinhomes' -> 'vinhomes'."""
    words = re.findall(r"[a-z0-9]+", strip_accents(name))
    return "".join(w for w in words if w not in LEGAL_WORDS)


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


def vi_date(text: str) -> str:
    """'June 2025' -> 'tháng 6/2025'; '2019' giữ nguyên."""
    months = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
    m = re.fullmatch(r"(\w+) (\d{4})", text)
    return f"tháng {months.index(m.group(1)) + 1}/{m.group(2)}" if m and m.group(1) in months else text


def years_text(years: list[int]) -> str:
    return ", ".join(str(y) for y in years)


# --------------------------------------------------------------------------- #
# Dựng graph
# --------------------------------------------------------------------------- #

def main() -> None:
    print("1/6 Lấy entity VinFast + Vingroup từ Wikidata...")
    ent = entity_json(VINFAST)
    inception_raw = claim_values(ent, "P571")
    logos = claim_values(ent, "P154")
    parent_q = (claim_values(ent, "P749") or [None])[0]
    hq_q = (claim_values(ent, "P159") or [None])[0]
    founder_q = (claim_values(ent, "P112") or [None])[0]
    industry_q = (claim_values(ent, "P452") or [None])[0]
    legal_q = (claim_values(ent, "P1454") or [None])[0]
    website = (claim_values(ent, "P856") or [None])[0]
    vg_ent = entity_json(parent_q) if parent_q else {}
    vg_subs = fetch_vingroup_subsidiaries(parent_q) if parent_q else []
    print(f"    -> {len(vg_subs)} công ty con khác của Vingroup")

    print("2/6 Lấy model xe + loại xe từ Wikidata...")
    models = fetch_car_models()
    classes = fetch_vehicle_classes()
    print(f"    -> {len(models)} model, {len(classes)} cặp model-loại xe")

    print("3/6 Lấy HĐQT các năm từ SEC 20-F...")
    filings = annual_20f_filings()
    latest = filings[0]
    people = board_history(filings)

    print(f"4/6 Đọc 20-F FY{latest['fiscal_year']}: công ty con, cổ đông, bên liên quan...")
    doc = sec_get(latest["url"])
    text = flat_text(doc)
    subs, ex8_url = fetch_subsidiaries(latest)
    ownership = fetch_ownership_notes(text)
    holders = fetch_shareholders(doc)
    related = fetch_related_parties(doc)
    print(f"    -> {len(subs)} công ty con, {len(ownership)} chú thích sở hữu, "
          f"{len(holders)} cổ đông, {len(related)} bên liên quan")

    print("5/6 Đọc 20-F: thương hiệu, mẫu xe, nhà máy...")
    brand_info = fetch_brands(text)
    sec_models, product_lines = fetch_models(text)
    factories = fetch_factories(text)
    print(f"    -> {len(brand_info['brands'])} thương hiệu, {len(sec_models)} mẫu xe, "
          f"{len(product_lines)} dòng sản phẩm, {len(factories)} nhà máy")

    print("6/6 Dựng graph...")
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    sec_src = {"source": "sec_20f", "source_url": latest["url"], "source_filing_date": latest["filing_date"]}

    def add(nid: str, label: str, props: dict) -> str:
        props = {k: v for k, v in props.items() if v not in (None, "", [], {})}
        props.setdefault("crawled_at", CRAWLED_AT)
        if nid in nodes:  # bổ sung field, không ghi đè field đã có
            for k, v in props.items():
                nodes[nid]["properties"].setdefault(k, v)
        else:
            nodes[nid] = {"id": nid, "label": label, "properties": props}
        return nid

    def edge(a: str, b: str, kind: str, **props) -> None:
        edges.append({"from": a, "to": b, "type": kind,
                      "properties": {k: v for k, v in props.items() if v not in (None, "", [])}})

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

    # --- Công ty mẹ Vingroup + các công ty con khác của Vingroup ---
    vingroup_id = None
    if parent_q:
        p = label_of(parent_q)
        vingroup_id = add(slug(parent_q, "vingroup"), "Organization", {
            "name": p.get("vi") or p.get("en"),
            "description": f"{p.get('vi') or p.get('en')} — công ty mẹ của VinFast.",
            **wd_props(parent_q),
        })
        edge(company_id, vingroup_id, "SUBSIDIARY_OF")
        for s in vg_subs:
            sq = qid_of(s["s"])
            name = s["sLabel"]
            sid = add(slug(sq, name), "Company", {
                "name": name,
                "founded": year_month(s["inception"]) if s.get("inception") else None,
                "description": f"{name} — công ty con của Vingroup.",
                **wd_props(sq),
            })
            edge(sid, vingroup_id, "SUBSIDIARY_OF")

    # --- Trụ sở ---
    hq_id = None
    if hq_q:
        hq_id = add(slug(hq_q, hq.get("vi") or "hq"), "Place", {
            "name": hq.get("vi") or hq.get("en"),
            "description": f"{hq.get('vi') or hq.get('en')} — nơi đặt trụ sở VinFast.",
            **wd_props(hq_q),
        })
        edge(company_id, hq_id, "HEADQUARTERED_IN")

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
        edge(founder_nid, company_id, "FOUNDED")
        if vingroup_id and founder_q in claim_values(vg_ent, "P112"):
            edge(founder_nid, vingroup_id, "FOUNDED")

    # --- HĐQT / ban điều hành qua các năm (SEC) ---
    person_ids: dict[str, str] = {}
    for m in people:
        nid = slug("sec", m["name"])
        person_ids[strip_accents(m["name"])] = nid
        title, years = m["title"], m["fiscal_years"]
        is_director = bool(re.search(r"Director|Chair", title))
        if m["current"]:
            desc = f"{m['name']}, {m['age']} tuổi — {title} của VinFast."
        else:
            desc = (f"{m['name']} — từng là {title} của VinFast "
                    f"(theo 20-F năm tài chính {years_text(years)}), nay không còn trong danh sách.")
        add(nid, "Person", {
            "name": m["name"],
            "age": m["age"],
            "age_as_of_year": m["as_of_year"],
            "title": title,
            "bio": m.get("bio"),
            "is_independent": "Independent" in title,
            "is_current": m["current"],
            "fiscal_years": years,
            "description": desc,
            "source": "sec_20f",
            "source_url": m["source_url"],
            "source_filing_date": m["source_filing_date"],
        })
        kind = "BOARD_MEMBER_OF" if is_director else "EXECUTIVE_OF"
        edge(nid, company_id, kind if m["current"] else f"FORMER_{kind}", title=title, fiscal_years=years)
        if m["current"] and re.search(r"\bCEO\b|Chief Executive", title):
            edge(nid, company_id, "CEO_OF")
        if m["current"] and re.search(r"\bCFO\b|Chief Financial", title):
            edge(nid, company_id, "CFO_OF")
        # Entity resolution: node SEC (tên không dấu) và node Wikidata (tên có dấu)
        # có thể là cùng một người — nối SAME_AS thay vì để graph có 2 node trùng.
        if founder_nid and same_person(m["name"], nodes[founder_nid]["properties"]["name"]):
            edge(nid, founder_nid, "SAME_AS", note="cùng một người, hai nguồn khác nhau")

    # --- Quốc gia / vùng ---
    country_names = {s["jurisdiction"] for s in subs} | {f["country"] for f in factories}
    for sm in sec_models:
        country_names |= set(sm["markets"])
    region_names = country_names & REGIONS
    country_names -= REGIONS
    wd_countries = fetch_countries(sorted(country_names))
    missing = country_names - set(wd_countries)
    if missing:
        print(f"    ⚠️  Không khớp được trên Wikidata (giữ tên từ 20-F): {sorted(missing)}")

    geo_ids: dict[str, str] = {}
    for name in sorted(country_names):
        wd = wd_countries.get(name)
        vi = (wd or {}).get("vi") or name
        # id có hậu tố "country" để không trùng node Place của domain bóng đá
        nid = slug(wd["qid"], f"country {name}") if wd else slug("sec", f"country {name}")
        geo_ids[name] = add(nid, "Country", {
            "name": vi, "name_en": name,
            "description": f"{vi} — quốc gia nơi VinFast có công ty con, nhà máy hoặc bán xe.",
            **(wd_props(wd["qid"]) if wd else sec_src),
        })
    for name in sorted(region_names):
        geo_ids[name] = add(slug("sec", f"region {name}"), "Region", {
            "name": name,
            "description": f"{name} — khu vực thị trường VinFast bán xe (theo 20-F).",
            **sec_src,
        })

    # --- Công ty con (Exhibit 8.1) ---
    sub_ids: dict[str, str] = {}
    for s in subs:
        nid = slug("sec", s["name"])
        sub_ids[s["name"]] = add(nid, "Company", {
            "name": s["name"],
            "jurisdiction": s["jurisdiction"],
            "description": f"{s['name']} — công ty con của VinFast, đăng ký tại {s['jurisdiction']}.",
            "source": "sec_20f_ex8", "source_url": ex8_url, "source_filing_date": latest["filing_date"],
        })
        edge(nid, geo_ids[s["jurisdiction"]], "INCORPORATED_IN")
    owned = {o["sub"]: o for o in ownership if o["owner"] is None}
    for name, nid in sub_ids.items():
        o = owned.get(name)
        edge(nid, company_id, "SUBSIDIARY_OF",
             direct_ownership_pct=o["pct"] if o else None, evidence=o["evidence"] if o else None)
    for o in ownership:
        if o["owner"] and o["owner"] in sub_ids and o["sub"] in sub_ids:
            edge(sub_ids[o["sub"]], sub_ids[o["owner"]], "SUBSIDIARY_OF",
                 direct_ownership_pct=o["pct"], evidence=o["evidence"])

    # --- Cổ đông lớn ---
    org_ids: dict[str, str] = {}
    for h in holders:
        if h["group"] == "insider":
            pid = person_ids.get(strip_accents(h["name"]))
            if not pid:
                print(f"    ⚠️  Cổ đông {h['name']} không có trong bảng HĐQT — bỏ qua")
                continue
        elif h["name"] == "Vingroup" and vingroup_id:
            pid = vingroup_id
        else:
            full = alias_full_name(text, h["name"])
            pid = add(slug("sec", full), "Organization", {
                "name": full, "short_name": h["name"],
                "description": f"{full} ({h['name']}) — cổ đông lớn của VinFast, nắm {h['pct']}% cổ phần.",
                **sec_src,
            })
            org_ids[h["name"]] = pid
            org_ids[full] = pid
        edge(pid, company_id, "SHAREHOLDER_OF", shares=h["shares"], pct=h["pct"])

    # --- Bên liên quan ---
    known = {company_key(n["properties"]["name"]): nid for nid, n in nodes.items()
             if n["label"] in ("Company", "Organization")}
    for r in related:
        names = [r["name"]] + ([r["alias"]] if r["alias"] else [])
        if any(strip_accents(n) in person_ids for n in names):
            continue  # người — đã có cạnh chức vụ
        if r["name"].startswith("Vingroup JSC") or any(n in org_ids for n in names):
            continue  # công ty mẹ / cổ đông — đã có cạnh riêng
        nid = known.get(company_key(r["name"]))
        if not nid:
            nid = add(slug("sec", r["name"]), "Company", {
                "name": r["name"], "short_name": r["alias"],
                "description": f"{r['name']} — bên liên quan của VinFast ({r['relationship']}).",
                **sec_src,
            })
        edge(nid, company_id, "RELATED_PARTY_OF", relationship=r["relationship"])

    # --- Thương hiệu ---
    brand_ids = {}
    for name, desc in brand_info["brands"].items():
        brand_ids[name] = add(slug("sec", f"brand {name}"), "Brand", {
            "name": name,
            "summary": first_sentence(desc),
            "description": f"{name} — thương hiệu xe điện của VinFast. 20-F: {first_sentence(desc)}",
            **sec_src,
        })
        edge(company_id, brand_ids[name], "HAS_BRAND")

    # --- Model xe: Wikidata trước, bổ sung/ thêm mới từ 20-F ---
    model_ids: dict[str, str] = {}
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
        model_ids[model_key(mname)] = mid
        edge(company_id, mid, "MANUFACTURES")

    for sm in sec_models:
        key = model_key(sm["name"])
        if key in model_ids:  # model đã có từ Wikidata -> bổ sung mô tả từ 20-F
            node = nodes[model_ids[key]]
            node["properties"]["sec_summary"] = sm["summary"]
            node["properties"]["description"] += f" 20-F: {sm['summary']}"
            node["properties"]["sec_source_url"] = latest["url"]
        else:
            model_ids[key] = add(slug("sec", sm["name"]), "CarModel", {
                "name": sm["name"],
                "sec_summary": sm["summary"],
                "description": f"{sm['name']} — mẫu xe của VinFast. 20-F: {sm['summary']}",
                **sec_src,
            })
            edge(company_id, model_ids[key], "MANUFACTURES")
        for market in sm["markets"]:
            edge(model_ids[key], geo_ids[market], "SOLD_IN", evidence=sm["markets_evidence"])

    # Mẫu Green không có gạch đầu dòng riêng (VD Nerio Green) -> lấy từ câu thương hiệu
    for name, segment in brand_info["segments"].items():
        key = model_key(name)
        if key not in model_ids:
            model_ids[key] = add(slug("sec", name), "CarModel", {
                "name": name,
                "description": f"{name} — mẫu xe ({segment}) thuộc thương hiệu Green của VinFast.",
                **sec_src,
            })
            edge(company_id, model_ids[key], "MANUFACTURES")
        add(model_ids[key], "CarModel", {"segment": segment})

    for brand, names in brand_info["members"].items():
        for n in names:
            key = model_key(n)
            if key not in model_ids:
                # Có trong câu liệt kê thương hiệu của 20-F nhưng không có Wikidata/gạch đầu dòng
                seg = brand_info["segments"].get(n)
                model_ids[key] = add(slug("sec", n), "CarModel", {
                    "name": n, "segment": seg,
                    "description": f"{n} — mẫu xe thuộc thương hiệu {brand} của VinFast"
                                   + (f" (phân khúc {seg})." if seg else "."),
                    "evidence": brand_info["members_evidence"],
                    **sec_src,
                })
                edge(company_id, model_ids[key], "MANUFACTURES")
            edge(model_ids[key], brand_ids[brand], "BELONGS_TO_BRAND",
                 evidence=brand_info["members_evidence"])

    based: dict[tuple[str, str], str | None] = {}
    for m in sec_models:
        if m["based_on"]:
            based[(model_key(m["name"]), model_key(m["based_on"]))] = None
    for child, parent, ev in brand_info["based_on"]:
        based[(model_key(child), model_key(parent))] = ev
    for (child, parent), ev in based.items():
        if child in model_ids and parent in model_ids:
            edge(model_ids[child], model_ids[parent], "BASED_ON", evidence=ev)
        else:
            raise RuntimeError(f"BASED_ON {child} -> {parent}: thiếu node mẫu xe")

    # --- Loại xe (Wikidata) ---
    by_qid = {n["properties"].get("wikidata_id"): nid for nid, n in nodes.items() if n["label"] == "CarModel"}
    for c in classes:
        mid = by_qid.get(qid_of(c["model"]))
        if not mid:
            continue
        cq = qid_of(c["cls"])
        cname = c.get("clsLabel") or cq
        cid = add(slug(cq, cname), "VehicleClass", {
            "name": cname,
            "description": f"{cname} — loại xe (theo phân loại của Wikidata).",
            **wd_props(cq),
        })
        edge(mid, cid, "IS_A")

    # --- Dòng sản phẩm khác (e-bus, e-scooter, e-bike) ---
    for pl in product_lines:
        pid = add(slug("sec", f"product {pl['name']}"), "ProductLine", {
            "name": pl["name"],
            "description": f"{pl['name']} — dòng sản phẩm của VinFast. 20-F: {pl['summary']}",
            **sec_src,
        })
        edge(company_id, pid, "MANUFACTURES")

    # --- Nhà máy ---
    for f in factories:
        if hq_id and strip_accents(f["place"]) == strip_accents(nodes[hq_id]["properties"]["name"]):
            place_id = hq_id
        else:
            place_id = add(slug("sec", f"place {f['place']}"), "Place", {
                "name": f["place"],
                "description": f"{f['place']}, {f['country']} — nơi VinFast đặt nhà máy.",
                **sec_src,
            })
        edge(place_id, geo_ids[f["country"]], "LOCATED_IN")
        status = f"dự kiến sản xuất từ {f['planned_start']}" if f.get("planned_start") else (
            f"khánh thành {vi_date(f['opened'])}" if f.get("opened") else None)
        fid = add(slug("sec", f"factory {f['key']}"), "Factory", {
            "name": f"Nhà máy VinFast {f['place']}",
            "location": f"{f['place']}, {f['country']}",
            "opened": f.get("opened"),
            "planned_start": f.get("planned_start"),
            "capacity_per_year": f.get("capacity"),
            "evidence": f["evidence"],
            "description": f"Nhà máy VinFast tại {f['place']}, {f['country']}"
                           + (f", {status}" if status else "")
                           + (f", công suất {f['capacity']} xe/năm" if f.get("capacity") else "") + ".",
            **sec_src,
        })
        edge(company_id, fid, "OPERATES")
        edge(fid, place_id, "LOCATED_IN")
        for n in f.get("produces", []):
            if model_key(n) in model_ids:
                edge(fid, model_ids[model_key(n)], "PRODUCES")

    edges = dedupe_edges(edges)
    by_label = collections.Counter(n["label"] for n in nodes.values())
    by_type = collections.Counter(e["type"] for e in edges)
    out = {
        "domain": "vinfast",
        "title": "VinFast — hãng xe, HĐQT, cổ đông, công ty con, nhà máy, thương hiệu và dòng sản phẩm",
        "crawled_at": CRAWLED_AT,
        "sources": [
            {"name": "Wikidata", "url": f"https://www.wikidata.org/wiki/{VINFAST}", "license": "CC0"},
            *({"name": f"SEC EDGAR 20-F FY{f['fiscal_year']}", "url": f["url"],
               "filing_date": f["filing_date"], "license": "public domain"} for f in filings),
            {"name": "SEC EDGAR 20-F Exhibit 8.1", "url": ex8_url, "license": "public domain"},
        ],
        "stats": {"nodes": len(nodes), "edges": len(edges),
                  "by_label": dict(by_label), "by_edge_type": dict(by_type)},
        "nodes": sorted(nodes.values(), key=lambda n: (n["label"], n["id"])),
        "edges": edges,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n Ghi {OUT}")
    print(f"   Nodes: {len(nodes)} {dict(by_label)}")
    print(f"   Edges: {len(edges)} {dict(by_type)}")


if __name__ == "__main__":
    main()
