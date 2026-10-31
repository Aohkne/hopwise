"""Gắn ảnh cho entity trích xuất từ văn bản bằng cách khớp tên với node đã có ảnh ở domain khác.

Văn bản chính sách chỉ nhắc tên xe ("VF 8", "VF9"), không có ảnh; domain `vinfast` (Wikidata) lại có
`image_url` cho nhiều mẫu xe. Khớp theo tên đã rút gọn (bỏ khoảng trắng/dấu gạch, bỏ tiền tố
"VinFast") để "VF 8", "VF8" và "VinFast VF 8" là một. Chỉ khớp đúng tên, không đoán.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.harness.merge import norm_key

_BRAND = re.compile(r"^vinfast")
_SEPARATORS = re.compile(r"[\s_\-]+")
THUMB_WIDTH = 640


def thumbnail(url: str) -> str:
    """Ảnh Wikimedia `Special:FilePath` mặc định là bản gốc (vài MB); xin bản rộng 640px cho card chi tiết."""
    if "Special:FilePath" in url and "width=" not in url:
        return f"{url}{'&' if '?' in url else '?'}width={THUMB_WIDTH}"
    return url


def compact_name(name: str | None) -> str:
    key = _SEPARATORS.sub("", norm_key(name))
    return _BRAND.sub("", key)


def image_index(reference: Path) -> dict[str, tuple[str, str]]:
    """tên rút gọn -> (image_url, id node nguồn) của file domain `reference` (rỗng nếu không có file)."""
    if not reference.exists():
        return {}
    doc = json.loads(reference.read_text(encoding="utf-8"))
    index: dict[str, tuple[str, str]] = {}
    for node in doc.get("nodes", []):
        props = node.get("properties", {})
        key = compact_name(props.get("name"))
        if key and props.get("image_url"):
            index.setdefault(key, (props["image_url"], node["id"]))
    return index


def attach_images(document: dict, reference: Path) -> int:
    """Thêm `image_url` (+ `image_source`) vào node chưa có ảnh mà tên khớp. Trả số node được gắn."""
    index = image_index(reference)
    attached = 0
    for node in document.get("nodes", []):
        props = node.get("properties", {})
        if props.get("image_url") or node.get("label") == "Claim":
            continue
        match = index.get(compact_name(props.get("name")))
        if match:
            props["image_url"], props["image_source"] = thumbnail(match[0]), match[1]
            attached += 1
    return attached
