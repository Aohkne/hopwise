"""Gộp kết quả nhiều chunk: dedupe entity / relationship / claim, bỏ record mồ côi."""

from app.harness.merge import merge_extractions, norm_key
from app.harness.parse import Claim, Entity, Extraction, Relationship


def claim(**over) -> Claim:
    base = {"subject": "VF3", "object": "ƯU ĐÃI", "type": "DISCOUNT", "status": "TRUE", "start": "2026-01-15",
            "end": "2026-01-20", "condition": "mua xe", "description": "giảm 30%", "source_text": "gốc",
            "text_unit_ids": ["c1"]}
    return Claim(**{**base, **over})


def part(chunk: str, **over) -> Extraction:
    base = {
        "entities": [Entity("VF3", "PRODUCT", "xe", [chunk]), Entity("ƯU ĐÃI", "PROGRAM", "ct", [chunk])],
        "relationships": [Relationship("VF3", "ƯU ĐÃI", "tham gia", 6, [chunk])],
        "claims": [claim(text_unit_ids=[chunk])],
    }
    return Extraction(**{**base, **over})


def test_norm_key_ignores_case_spacing_and_unicode_form() -> None:
    assert norm_key("  VinFast \n Auto") == norm_key("vinfast auto")
    assert norm_key("Việt Nam") == norm_key("Việt Nam")  # NFC vs NFD
    assert norm_key(None) == ""


def test_same_entity_in_two_chunks_is_merged_with_both_sources() -> None:
    a = part("c1")
    b = part("c2", entities=[Entity("vf3", "PRODUCT", "Xe điện cỡ nhỏ của VinFast", ["c2"]),
                             Entity("ƯU ĐÃI", "PROGRAM", "ct", ["c2"])])
    merged = merge_extractions([a, b])
    vf3 = next(e for e in merged.entities if norm_key(e.name) == "vf3")
    assert len(merged.entities) == 2
    assert vf3.name == "VF3" and vf3.description == "Xe điện cỡ nhỏ của VinFast"  # mô tả dài hơn
    assert vf3.text_unit_ids == ["c1", "c2"]


def test_relationships_and_claims_are_deduped_across_chunks() -> None:
    a = part("c1")
    b = part("c2", relationships=[Relationship("vf3", "ưu đãi", "xe tham gia chương trình", 9, ["c2"])])
    merged = merge_extractions([a, b, part("c3")])
    assert len(merged.relationships) == 1 and len(merged.claims) == 1
    rel = merged.relationships[0]
    assert rel.strength == 9 and rel.text_unit_ids == ["c1", "c2", "c3"]
    assert "tham gia" in rel.description and "xe tham gia chương trình" in rel.description
    assert merged.claims[0].text_unit_ids == ["c1", "c2", "c3"]


def test_claims_differing_in_date_or_condition_stay_separate() -> None:
    merged = merge_extractions([part("c1", claims=[
        claim(), claim(start="2026-02-01", end="2026-02-05"), claim(condition="mua xe cũ")])])
    assert len(merged.claims) == 3


def test_orphans_and_self_loops_are_dropped_and_reported() -> None:
    merged = merge_extractions([part(
        "c1",
        relationships=[Relationship("VF3", "KHÔNG CÓ", "x", 5, ["c1"]), Relationship("VF3", "vf3", "y", 5, ["c1"])],
        claims=[claim(subject="MA"), claim(object="MA")],
    )])
    assert merged.relationships == [] and merged.claims == []
    assert len(merged.skipped) == 4


def test_claim_without_object_is_kept() -> None:
    merged = merge_extractions([part("c1", claims=[claim(object=None)])])
    assert merged.claims[0].object is None


def test_most_common_type_wins() -> None:
    parts = [Extraction(entities=[Entity("X", t, "d", ["c"])]) for t in ("GEO", "GEO", "EVENT")]
    assert merge_extractions(parts).entities[0].type == "GEO"
