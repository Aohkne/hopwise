"""Prompt trích xuất Entity / Relationship / Claim (3 lớp) — nội dung ở
`templates/extract_graph.md`, file này chỉ đọc và điền văn bản đầu vào."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "extract_graph.md"
PLACEHOLDER = "{input_text}"
# Phần đầu file (tiêu đề + ghi chú cho người đọc) kết thúc ở dòng `---` đầu tiên và
# không gửi cho model.
_HEADER_END = "\n---\n"


@lru_cache
def load_template() -> str:
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    _, sep, body = text.partition(_HEADER_END)
    template = (body if sep else text).strip()
    if PLACEHOLDER not in template:
        raise ValueError(f"{TEMPLATE_PATH.name} thiếu placeholder {PLACEHOLDER}")
    return template


def build_prompt(text: str) -> str:
    """Điền văn bản vào prompt. Dùng `replace` thay vì `format` vì prompt chứa nhiều dấu ngoặc nhọn
    và văn bản đầu vào cũng có thể chứa."""
    return load_template().replace(PLACEHOLDER, text)
