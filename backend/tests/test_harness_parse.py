"""Parser tuple của prompt trích xuất — kiểm tra bằng chính output mẫu trong docs/research."""

from pathlib import Path

from app.harness.parse import parse_records

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "research" / "samples" / "output"


def test_parses_the_small_sample_output() -> None:
    text = (SAMPLES / "sample.md").read_text(encoding="utf-8")
    result = parse_records(text, "c1")
    assert (len(result.entities), len(result.relationships), len(result.claims)) == (7, 5, 2)
    assert result.skipped == []

    vf3 = next(e for e in result.entities if e.name == "VF3")
    assert vf3.type == "PRODUCT" and vf3.text_unit_ids == ["c1"]
    rel = result.relationships[0]
    assert (rel.source, rel.target, rel.strength) == ("VINFAST", "VF3", 9)

    discount, export = result.claims
    assert (discount.status, discount.start, discount.end) == ("TRUE", "2026-01-15", "2026-01-20")
    assert discount.condition == "mua xe" and "30%" in discount.source_text
    # NONE -> None, ngày mơ hồ giữ nguyên dạng text
    assert (export.status, export.start, export.end, export.condition) == (
        "SUSPECTED", None, "cuối năm 2026", None)


def test_parses_the_policy_notice_sample_output() -> None:
    path = next(SAMPLES.glob("thong-bao-*.md"))
    result = parse_records(path.read_text(encoding="utf-8"), "c1")
    assert (len(result.entities), len(result.relationships), len(result.claims)) == (45, 40, 59)
    assert result.skipped == []
    # mô tả có dấu ngoặc đơn và "&" không bị cắt giữa chừng
    assert any("&" in c.source_text for c in result.claims)


def test_tolerates_fences_prose_and_missing_separators() -> None:
    text = (
        'Đây là kết quả:\n```\n("entity"<|>A<|>PERSON<|>Ông A (CEO))\n'
        '("entity"<|>B<|>GEO<|>Nơi B)\n##\n'
        '("relationship"<|>A<|>B<|>A ở B<|>7)\n<|COMPLETE|>\n```\nHết.'
    )
    result = parse_records(text, "c1")
    assert [e.description for e in result.entities] == ["Ông A (CEO)", "Nơi B"]
    assert result.relationships[0].strength == 7


def test_bad_records_are_skipped_and_reported_not_repaired() -> None:
    text = (
        '("entity"<|>A<|>PERSON)\n##\n'                       # thiếu mô tả
        '("relationship"<|>A<|><|>mô tả<|>5)\n##\n'            # thiếu đích
        '("claim"<|>A<|>B<|>DISCOUNT<|>TRUE)\n##\n'           # thiếu trường
        '("entity"<|>C<|>GEO<|>ok)'
    )
    result = parse_records(text, "c1")
    assert [e.name for e in result.entities] == ["C"]
    assert len(result.skipped) == 3 and result.relationships == [] and result.claims == []


def test_strength_is_clamped_and_unreadable_strength_is_none() -> None:
    text = ('("relationship"<|>A<|>B<|>x<|>15)\n##\n("relationship"<|>A<|>C<|>y<|>cao)\n')
    strengths = [r.strength for r in parse_records(text, "c").relationships]
    assert strengths == [10, None]
