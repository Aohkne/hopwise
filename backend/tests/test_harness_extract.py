"""Chia chunk và vòng trích xuất — client LLM giả, không gọi mạng."""

import asyncio

import pytest

from app.harness.extract import chunk_text, extract_from_raw, extract_text


def test_chunking_groups_paragraphs_and_never_loses_text() -> None:
    text = "\n\n".join(f"Đoạn {i} " + "x" * 40 for i in range(6))
    chunks = chunk_text(text, 100)
    assert all(len(c) <= 100 for c in chunks) and len(chunks) == 3
    assert "".join(c.replace("\n\n", "") for c in chunks) == text.replace("\n\n", "")

    long_line = "y" * 250
    pieces = chunk_text(long_line, 100)
    assert [len(p) for p in pieces] == [100, 100, 50] and "".join(pieces) == long_line
    assert chunk_text("  \n\n  ", 100) == []


class FakeClient:
    def __init__(self, replies: list) -> None:
        self.replies, self.prompts = replies, []

    async def complete(self, prompt: str, max_tokens: int | None = None) -> dict:
        self.prompts.append((prompt, max_tokens))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return {"text": reply, "usage": {"total_tokens": 10}, "truncated": reply.endswith("...")}


ENTITY_A = '("entity"<|>A<|>PERSON<|>Ông A)\n##\n'
ENTITY_B = '("entity"<|>B<|>GEO<|>Nơi B)\n##\n("relationship"<|>A<|>B<|>A ở B<|>7)\n<|COMPLETE|>'


def run(text: str, client: FakeClient, chunk_chars: int = 30):
    return asyncio.run(extract_text(text, client, doc_id="d", chunk_chars=chunk_chars, max_tokens=999))


def test_each_chunk_gets_its_own_prompt_and_results_are_merged() -> None:
    client = FakeClient([ENTITY_A, ENTITY_B])
    seen = []
    result = asyncio.run(extract_text(
        "Ông A làm việc.\n\nNơi B xa lắm.", client, doc_id="d", chunk_chars=20, max_tokens=999,
        on_chunk=lambda i, n: seen.append((i, n))))

    assert [p[1] for p in client.prompts] == [999, 999]
    assert "Ông A làm việc." in client.prompts[0][0] and "Nơi B xa lắm." in client.prompts[1][0]
    assert result.text_units == {"d_c001": "Ông A làm việc.", "d_c002": "Nơi B xa lắm."}
    assert result.raw["d_c002"] == ENTITY_B and seen == [(1, 2), (2, 2)]
    assert result.report["entities"] == 2 and result.report["relationships"] == 1
    assert result.report["tokens"] == 20 and result.report["errors"] == []
    # relationship ở chunk 2 truy về chunk 2
    assert result.extraction.relationships[0].text_unit_ids == ["d_c002"]


def test_a_failed_chunk_is_reported_but_does_not_sink_the_document() -> None:
    result = run("Đoạn một đủ dài.\n\nĐoạn hai đủ dài.", FakeClient([RuntimeError("503"), ENTITY_A]), 20)
    assert result.report["errors"] == ["d_c001: 503"] and result.report["entities"] == 1
    assert "d_c001" not in result.raw


def test_all_chunks_failing_raises() -> None:
    with pytest.raises(RuntimeError, match="Mọi chunk đều lỗi"):
        run("Chỉ một đoạn.", FakeClient([RuntimeError("hết credit")]))


def test_truncated_chunk_is_flagged() -> None:
    result = run("Một đoạn.", FakeClient([ENTITY_A + "..."]))
    assert result.report["truncated_chunks"] == ["d_c001"]


def test_empty_text_is_rejected_before_calling_the_model() -> None:
    client = FakeClient([])
    with pytest.raises(ValueError, match="trống"):
        run("   ", client)
    assert client.prompts == []


def test_extract_from_raw_rebuilds_without_a_model() -> None:
    result = extract_from_raw({"d_c001": ENTITY_A, "d_c002": ENTITY_B}, {"d_c001": "a", "d_c002": "b"})
    assert result.report["entities"] == 2 and result.report["chunks"] == 2
