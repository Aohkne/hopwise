"""Prompt trích xuất: template .md được đọc và điền văn bản đúng chỗ."""

from app.harness.prompts.extract_graph import PLACEHOLDER, build_prompt, load_template


def test_template_skips_header_and_keeps_placeholder() -> None:
    template = load_template()
    assert template.startswith("Bạn là hệ thống trích xuất")
    assert template.count(PLACEHOLDER) == 1
    assert template.rstrip().endswith("## OUTPUT")


def test_build_prompt_inserts_text_verbatim() -> None:
    text = 'Xe ZZ9 giảm {30%} - ("entity"<|>X) {input_text}'
    prompt = build_prompt(text)
    assert prompt.count(text) == 1
    assert prompt.endswith("## OUTPUT")
