"""Gắn ảnh cho entity trích xuất bằng cách khớp tên với node có ảnh ở domain khác."""

import json

from app.harness.enrich import attach_images, compact_name, thumbnail


def reference(tmp_path):
    path = tmp_path / "vinfast.json"
    nodes = [
        {"id": "q_vf8", "label": "CarModel", "properties": {"name": "VinFast VF 8", "image_url": "http://img/vf8.jpg"}},
        {"id": "q_vf9", "label": "CarModel", "properties": {"name": "VinFast VF 9"}},  # không có ảnh
    ]
    path.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    return path


def test_compact_name_ignores_brand_spacing_and_case() -> None:
    assert compact_name("VinFast VF 8") == compact_name("vf8") == compact_name("VF_8") == "vf8"


def test_attach_images_matches_exact_compact_name_only(tmp_path) -> None:
    doc = {"nodes": [
        {"id": "a", "label": "Product", "properties": {"name": "VF8"}},
        {"id": "b", "label": "Product", "properties": {"name": "VF 8 Thế hệ mới"}},  # tên khác -> không khớp
        {"id": "c", "label": "Product", "properties": {"name": "VF 9"}},              # nguồn không có ảnh
        {"id": "d", "label": "Product", "properties": {"name": "VF 8", "image_url": "keep"}},
        {"id": "e", "label": "Claim", "properties": {"name": "VF 8"}},
    ]}
    assert attach_images(doc, reference(tmp_path)) == 1
    by_id = {n["id"]: n["properties"] for n in doc["nodes"]}
    assert by_id["a"]["image_url"] == "http://img/vf8.jpg" and by_id["a"]["image_source"] == "q_vf8"
    assert "image_url" not in by_id["b"] and "image_url" not in by_id["c"] and "image_url" not in by_id["e"]
    assert by_id["d"]["image_url"] == "keep"


def test_missing_reference_file_attaches_nothing(tmp_path) -> None:
    doc = {"nodes": [{"id": "a", "label": "Product", "properties": {"name": "VF8"}}]}
    assert attach_images(doc, tmp_path / "none.json") == 0


def test_wikimedia_filepath_urls_get_a_thumbnail_width() -> None:
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/VF_8.jpg"
    assert thumbnail(url) == url + "?width=640"
    assert thumbnail(url + "?width=100") == url + "?width=100"
    assert thumbnail("http://img/vf8.jpg") == "http://img/vf8.jpg"
