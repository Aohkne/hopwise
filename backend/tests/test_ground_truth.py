"""Test bộ sinh/kiểm tra ground truth (benchmarks/) bằng graph nhỏ giả, và kiểm tra
bộ câu hỏi đã commit còn khớp data/*.json."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks"))

from generate_cases import generate
from kg import KG, Step
from templates import Template, build_case, inc, out
from verify_cases import verify_doc


def node(i: str, label: str, name: str) -> dict:
    return {"id": i, "label": label, "properties": {"name": name, "description": name, "source": "t"}}


def edge(a: str, kind: str, b: str, **props) -> dict:
    return {"from": a, "to": b, "type": kind, "properties": props}


def tiny_graph(extra_nodes=(), extra_edges=()) -> KG:
    """Acme -[MAKES]-> Alpha, Beta;  Narnia <-[IN]- Acme Narnia Ltd -[SUB]-> Acme."""
    doc = {
        "domain": "tiny", "crawled_at": "2026-01-01T00:00:00+00:00",
        "nodes": [node("acme", "Company", "Acme"), node("alpha", "Model", "Alpha"),
                  node("beta", "Model", "Beta"), node("narnia", "Country", "Narnia"),
                  node("sub", "Company", "Acme Narnia Ltd"), *extra_nodes],
        "edges": [edge("acme", "MAKES", "alpha"), edge("acme", "MAKES", "beta"),
                  edge("sub", "IN", "narnia"), edge("sub", "SUB", "acme"), *extra_edges],
    }
    return KG.from_doc("tiny", doc)


def tpl(steps: list[Step], text: str, anchor: str = "Model") -> Template:
    return Template("t", "tiny", anchor, steps, text)


def test_walk_requires_exactly_one_node_per_step() -> None:
    kg = tiny_graph()
    assert kg.walk("alpha", [Step("MAKES", "in")], {}).answers == ["acme"]
    assert kg.walk("acme", [Step("MAKES", "out")], {}) is None  # Alpha và Beta -> mơ hồ
    assert kg.walk("alpha", [Step("NOPE", "in")], {}) is None  # không có cạnh


def test_same_as_nodes_count_as_one_answer() -> None:
    kg = tiny_graph([node("acme2", "Company", "Acme Inc")], [edge("acme2", "SAME_AS", "acme")])
    walk = kg.walk("alpha", [Step("MAKES", "in")], {})
    assert walk.answers == ["acme", "acme2"]


def test_edge_property_filter_selects_one_edge() -> None:
    kg = tiny_graph(
        [node("p1", "Person", "Ann"), node("p2", "Person", "Bob")],
        [edge("p1", "HOLDS", "acme", pct="60"), edge("p2", "HOLDS", "acme", pct="40")],
    )
    step = Step("HOLDS", "in", None, (("pct", "pct"),))
    assert kg.param_values("acme", step) == [{"pct": "60"}, {"pct": "40"}]
    assert kg.walk("acme", [step], {"pct": "40"}).answers == ["p2"]


def test_duplicate_names_reject_the_anchor() -> None:
    kg = tiny_graph([node("alpha2", "Model", "alpha")], [edge("acme", "MAKES", "alpha2")])
    assert build_case(kg, tpl([inc("MAKES")], "Xe {a} của công ty nào?"), "alpha", {}) is None
    assert build_case(kg, tpl([inc("MAKES")], "Xe {a} của công ty nào?"), "beta", {}) is not None


def test_question_must_not_contain_the_answer() -> None:
    kg = tiny_graph()
    leaky = tpl([inc("IN", "Company")], "Công ty Acme Narnia Ltd ở {a}?", anchor="Country")
    ok = tpl([inc("IN", "Company")], "Công ty nào ở {a}?", anchor="Country")
    assert build_case(kg, leaky, "narnia", {}) is None
    case = build_case(kg, ok, "narnia", {})
    assert case["answers"] == ["sub"] and case["hops"] == 1 and "incoming-edge" in case["tags"]


def test_two_hop_case_records_reference_path() -> None:
    kg = tiny_graph()
    case = build_case(kg, tpl([out("IN", "Country"), inc("IN", "Company")], "{a}?", anchor="Company"),
                      "sub", {})
    assert case is None  # đi vòng về chính node neo
    case = build_case(kg, tpl([inc("MAKES", "Company"), inc("SUB", "Company")],
                              "Công ty con của hãng sản xuất {a}?"), "alpha", {})
    assert [p["node"] for p in case["reference_path"]] == ["alpha", "acme", "sub"]
    assert case["reference_path"][1]["edge"] == "MAKES (in)"


# --- verify_cases ----------------------------------------------------------------

def make_doc(domain: str) -> tuple[KG, dict]:
    return KG.load(domain), generate(domain, 30, 42)


def test_committed_cases_match_the_graph() -> None:
    for domain in ("football_vn", "vinfast"):
        doc = json.loads((ROOT / "benchmarks" / "cases" / f"{domain}.json").read_text(encoding="utf-8"))
        errors, _ = verify_doc(KG.load(domain), doc)
        assert errors == [], errors
        assert len(doc["cases"]) == 30


def test_generation_is_deterministic_and_matches_committed_files() -> None:
    for domain in ("football_vn", "vinfast"):
        committed = json.loads((ROOT / "benchmarks" / "cases" / f"{domain}.json").read_text(encoding="utf-8"))
        assert generate(domain, 30, 42)["cases"] == committed["cases"], \
            f"{domain}: sinh lại ra bộ câu khác file đã commit — chạy generate_cases.py"


def test_verify_detects_tampering_and_stale_graph() -> None:
    kg, doc = make_doc("vinfast")
    assert verify_doc(kg, doc)[0] == []

    wrong = copy.deepcopy(doc)
    wrong["cases"][0]["answers"] = ["Q56660561_vinfast"]
    assert any("answers" in e for e in verify_doc(kg, wrong)[0])

    dup = copy.deepcopy(doc)
    dup["cases"][1]["question"] = dup["cases"][0]["question"]
    assert any("trùng" in e for e in verify_doc(kg, dup)[0])

    stale = copy.deepcopy(doc)
    stale["graph"]["crawled_at"] = "2020-01-01T00:00:00+00:00"
    assert any("crawl lại" in e for e in verify_doc(kg, stale)[0])

    ghost = copy.deepcopy(doc)
    ghost["cases"][0]["anchors"] = ["khong_co_node_nay"]
    assert any("không có trong graph" in e for e in verify_doc(kg, ghost)[0])
