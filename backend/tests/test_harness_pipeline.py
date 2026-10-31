"""ingest_document: trích xuất -> gộp vào data/<domain>.json -> nạp Neo4j (mock, không cần Neo4j)."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.harness import pipeline

OUTPUT = (
    '("entity"<|>VF3<|>PRODUCT<|>Xe điện)\n##\n("entity"<|>ƯU ĐÃI<|>PROGRAM<|>Chương trình)\n##\n'
    '("relationship"<|>VF3<|>ƯU ĐÃI<|>tham gia<|>8)\n##\n'
    '("claim"<|>VF3<|>ƯU ĐÃI<|>DISCOUNT<|>TRUE<|>2026-01-15<|>2026-01-20<|>mua xe<|>giảm 30%<|>nguồn)\n'
)


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, prompt: str, max_tokens: int | None = None) -> dict:
        self.calls += 1
        return {"text": OUTPUT, "usage": {"total_tokens": 5}, "truncated": False}


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = SimpleNamespace(extract_chunk_chars=3000, extract_max_tokens=100,
                               outputs_dir=tmp_path / "outputs", data_dir=tmp_path / "data")
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)
    loaded = []
    monkeypatch.setattr(pipeline.graph_loader, "load_file",
                        lambda path: loaded.append(path) or {"nodes": 4, "edges": 4})
    return SimpleNamespace(settings=settings, loaded=loaded)


def ingest(name="a.md", **kw):
    return asyncio.run(pipeline.ingest_document(name, "VF3 giảm 30%.", client=kw.pop("client", FakeClient()), **kw))


def test_writes_the_domain_file_saves_raw_output_and_loads_neo4j(env) -> None:
    report = ingest()
    path = env.settings.data_dir / "vinfast_policy.json"
    doc = json.loads(path.read_text(encoding="utf-8"))

    assert doc["domain"] == "vinfast_policy" and doc["stats"]["by_label"] == {
        "Product": 1, "Program": 1, "Claim": 1}
    assert report["entities"] == 2 and report["claims"] == 1 and report["loaded"] == {"nodes": 4, "edges": 4}
    assert env.loaded == [path]
    raw = json.loads((env.settings.outputs_dir / "extract" / "vinfast_policy_a_raw.json").read_text("utf-8"))
    assert raw == {"a_c001": OUTPUT}


def test_second_document_is_merged_not_overwritten(env) -> None:
    ingest("a.md")
    ingest("b.md")
    doc = json.loads((env.settings.data_dir / "vinfast_policy.json").read_text(encoding="utf-8"))
    assert doc["stats"]["nodes"] == 3  # cùng entity/claim -> không nhân đôi
    assert [s["name"] for s in doc["sources"]] == ["a.md", "b.md"]
    vf3 = next(n for n in doc["nodes"] if n["properties"].get("name") == "VF3")
    assert vf3["properties"]["source_docs"] == ["a.md", "b.md"]


def test_from_raw_does_not_call_the_model_and_no_load_skips_neo4j(env) -> None:
    client = FakeClient()
    report = ingest(client=client, raw={"a_c001": OUTPUT}, load=False)
    assert client.calls == 0 and "loaded" not in report and env.loaded == []
    assert report["entities"] == 2
    assert not (env.settings.outputs_dir / "extract").exists()


@pytest.mark.parametrize("bad", ["../etc", "Vinfast", "a b", "", "1abc"])
def test_domain_name_cannot_escape_the_data_folder(env, bad) -> None:
    with pytest.raises(ValueError, match="domain không hợp lệ"):
        ingest(domain=bad)


def test_make_extractor_follows_provider(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "get_settings", lambda: SimpleNamespace(extract_provider="ollama"))
    assert pipeline.make_extractor().name == "ollama"
    assert pipeline.make_extractor("nvidia").name == "nvidia"
    with pytest.raises(ValueError, match="EXTRACT_PROVIDER"):
        pipeline.make_extractor("gemini")
