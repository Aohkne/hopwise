"""Dựng graph JSON (schema data/*.json) từ Extraction và gộp nhiều tài liệu."""

from app.harness.build_graph import (
    build_document,
    claim_id,
    doc_id_of,
    entity_id,
    merge_documents,
    slug,
)
from app.harness.parse import Claim, Entity, Extraction, Relationship


def extraction(chunk="d_c001", description="xe điện", object_="ƯU ĐÃI") -> Extraction:
    return Extraction(
        entities=[Entity("VF 3", "PRODUCT", description, [chunk]), Entity("ƯU ĐÃI", "PROGRAM", "ct", [chunk]),
                  Entity("Lạ", "WEIRD", "loại ngoài danh sách", [chunk])],
        relationships=[Relationship("VF 3", "ƯU ĐÃI", "tham gia", 8, [chunk])],
        claims=[Claim("VF 3", object_, "DISCOUNT", "TRUE", "2026-01-15", None, "mua xe", "giảm 30%",
                      "Giảm 30% từ 15/01", [chunk])],
    )


def build(**kw) -> dict:
    return build_document(extraction(**kw), {"d_c001": "văn bản gốc"}, domain="vinfast_policy", doc_name="d.md")


def by_type(doc: dict, type_: str) -> list[dict]:
    return [e for e in doc["edges"] if e["type"] == type_]


def test_maps_entities_relationships_and_claims() -> None:
    doc = build()
    nodes = {n["id"]: n for n in doc["nodes"]}
    vf3 = nodes[entity_id("VF 3")]
    assert vf3["label"] == "Product" and vf3["properties"]["name"] == "VF 3"
    assert vf3["properties"]["text_unit_ids"] == ["d_c001"] and vf3["properties"]["source_docs"] == ["d.md"]
    assert nodes[entity_id("ƯU ĐÃI")]["label"] == "Program"
    assert nodes[entity_id("Lạ")]["label"] == "Entity"  # loại lạ: giữ node, không đoán

    (rel,) = by_type(doc, "RELATED_TO")
    assert rel["properties"] == {"description": "tham gia", "weight": 0.8, "source_docs": ["d.md"],
                                 "text_unit_ids": ["d_c001"]}
    assert doc["text_units"] == {"d_c001": "văn bản gốc"}


def test_claim_is_a_node_linked_by_has_claim_and_about() -> None:
    doc = build()
    cid = claim_id("VF 3", "ƯU ĐÃI", "DISCOUNT", "2026-01-15", None, "mua xe")
    claim = next(n for n in doc["nodes"] if n["id"] == cid)
    assert claim["label"] == "Claim"
    props = claim["properties"]
    assert (props["status"], props["start_date"], props["condition"]) == ("TRUE", "2026-01-15", "mua xe")
    assert props["source_text"] == "Giảm 30% từ 15/01" and "end_date" not in props  # None bị bỏ
    (has,) = by_type(doc, "HAS_CLAIM")
    (about,) = by_type(doc, "ABOUT")
    assert (has["from"], has["to"]) == (entity_id("VF 3"), cid)
    assert (about["from"], about["to"]) == (cid, entity_id("ƯU ĐÃI"))


def test_claim_without_object_has_no_about_edge() -> None:
    assert by_type(build(object_=None), "ABOUT") == []


def test_stats_match_the_graph_and_every_edge_points_to_a_node() -> None:
    doc = build()
    assert doc["stats"]["nodes"] == len(doc["nodes"]) and doc["stats"]["edges"] == len(doc["edges"])
    assert doc["stats"]["by_label"] == {"Product": 1, "Program": 1, "Entity": 1, "Claim": 1}
    assert doc["stats"]["by_edge_type"] == {"RELATED_TO": 1, "HAS_CLAIM": 1, "ABOUT": 1}
    ids = {n["id"] for n in doc["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in doc["edges"])


def test_ids_are_stable_and_ascii_free_names_are_kept_readable() -> None:
    assert entity_id("  Phạm Nhật  Vượng ") == entity_id("phạm nhật vượng") == "ent_phạm_nhật_vượng"
    assert slug("TP.HCM") == "tp_hcm" and doc_id_of("Thông báo 09.2026.md") == "thông_báo_09_2026"
    assert entity_id("???").startswith("ent_") and len(entity_id("???")) > 4


def test_merging_a_second_document_keeps_everything_and_unions_provenance() -> None:
    first = build()
    second = build_document(extraction(chunk="e_c001", description="Xe điện hatchback cỡ nhỏ của VinFast"),
                            {"e_c001": "văn bản khác"}, domain="vinfast_policy", doc_name="e.md")
    merged = merge_documents(first, second)

    assert len(merged["nodes"]) == len(first["nodes"]) and len(merged["edges"]) == len(first["edges"])
    vf3 = next(n for n in merged["nodes"] if n["id"] == entity_id("VF 3"))
    assert vf3["properties"]["description"] == "Xe điện hatchback cỡ nhỏ của VinFast"
    assert vf3["properties"]["source_docs"] == ["d.md", "e.md"]
    assert vf3["properties"]["text_unit_ids"] == ["d_c001", "e_c001"]
    assert set(merged["text_units"]) == {"d_c001", "e_c001"}
    assert [s["name"] for s in merged["sources"]] == ["d.md", "e.md"]
    assert merged["stats"]["by_label"]["Claim"] == 1


def test_merge_into_nothing_returns_the_new_document_and_rejects_other_domains() -> None:
    doc = build()
    assert merge_documents(None, doc) is doc
    other = build_document(extraction(), {}, domain="khac", doc_name="x.md")
    try:
        merge_documents(doc, other)
    except ValueError as err:
        assert "Khác domain" in str(err)
    else:
        raise AssertionError("phải từ chối gộp khác domain")
