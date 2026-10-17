"""Test vòng lặp tìm kiếm + benchmark với client/graph GIẢ — không gọi mạng,
không cần Neo4j, không đụng server đang chạy."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.routers import benchmark as benchmark_router
from app.services import benchmark
from app.services.search import CHUNK, find_answer

# --- graph giả: VinFast -[MANUFACTURES]-> VF 8, VinFast -[SUBSIDIARY_OF]-> Vingroup
NODES = {
    "vinfast": {"id": "vinfast", "label": "Company",
                "properties": {"name": "VinFast", "description": "VinFast — hãng xe Việt Nam"}},
    "vf8": {"id": "vf8", "label": "CarModel",
            "properties": {"name": "VinFast VF 8", "description": "VinFast VF 8 — mẫu xe"}},
    "vf9": {"id": "vf9", "label": "CarModel",
            "properties": {"name": "VinFast VF 9", "description": "VinFast VF 9 — mẫu xe"}},
    "vingroup": {"id": "vingroup", "label": "Organization",
                 "properties": {"name": "Vingroup", "description": "Vingroup — công ty mẹ"}},
}
EDGES = [("vinfast", "MANUFACTURES", "vf8"), ("vinfast", "MANUFACTURES", "vf9"),
         ("vinfast", "SUBSIDIARY_OF", "vingroup")]


class FakeGraph:
    def __init__(self, extra_nodes: dict | None = None) -> None:
        self.extra = extra_nodes or {}

    def domains(self):
        return ["football_vn", "vinfast"]

    def labels(self, domain):
        if domain != "vinfast":
            return [{"label": "Player", "count": 1}]
        labels = {}
        for n in NODES.values():
            labels[n["label"]] = labels.get(n["label"], 0) + 1
        for label, nodes in self.extra.items():
            labels[label] = len(nodes)
        return [{"label": k, "count": v} for k, v in sorted(labels.items())]

    def nodes(self, domain, label):
        if label in self.extra:
            return self.extra[label]
        return [{"id": n["id"], "label": n["label"], "description": n["properties"]["description"]}
                for n in NODES.values() if n["label"] == label]

    def node(self, node_id):
        return NODES.get(node_id)

    def neighbors(self, node_id):
        out = []
        for s, t, kind in [(s, t, k) for s, k, t in EDGES]:
            if s == node_id:
                other, direction = t, "out"
            elif t == node_id:
                other, direction = s, "in"
            else:
                continue
            n = NODES[other]
            out.append({"edge_type": kind, "edge_props": {}, "target_id": other,
                        "target_label": n["label"],
                        "target_description": n["properties"]["description"],
                        "direction": direction})
        return out


def _pick(criteria: dict, needle: str) -> str:
    return next((k for k, v in criteria.items() if needle in v), next(iter(criteria)))


class SmartClient:
    """Trả lời đúng cho câu "Xe VF8 của công ty nào?"."""

    model_name = "fake-smart"

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    async def decide(self, state, questions):
        if self.delay:
            await asyncio.sleep(self.delay)
        answers = {}
        for qid, q in questions.items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": 0.95 if "(Company)" in state else 0.05}
            elif qid == "domain":
                answers[qid] = {"type": "choice", "choice": "vinfast"}
            elif qid == "label":
                answers[qid] = {"type": "choice", "choice": "CarModel"}
            elif qid == "node":
                answers[qid] = {"type": "choice", "choice": _pick(q["criteria"], "VF 8")}
            else:  # next
                answers[qid] = {"type": "choice", "choice": _pick(q["criteria"], "Company")}
        return {"answers": answers, "usage": {"input_tokens": 10, "cost": 0.001},
                "model_version": "fake-smart-v1"}


class NeverAnswersClient:
    """Không bao giờ nói 'đây là câu trả lời', luôn đi cạnh đầu tiên."""

    model_name = "fake-lost"

    async def decide(self, state, questions):
        answers = {}
        for qid, q in questions.items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": 0.0}
            else:
                answers[qid] = {"type": "choice", "choice": next(iter(q["criteria"]))}
        return {"answers": answers, "usage": {}}


def _new_result():
    return benchmark._empty_result("jev", "fake")


def test_vf8_question_finds_vinfast_via_incoming_edge() -> None:
    result = _new_result()
    asyncio.run(find_answer(SmartClient(), "Xe VF8 của công ty nào?", FakeGraph(), result))

    assert result["status"] == "found"
    assert result["answer_node_id"] == "vinfast"
    assert result["answer_text"] == "VinFast"
    assert result["domain"] == "vinfast" and result["label"] == "CarModel"
    assert [s["phase"] for s in result["steps"]] == ["domain", "label", "pick", "visit", "visit"]
    # bước cuối tới VinFast qua cạnh ĐI VÀO VF 8 (cạnh hai chiều mới đi được)
    assert result["steps"][-1]["node_id"] == "vinfast"
    assert result["steps"][-1]["via_edge"] == "MANUFACTURES (in)"
    assert result["tokens"] == 50 and round(result["cost"], 3) == 0.005
    assert result["model_version"] == "fake-smart-v1"


def test_terminates_with_not_found_when_model_never_answers() -> None:
    class Lost(NeverAnswersClient):
        async def decide(self, state, questions):
            if "domain" in questions:
                return {"answers": {"domain": {"type": "choice", "choice": "vinfast"}}, "usage": {}}
            return await super().decide(state, questions)

    result = _new_result()
    asyncio.run(find_answer(Lost(), "?", FakeGraph(), result))

    assert result["status"] == "not_found"
    visited = [s["node_id"] for s in result["steps"] if s["phase"] == "visit"]
    assert visited  # đã thật sự đi trên graph
    assert set(visited) <= set(NODES)  # chỉ đi trong graph, không lặp vô hạn


def test_empty_label_ends_as_not_found() -> None:
    result = _new_result()
    # NeverAnswersClient chọn domain đầu tiên (football_vn) -> label Player rỗng
    asyncio.run(find_answer(NeverAnswersClient(), "?", FakeGraph(), result))
    assert result["status"] == "not_found"
    assert "không có node nào" in result["error"]


def test_large_label_is_picked_in_chunks() -> None:
    total = CHUNK * 2 + 20  # 2 lô đầy + 1 lô 20
    many = [{"id": f"x{i}", "label": "Big", "description": f"thực thể {i}"} for i in range(total)]
    result = _new_result()

    class PickBig(NeverAnswersClient):
        async def decide(self, state, questions):
            if "domain" in questions:
                return {"answers": {"domain": {"type": "choice", "choice": "vinfast"}}, "usage": {}}
            if "label" in questions:
                return {"answers": {"label": {"type": "choice", "choice": "Big"}}, "usage": {}}
            return await super().decide(state, questions)

    graph = FakeGraph({"Big": many})
    asyncio.run(find_answer(PickBig(), "?", graph, result))
    picks = [s for s in result["steps"] if s["phase"] == "pick"]
    # 3 lô, rồi 1 lần chọn giữa 3 node thắng
    assert [p["candidates"] for p in picks] == [CHUNK, CHUNK, 20, 3]


def test_hub_neighbors_are_offered_in_chunks() -> None:
    """Node có 2 lô đầy + 20 cạnh: lô đầu model chọn "none" -> được đưa lô 2, 3 rồi
    mới quay lui; chọn được cạnh ở lô 3 thì đi tiếp bình thường."""
    hub = {"id": "hub", "label": "Hub", "properties": {"description": "đội tuyển"}}
    leaves = {f"p{i}": {"id": f"p{i}", "label": "Player",
                        "properties": {"name": f"P{i}", "description": f"cầu thủ {i}."}}
              for i in range(CHUNK * 2 + 20)}
    target = f"cầu thủ {CHUNK * 2 + 10}."  # nằm ở lô thứ 3; dấu "." để không khớp nhầm

    class HubGraph(FakeGraph):
        def domains(self):
            return ["football_vn"]

        def labels(self, domain):
            return [{"label": "Hub", "count": 1}]

        def nodes(self, domain, label):
            return [{"id": "hub", "label": "Hub", "description": "đội tuyển"}]

        def node(self, node_id):
            return hub if node_id == "hub" else leaves.get(node_id)

        def neighbors(self, node_id):
            others = list(leaves) if node_id == "hub" else ["hub"]
            return [{"edge_type": "MEMBER_OF", "edge_props": {}, "target_id": o,
                     "target_label": "Player" if o != "hub" else "Hub",
                     "target_description": (leaves.get(o) or hub)["properties"]["description"],
                     "direction": "in"} for o in others]

    class WantsTarget:
        model_name = "fake"

        async def decide(self, state, questions):
            answers = {}
            for qid, q in questions.items():
                if q["type"] == "noul":
                    answers[qid] = {"type": "noul", "noul": 0.9 if target in state else 0.0}
                else:
                    answers[qid] = {"type": "choice",
                                    "choice": _pick(q["criteria"], target)
                                    if any(target in v for v in q["criteria"].values())
                                    else "none"}
            return {"answers": answers, "usage": {}}

    result = _new_result()
    asyncio.run(find_answer(WantsTarget(), "?", HubGraph(), result))

    target_id = f"p{CHUNK * 2 + 10}"
    assert result["status"] == "found" and result["answer_node_id"] == target_id
    walk = [(s["phase"], s["candidates"]) for s in result["steps"]]
    assert walk == [("visit", CHUNK), ("more", CHUNK), ("more", 20), ("visit", 0)]
    assert [s["decision"] for s in result["steps"][:3]] == ["none", "none", target_id]


def test_timeout_marks_model_as_timeout() -> None:
    run = {"question": "?", "models": {"jev": _new_result()}}
    asyncio.run(benchmark._run_one(run, "jev", SmartClient(delay=0.2), FakeGraph(), timeout=0.05))
    assert run["models"]["jev"]["status"] == "timeout"


def test_error_in_one_model_is_isolated() -> None:
    class Broken:
        model_name = "broken"

        async def decide(self, state, questions):
            raise ConnectionError("API không kết nối được")

    run = {"question": "?", "models": {"llm": _new_result()}}
    asyncio.run(benchmark._run_one(run, "llm", Broken(), FakeGraph(), timeout=5))
    assert run["models"]["llm"]["status"] == "error"
    assert "không kết nối được" in run["models"]["llm"]["error"]


def test_full_run_writes_csv_and_history_roundtrips(tmp_path) -> None:
    async def scenario():
        clients = {"jev": SmartClient(), "llm": SmartClient()}
        run = benchmark.start_run("Xe VF8 của công ty nào?", "fake-llm", clients, FakeGraph(),
                                  timeout=5, outputs_dir=tmp_path)
        while run["status"] != "done":
            await asyncio.sleep(0.01)
        return run

    run = asyncio.run(scenario())
    assert {r["status"] for r in run["models"].values()} == {"found"}
    assert (tmp_path / "runs.csv").exists()
    assert (tmp_path / f"run_{run['id']}_trace.csv").exists()

    history = benchmark.list_history(tmp_path)
    assert history[0]["id"] == run["id"]
    assert history[0]["models"]["llm"]["model_name"] == "fake-llm"
    assert history[0]["models"]["jev"]["model_version"] == "fake-smart-v1"
    loaded = benchmark.load_run(run["id"], tmp_path)
    assert loaded["models"]["jev"]["answer_node_id"] == "vinfast"
    assert [s["node_id"] for s in loaded["models"]["jev"]["steps"] if s["phase"] == "visit"] == [
        "vf8", "vinfast"]


def test_stop_cancels_running_models(tmp_path) -> None:
    async def scenario():
        clients = {k: SmartClient(delay=1.0) for k in ("jev", "llm")}
        run = benchmark.start_run("?", "fake-llm", clients, FakeGraph(), timeout=30,
                                  outputs_dir=tmp_path)
        await asyncio.sleep(0.05)
        assert benchmark.stop_run(run["id"])
        while run["status"] != "done":
            await asyncio.sleep(0.01)
        return run

    run = asyncio.run(scenario())
    assert {r["status"] for r in run["models"].values()} == {"stopped"}


def test_api_runs_and_history(tmp_path, monkeypatch) -> None:
    class S:
        baseline_models = "fake-llm,other-llm"
        jev_model = "typesafe/jev-1.13"
        bench_timeout_seconds = 5
        outputs_dir = tmp_path

    monkeypatch.setattr(benchmark_router, "get_settings", lambda: S)
    monkeypatch.setattr(benchmark_router, "make_clients",
                        lambda llm: {"jev": SmartClient(), "llm": SmartClient()})
    monkeypatch.setattr(benchmark_router, "make_graph", FakeGraph)

    with TestClient(app) as client:
        assert client.get("/api/v1/benchmark/models").json() == {
            "llm": ["fake-llm", "other-llm"], "jev": "typesafe/jev-1.13"}
        assert client.post("/api/v1/benchmark/runs", json={"question": " "}).status_code == 422

        run = client.post("/api/v1/benchmark/runs", json={"question": "Xe VF8 của công ty nào?"}).json()
        assert run["llm_model"] == "fake-llm"
        for _ in range(200):
            state = client.get(f"/api/v1/benchmark/runs/{run['id']}").json()
            if state["status"] == "done":
                break
        assert state["status"] == "done"
        assert state["models"]["llm"]["answer_text"] == "VinFast"

        history = client.get("/api/v1/benchmark/history").json()
        assert history[0]["id"] == run["id"]
        assert client.get("/api/v1/benchmark/runs/khong-co").status_code == 404


def test_old_runs_csv_header_is_migrated(tmp_path) -> None:
    (tmp_path / "runs.csv").write_text(
        "run_id,started_at,question,model,model_name,status,answer_node_id,answer_text,"
        "elapsed_ms,calls,tokens,cost,domain,label,error\n"
        "old,2026-01-01T00:00:00+00:00,q,jev,j,found,a,A,1,1,1,0,d,l,\n",
        encoding="utf-8",
    )
    run = {"id": "new", "question": "q2", "started_at": "2026-02-01T00:00:00+00:00",
           "models": {k: {**benchmark._empty_result(k, k), "status": "found",
                          "model_version": f"{k}-v2"} for k in benchmark.MODEL_KEYS}}
    benchmark.write_csv(run, tmp_path)
    history = {r["id"]: r for r in benchmark.list_history(tmp_path)}
    assert history["old"]["models"]["jev"]["answer_text"] == "A"
    assert history["old"]["models"]["jev"]["model_version"] is None
    assert history["new"]["models"]["llm"]["model_version"] == "llm-v2"


def test_history_ignores_rows_of_removed_models(tmp_path) -> None:
    """runs.csv cũ còn dòng của Kev (đã bỏ khỏi benchmark) -> không hiện trong lịch sử."""
    run = {"id": "r1", "question": "q", "started_at": "2026-02-01T00:00:00+00:00",
           "models": {k: {**benchmark._empty_result(k, k), "status": "found"}
                      for k in benchmark.MODEL_KEYS}}
    benchmark.write_csv(run, tmp_path)
    with (tmp_path / "runs.csv").open("a", encoding="utf-8") as f:
        f.write("r1,2026-02-01T00:00:00+00:00,q,kev,kev-latest,v,found,a,A,1,1,1,0,d,l,\n")
    assert set(benchmark.list_history(tmp_path)[0]["models"]) == {"jev", "llm"}
