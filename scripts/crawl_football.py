"""Crawl domain 1: Bóng đá Việt Nam (đội tuyển QG + V.League 1) từ Wikidata.

Phạm vi: cầu thủ thuộc ĐTQG Việt Nam (Q270689) hoặc từng khoác áo CLB V.League 1 (Q209080),
kèm CLB, HLV, sân vận động, nơi sinh và các danh hiệu (giải đã vô địch).

Nguyên tắc: chỉ ghi field khi Wikidata thực sự trả về. Không suy đoán, không hardcode.
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wikidata_client import commons_url, qid_of, slug, sparql, sparql_batched  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "football_vn.json"

NATIONAL_TEAM = "Q270689"  # Đội tuyển bóng đá quốc gia Việt Nam (nam)
VLEAGUE1 = "Q209080"       # V.League 1
VIETNAM = "Q881"
CRAWLED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

WD = "http://www.wikidata.org/entity/"


# --------------------------------------------------------------------------- #
# Truy vấn
# --------------------------------------------------------------------------- #

def fetch_scope_players() -> list[str]:
    rows = sparql(f"""
        SELECT DISTINCT ?player WHERE {{
          ?player wdt:P106 wd:Q937857 .
          {{ ?player wdt:P54 wd:{NATIONAL_TEAM} }}
          UNION {{ ?player wdt:P1532 wd:{VIETNAM} }}
          UNION {{ ?player wdt:P54 ?c . ?c wdt:P118 wd:{VLEAGUE1} }}
        }}
    """)
    return [qid_of(r["player"]) for r in rows]


def fetch_vleague_clubs() -> list[str]:
    rows = sparql(f"SELECT DISTINCT ?club WHERE {{ ?club wdt:P118 wd:{VLEAGUE1} . }}")
    return [qid_of(r["club"]) for r in rows]


def fetch_player_details(qids: list[str]) -> list[dict]:
    return sparql_batched("""
        SELECT ?player ?dob ?image ?position ?birthPlace ?height ?nationality ?article WHERE {
          VALUES ?player { {VALUES} }
          OPTIONAL { ?player wdt:P569 ?dob }
          OPTIONAL { ?player wdt:P18  ?image }
          OPTIONAL { ?player wdt:P413 ?position }
          OPTIONAL { ?player wdt:P19  ?birthPlace }
          OPTIONAL { ?player wdt:P2048 ?height }
          OPTIONAL { ?player wdt:P27  ?nationality }
          OPTIONAL { ?article schema:about ?player ; schema:isPartOf <https://vi.wikipedia.org/> }
        }
    """, qids)


def fetch_club_statements(qids: list[str]) -> list[dict]:
    """Cạnh cầu thủ -> CLB, kèm qualifier thời gian và số trận (nếu có)."""
    return sparql_batched("""
        SELECT ?player ?club ?start ?end ?matches WHERE {
          VALUES ?player { {VALUES} }
          ?player p:P54 ?st .
          ?st ps:P54 ?club .
          OPTIONAL { ?st pq:P580 ?start }
          OPTIONAL { ?st pq:P582 ?end }
          OPTIONAL { ?st pq:P1350 ?matches }
        }
    """, qids)


def fetch_club_details(qids: list[str]) -> list[dict]:
    return sparql_batched("""
        SELECT ?club ?inception ?venue ?logo ?country ?league ?image WHERE {
          VALUES ?club { {VALUES} }
          OPTIONAL { ?club wdt:P571 ?inception }
          OPTIONAL { ?club wdt:P115 ?venue }
          OPTIONAL { ?club wdt:P154 ?logo }
          OPTIONAL { ?club wdt:P17  ?country }
          OPTIONAL { ?club wdt:P118 ?league }
          OPTIONAL { ?club wdt:P18  ?image }
        }
    """, qids)


def fetch_vn_managers() -> list[str]:
    """HLV mang quốc tịch Việt Nam (P106 = huấn luyện viên bóng đá)."""
    rows = sparql(f"""
        SELECT DISTINCT ?coach WHERE {{
          ?coach wdt:P106 wd:Q628099 ; wdt:P27 wd:{VIETNAM} .
        }}
    """)
    return [qid_of(r["coach"]) for r in rows]


def fetch_coaching_stints(team_qids: list[str]) -> list[dict]:
    """Cạnh HLV -> đội, qua P6087 (coach of sports team) kèm qualifier thời gian.

    Lưu ý: P286 (head coach) hầu như không được set trên CLB Việt Nam nên không dùng.
    """
    return sparql_batched("""
        SELECT ?coach ?team ?start ?end WHERE {
          VALUES ?team { {VALUES} }
          ?coach p:P6087 ?st .
          ?st ps:P6087 ?team .
          OPTIONAL { ?st pq:P580 ?start }
          OPTIONAL { ?st pq:P582 ?end }
        }
    """, team_qids)


def fetch_person_details(qids: list[str]) -> list[dict]:
    return sparql_batched("""
        SELECT ?person ?dob ?image ?nationality WHERE {
          VALUES ?person { {VALUES} }
          OPTIONAL { ?person wdt:P569 ?dob }
          OPTIONAL { ?person wdt:P18  ?image }
          OPTIONAL { ?person wdt:P27  ?nationality }
        }
    """, qids)


def fetch_titles_won(team_qids: list[str]) -> list[dict]:
    """Danh hiệu: giải đấu có P1346 (winner) trỏ về CLB/đội tuyển trong phạm vi."""
    return sparql_batched("""
        SELECT ?comp ?winner ?date WHERE {
          VALUES ?winner { {VALUES} }
          ?comp wdt:P1346 ?winner .
          OPTIONAL { ?comp wdt:P585 ?date }
        }
    """, team_qids)


def fetch_labels(qids: list[str]) -> dict[str, dict]:
    """Lấy nhãn vi + en, kèm nhãn dự phòng đa ngôn ngữ.

    Một số entity (CLB/cầu thủ nước ngoài) không có nhãn vi lẫn en nhưng có nhãn
    tiếng khác — không lấy dự phòng thì node sẽ mang tên là QID, vô dụng khi làm state.
    """
    rows = sparql_batched("""
        SELECT ?item ?nameVi ?nameEn ?itemLabel WHERE {
          VALUES ?item { {VALUES} }
          OPTIONAL { ?item rdfs:label ?nameVi . FILTER(LANG(?nameVi) = "vi") }
          OPTIONAL { ?item rdfs:label ?nameEn . FILTER(LANG(?nameEn) = "en") }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en,mul,fr,es,pt,de,it,nl,pl,ja,ko,th". }
        }
    """, qids)
    out: dict[str, dict] = {}
    for r in rows:
        q = qid_of(r["item"])
        entry = out.setdefault(q, {})
        if r.get("nameVi"):
            entry["vi"] = r["nameVi"]
        if r.get("nameEn"):
            entry["en"] = r["nameEn"]
        # itemLabel trả về chính QID khi entity không có nhãn nào -> bỏ qua
        if r.get("itemLabel") and r["itemLabel"] != q:
            entry.setdefault("fallback", r["itemLabel"])
    return out


# --------------------------------------------------------------------------- #
# Gom dòng SPARQL (một entity có thể trả nhiều dòng do nhiều giá trị)
# --------------------------------------------------------------------------- #

def group(rows: list[dict], key: str) -> dict[str, dict[str, set]]:
    out: dict[str, dict[str, set]] = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        k = qid_of(r[key])
        for field, value in r.items():
            if field != key and value:
                out[k][field].add(value)
    return out


def one(values: set | None):
    """Lấy 1 giá trị đại diện (sort để ổn định giữa các lần chạy)."""
    return sorted(values)[0] if values else None


def year(iso: str | None) -> str | None:
    return iso[:4] if iso else None


def fmt_date(iso: str | None) -> str | None:
    """1995-05-16T00:00:00Z -> 16/05/1995"""
    if not iso or len(iso) < 10:
        return None
    y, m, d = iso[:4], iso[5:7], iso[8:10]
    if m == "00" or d == "00":
        return y
    return f"{d}/{m}/{y}"


def dedupe_edges(edges: list[dict]) -> list[dict]:
    """Loại cạnh trùng hoàn toàn (cùng from/to/type/properties)."""
    seen, out = set(), []
    for e in edges:
        key = (e["from"], e["to"], e["type"], json.dumps(e.get("properties", {}), sort_keys=True))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def completeness(props: dict, fields: list[str]) -> float:
    have = sum(1 for f in fields if props.get(f))
    return round(have / len(fields), 2)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    print("1/8 Lấy danh sách cầu thủ trong phạm vi...")
    players = fetch_scope_players()
    print(f"    -> {len(players)} cầu thủ")

    print("2/8 Lấy danh sách CLB V.League 1...")
    vleague_clubs = set(fetch_vleague_clubs())
    print(f"    -> {len(vleague_clubs)} CLB")

    print("3/8 Chi tiết cầu thủ...")
    pdet = group(fetch_player_details(players), "player")

    print("4/8 Cạnh cầu thủ -> CLB...")
    club_rows = fetch_club_statements(players)
    print(f"    -> {len(club_rows)} statement")

    all_clubs = {qid_of(r["club"]) for r in club_rows} | vleague_clubs
    all_clubs.discard(NATIONAL_TEAM)
    print(f"5/8 Chi tiết {len(all_clubs)} CLB (gồm cả CLB nước ngoài cầu thủ từng đầu quân)...")
    cdet = group(fetch_club_details(sorted(all_clubs)), "club")

    print("6/8 Huấn luyện viên...")
    coach_rows = fetch_coaching_stints(sorted(vleague_clubs | {NATIONAL_TEAM}))
    coaches = sorted({qid_of(r["coach"]) for r in coach_rows} | set(fetch_vn_managers()))
    codet = group(fetch_person_details(coaches), "person") if coaches else {}
    print(f"    -> {len(coaches)} HLV, {len(coach_rows)} lượt dẫn dắt")

    print("7/8 Danh hiệu (giải đã vô địch)...")
    title_rows = fetch_titles_won(sorted(vleague_clubs | {NATIONAL_TEAM}))
    print(f"    -> {len(title_rows)} danh hiệu")

    # ---- gom mọi QID cần nhãn ----
    need_labels: set[str] = set(players) | all_clubs | set(coaches) | {NATIONAL_TEAM}
    for d in pdet.values():
        for f in ("position", "birthPlace", "nationality"):
            need_labels |= {qid_of(v) for v in d.get(f, set())}
    for d in cdet.values():
        for f in ("venue", "country", "league"):
            need_labels |= {qid_of(v) for v in d.get(f, set())}
    for d in codet.values():
        need_labels |= {qid_of(v) for v in d.get("nationality", set())}
    need_labels |= {qid_of(r["comp"]) for r in title_rows}

    print(f"8/8 Lấy nhãn cho {len(need_labels)} entity...")
    labels = fetch_labels(sorted(need_labels))

    def name(qid: str) -> str:
        entry = labels.get(qid, {})
        return entry.get("vi") or entry.get("en") or entry.get("fallback") or qid

    def name_en(qid: str) -> str | None:
        return labels.get(qid, {}).get("en")

    # ------------------------------------------------------------------ #
    # Dựng node / edge
    # ------------------------------------------------------------------ #
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(qid: str, label: str, props: dict) -> str:
        nid = slug(qid, props.get("name_vi") or props.get("name") or "")
        if nid not in nodes:
            props = {k: v for k, v in props.items() if v not in (None, "", [], {})}
            props.update({
                "wikidata_id": qid,
                "source": "wikidata",
                "source_url": f"https://www.wikidata.org/wiki/{qid}",
                "crawled_at": CRAWLED_AT,
            })
            nodes[nid] = {"id": nid, "label": label, "properties": props}
        return nid

    qid2nid: dict[str, str] = {}

    # --- Đội tuyển quốc gia ---
    nt_id = add_node(NATIONAL_TEAM, "NationalTeam", {
        "name_vi": name(NATIONAL_TEAM),
        "name_en": name_en(NATIONAL_TEAM),
        "country": "Việt Nam",
        "description": f"{name(NATIONAL_TEAM)} — đội tuyển bóng đá đại diện quốc gia Việt Nam.",
    })
    qid2nid[NATIONAL_TEAM] = nt_id

    # --- Sân vận động & nơi sinh (Place) ---
    def place_node(qid: str) -> str:
        if qid not in qid2nid:
            qid2nid[qid] = add_node(qid, "Place", {
                "name_vi": name(qid),
                "name_en": name_en(qid),
                "description": f"{name(qid)} — địa điểm.",
            })
        return qid2nid[qid]

    # --- CLB ---
    for cq in sorted(all_clubs):
        d = cdet.get(cq, {})
        venue_q = qid_of(one(d.get("venue"))) if d.get("venue") else None
        league_q = qid_of(one(d.get("league"))) if d.get("league") else None
        country_q = qid_of(one(d.get("country"))) if d.get("country") else None
        inception = one(d.get("inception"))
        logo = one(d.get("logo"))
        props = {
            "name_vi": name(cq),
            "name_en": name_en(cq),
            "founded_year": year(inception),
            "home_venue": name(venue_q) if venue_q else None,
            "league": name(league_q) if league_q else None,
            "country": name(country_q) if country_q else None,
            # P154 trống với hầu hết CLB VN (logo có bản quyền, không lên Commons)
            "logo_url": commons_url(logo) if logo else None,
            "image_url": commons_url(one(d["image"])) if d.get("image") else None,
            "in_vleague1": cq in vleague_clubs,
        }
        bits = [name(cq)]
        if props["founded_year"]:
            bits.append(f"thành lập năm {props['founded_year']}")
        if props["league"]:
            bits.append(f"thi đấu tại {props['league']}")
        if props["home_venue"]:
            bits.append(f"sân nhà {props['home_venue']}")
        props["description"] = ", ".join(bits) + "."
        props["_completeness"] = completeness(props, ["founded_year", "home_venue", "league", "country", "logo_url"])
        qid2nid[cq] = add_node(cq, "Club", props)

        if venue_q:
            edges.append({"from": qid2nid[cq], "to": place_node(venue_q), "type": "HOME_VENUE", "properties": {}})

    # --- Cầu thủ ---
    for pq in players:
        d = pdet.get(pq, {})
        dob = one(d.get("dob"))
        image = one(d.get("image"))
        positions = sorted({name(qid_of(v)) for v in d.get("position", set())})
        nats = sorted({name(qid_of(v)) for v in d.get("nationality", set())})
        birth_q = qid_of(one(d.get("birthPlace"))) if d.get("birthPlace") else None
        props = {
            "name_vi": name(pq),
            "name_en": name_en(pq),
            "dob": fmt_date(dob),
            "dob_iso": dob[:10] if dob else None,
            "image_url": commons_url(image) if image else None,
            "position": ", ".join(positions) or None,
            "birth_place": name(birth_q) if birth_q else None,
            "height_cm": one(d.get("height")),
            "nationality": ", ".join(nats) or None,
            "wikipedia_url": one(d.get("article")),
        }
        bits = [name(pq)]
        if props["dob"]:
            bits.append(f"sinh {props['dob']}")
        if props["position"]:
            bits.append(f"vị trí {props['position']}")
        if props["nationality"]:
            bits.append(f"quốc tịch {props['nationality']}")
        props["description"] = ", ".join(bits) + "."
        props["_completeness"] = completeness(
            props, ["dob", "image_url", "position", "birth_place", "height_cm", "nationality", "wikipedia_url"]
        )
        qid2nid[pq] = add_node(pq, "Player", props)

        if birth_q:
            edges.append({"from": qid2nid[pq], "to": place_node(birth_q), "type": "BORN_IN", "properties": {}})

    # --- Cạnh cầu thủ -> CLB / đội tuyển ---
    seen_edges: set[tuple] = set()
    for r in club_rows:
        pq, cq = qid_of(r["player"]), qid_of(r["club"])
        if pq not in qid2nid or cq not in qid2nid:
            continue
        etype = "MEMBER_OF_NATIONAL_TEAM" if cq == NATIONAL_TEAM else "PLAYED_FOR"
        props = {}
        if r.get("start"):
            props["start_year"] = year(r["start"])
        if r.get("end"):
            props["end_year"] = year(r["end"])
        if r.get("matches"):
            props["matches"] = r["matches"]
        key = (qid2nid[pq], qid2nid[cq], etype, props.get("start_year"), props.get("end_year"))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append({"from": qid2nid[pq], "to": qid2nid[cq], "type": etype, "properties": props})

    # --- HLV ---
    for cq_str in coaches:
        d = codet.get(cq_str, {})
        dob = one(d.get("dob"))
        image = one(d.get("image"))
        nats = sorted({name(qid_of(v)) for v in d.get("nationality", set())})
        props = {
            "name_vi": name(cq_str),
            "name_en": name_en(cq_str),
            "dob": fmt_date(dob),
            "dob_iso": dob[:10] if dob else None,
            "image_url": commons_url(image) if image else None,
            "nationality": ", ".join(nats) or None,
        }
        bits = [name(cq_str), "huấn luyện viên"]
        if props["dob"]:
            bits.append(f"sinh {props['dob']}")
        if props["nationality"]:
            bits.append(f"quốc tịch {props['nationality']}")
        props["description"] = ", ".join(bits) + "."
        props["_completeness"] = completeness(props, ["dob", "image_url", "nationality"])
        if cq_str in qid2nid:
            # Cựu cầu thủ chuyển sang làm HLV: giữ node Player sẵn có, đánh dấu thêm vai trò.
            nodes[qid2nid[cq_str]]["properties"]["also_coach"] = True
        else:
            qid2nid[cq_str] = add_node(cq_str, "Coach", props)

    seen_coach_edges: set[tuple] = set()
    for r in coach_rows:
        team_q, coach_q = qid_of(r["team"]), qid_of(r["coach"])
        if team_q not in qid2nid or coach_q not in qid2nid:
            continue
        props = {}
        if r.get("start"):
            props["start_year"] = year(r["start"])
        if r.get("end"):
            props["end_year"] = year(r["end"])
        key = (coach_q, team_q, props.get("start_year"), props.get("end_year"))
        if key in seen_coach_edges:
            continue
        seen_coach_edges.add(key)
        edges.append({"from": qid2nid[coach_q], "to": qid2nid[team_q], "type": "COACHES", "properties": props})

    # --- Danh hiệu ---
    for r in title_rows:
        comp_q, win_q = qid_of(r["comp"]), qid_of(r["winner"])
        if win_q not in qid2nid:
            continue
        if comp_q not in qid2nid:
            date = r.get("date")
            props = {
                "name_vi": name(comp_q),
                "name_en": name_en(comp_q),
                "date": fmt_date(date),
                "season_year": year(date),
                "description": f"{name(comp_q)} — giải đấu bóng đá"
                               + (f" năm {year(date)}." if year(date) else "."),
            }
            qid2nid[comp_q] = add_node(comp_q, "Competition", props)
        edges.append({"from": qid2nid[win_q], "to": qid2nid[comp_q], "type": "WON", "properties": {}})

    # ------------------------------------------------------------------ #
    # Ghi file
    # ------------------------------------------------------------------ #
    edges = dedupe_edges(edges)
    by_label = collections.Counter(n["label"] for n in nodes.values())
    by_type = collections.Counter(e["type"] for e in edges)
    doc = {
        "domain": "football_vn",
        "title": "Bóng đá Việt Nam — đội tuyển quốc gia & V.League 1",
        "crawled_at": CRAWLED_AT,
        "sources": [
            {"name": "Wikidata SPARQL", "url": "https://query.wikidata.org/sparql", "license": "CC0"},
            {"name": "Wikimedia Commons (ảnh)", "url": "https://commons.wikimedia.org/", "license": "xem từng file"},
        ],
        "scope": {
            "national_team": NATIONAL_TEAM,
            "league": VLEAGUE1,
            "note": "Cầu thủ thuộc ĐTQG VN hoặc từng khoác áo CLB V.League 1; gồm cả ngoại binh.",
        },
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
