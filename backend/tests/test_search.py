"""Test vòng lặp tìm kiếm + benchmark với client/graph GIẢ — không gọi mạng,
không cần Neo4j, không đụng server đang chạy."""

from __future__ import annotations

import asyncio
import json

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

    run = {"question": "?", "models": {"nvidia": _new_result()}}
    asyncio.run(benchmark._run_one(run, "nvidia", Broken(), FakeGraph(), timeout=5))
    assert run["models"]["nvidia"]["status"] == "error"
    assert "không kết nối được" in run["models"]["nvidia"]["error"]


def test_full_run_writes_csv_and_history_roundtrips(tmp_path) -> None:
    async def scenario():
        clients = {k: SmartClient() for k in benchmark.MODEL_KEYS}
        run = benchmark.start_run("Xe VF8 của công ty nào?", clients, FakeGraph(),
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
    assert history[0]["models"]["nvidia"]["model_name"] == "fake-smart"
    assert history[0]["models"]["jev"]["model_version"] == "fake-smart-v1"
    loaded = benchmark.load_run(run["id"], tmp_path)
    assert loaded["models"]["jev"]["answer_node_id"] == "vinfast"
    assert [s["node_id"] for s in loaded["models"]["jev"]["steps"] if s["phase"] == "visit"] == [
        "vf8", "vinfast"]


def test_stop_cancels_running_models(tmp_path) -> None:
    async def scenario():
        clients = {k: SmartClient(delay=1.0) for k in benchmark.MODEL_KEYS}
        run = benchmark.start_run("?", clients, FakeGraph(), timeout=30,
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
        ollama_model = "gemma4:12b"
        nvidia_model = "openai/gpt-oss-20b"
        jev_model = "typesafe/jev-1.13"
        bench_timeout_seconds = 5
        outputs_dir = tmp_path
        cases_dir = tmp_path / "cases"

    monkeypatch.setattr(benchmark_router, "get_settings", lambda: S)
    monkeypatch.setattr(benchmark_router, "make_clients",
                        lambda: {k: SmartClient() for k in benchmark.MODEL_KEYS})
    monkeypatch.setattr(benchmark_router, "make_graph", FakeGraph)

    async def fake_version():
        return "gemma4:12b · 11.9B · Q4_K_M"

    monkeypatch.setattr(benchmark_router, "ollama_version", fake_version)

    with TestClient(app) as client:
        assert client.get("/api/v1/benchmark/models").json() == {
            "jev": "typesafe/jev-1.13",
            "ollama": {"model": "gemma4:12b", "version": "gemma4:12b · 11.9B · Q4_K_M"},
            "nvidia": {"model": "openai/gpt-oss-20b"}}
        assert client.post("/api/v1/benchmark/runs", json={"question": " "}).status_code == 422

        run = client.post("/api/v1/benchmark/runs", json={"question": "Xe VF8 của công ty nào?"}).json()
        for _ in range(200):
            state = client.get(f"/api/v1/benchmark/runs/{run['id']}").json()
            if state["status"] == "done":
                break
        assert state["status"] == "done"
        assert state["models"]["nvidia"]["answer_text"] == "VinFast"

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
    assert history["new"]["models"]["nvidia"]["model_version"] == "nvidia-v2"


def test_history_ignores_rows_of_removed_models(tmp_path) -> None:
    """runs.csv cũ còn dòng của Kev (đã bỏ khỏi benchmark) -> không hiện trong lịch sử."""
    run = {"id": "r1", "question": "q", "started_at": "2026-02-01T00:00:00+00:00",
           "models": {k: {**benchmark._empty_result(k, k), "status": "found"}
                      for k in benchmark.MODEL_KEYS}}
    benchmark.write_csv(run, tmp_path)
    with (tmp_path / "runs.csv").open("a", encoding="utf-8") as f:
        f.write("r1,2026-02-01T00:00:00+00:00,q,kev,kev-latest,v,found,a,A,1,1,1,0,d,l,\n")
    assert set(benchmark.list_history(tmp_path)[0]["models"]) == set(benchmark.MODEL_KEYS)


# --- ground truth: case_id, expected_answers, correct ---------------------------------

def _run_case(tmp_path, answers: list[str] | None):
    case = {"id": "vinfast-001", "answers": answers} if answers is not None else None

    async def scenario():
        clients = {k: SmartClient() for k in benchmark.MODEL_KEYS}
        run = benchmark.start_run("Xe VF8 của công ty nào?", clients, FakeGraph(),
                                  timeout=5, outputs_dir=tmp_path, case=case)
        while run["status"] != "done":
            await asyncio.sleep(0.01)
        return run

    return asyncio.run(scenario())


def test_grade_only_judges_runs_that_found_an_answer() -> None:
    found = {"status": "found", "answer_node_id": "vinfast"}
    assert benchmark.grade(["vinfast", "vinfast_alt"], found) is True
    assert benchmark.grade(["vingroup"], found) is False
    assert benchmark.grade(["vinfast"], {"status": "not_found", "answer_node_id": None}) is None
    assert benchmark.grade(["vinfast"], {"status": "timeout", "answer_node_id": None}) is None
    assert benchmark.grade(None, found) is None  # câu gõ tay không có đáp án


def test_run_with_case_grades_every_model_and_writes_csv(tmp_path) -> None:
    run = _run_case(tmp_path, ["vinfast", "vinfast_alt"])
    assert run["case_id"] == "vinfast-001"
    assert {r["correct"] for r in run["models"].values()} == {True}

    header, *rows = (tmp_path / "runs.csv").read_text(encoding="utf-8").splitlines()
    assert "case_id" in header and "expected_answers" in header and "correct" in header
    assert all("vinfast-001" in r and "vinfast|vinfast_alt" in r and ",true," in r for r in rows)

    history = benchmark.list_history(tmp_path)[0]
    assert history["case_id"] == "vinfast-001"
    assert history["expected_answers"] == ["vinfast", "vinfast_alt"]
    assert history["models"]["jev"]["correct"] is True


def test_wrong_answer_is_false_and_manual_question_is_ungraded(tmp_path) -> None:
    wrong = _run_case(tmp_path, ["vingroup"])
    assert {r["correct"] for r in wrong["models"].values()} == {False}
    assert benchmark.list_history(tmp_path)[0]["models"]["nvidia"]["correct"] is False

    manual = _run_case(tmp_path / "manual", None)
    assert {r["correct"] for r in manual["models"].values()} == {None}
    only = benchmark.list_history(tmp_path / "manual")[0]
    assert only["case_id"] is None and only["models"]["jev"]["correct"] is None


def test_api_starts_a_ground_truth_case(tmp_path, monkeypatch) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "vinfast.json").write_text(json.dumps({"domain": "vinfast", "cases": [
        {"id": "vinfast-001", "question": "Xe VF8 của công ty nào?", "answers": ["vinfast"], "hops": 1}]}),
        encoding="utf-8")

    class S:
        ollama_model = "gemma4:12b"
        nvidia_model = "openai/gpt-oss-20b"
        jev_model = "j"
        bench_timeout_seconds = 5
        outputs_dir = tmp_path
        cases_dir = tmp_path / "cases"

    monkeypatch.setattr(benchmark_router, "get_settings", lambda: S)
    monkeypatch.setattr(benchmark_router, "make_clients",
                        lambda: {k: SmartClient() for k in benchmark.MODEL_KEYS})
    monkeypatch.setattr(benchmark_router, "make_graph", FakeGraph)

    with TestClient(app) as client:
        listed = client.get("/api/v1/benchmark/cases").json()
        assert listed == [{"id": "vinfast-001", "domain": "vinfast",
                           "question": "Xe VF8 của công ty nào?", "hops": 1}]  # không lộ đáp án
        assert client.post("/api/v1/benchmark/runs", json={"case_id": "nope"}).status_code == 422

        run = client.post("/api/v1/benchmark/runs", json={"case_id": "vinfast-001"}).json()
        assert run["question"] == "Xe VF8 của công ty nào?" and run["case_id"] == "vinfast-001"
        for _ in range(200):
            state = client.get(f"/api/v1/benchmark/runs/{run['id']}").json()
            if state["status"] == "done":
                break
        assert {r["correct"] for r in state["models"].values()} == {True}


def test_edge_description_is_shown_to_the_model_only_when_the_edge_has_one() -> None:
    from app.services.search import _edge_options

    plain = {"edge_type": "MANUFACTURES", "edge_props": {}, "target_id": "vf8", "target_label": "CarModel",
             "target_description": "VF 8 — mẫu xe", "direction": "out"}
    fact = {"edge_type": "RELATED_TO", "edge_props": {"description": "VF3 tham gia chương trình"},
            "target_id": "p", "target_label": "Program", "target_description": "Ưu đãi mùa xuân",
            "direction": "in"}
    _, criteria = _edge_options([plain, fact])
    assert criteria["e0"] == "MANUFACTURES → CarModel: VF 8 — mẫu xe"  # không đổi so với bản 1.0.0
    assert criteria["e1"] == "RELATED_TO ← Program: Ưu đãi mùa xuân [VF3 tham gia chương trình]"


def test_walks_from_an_entity_through_a_claim_node_to_the_answer() -> None:
    """Claim là node trung gian (Entity -HAS_CLAIM-> Claim -ABOUT-> Entity), không có `name`:
    answer_text lấy từ description."""
    nodes = {
        "vf3": {"id": "vf3", "label": "Product", "properties": {"name": "VF3", "description": "VF3 — xe"}},
        "claim": {"id": "claim", "label": "Claim", "properties": {"description": "VF3 giảm 30% từ 15/01"}},
    }
    edges = [{"edge_type": "HAS_CLAIM", "edge_props": {}, "target_id": "claim", "target_label": "Claim",
              "target_description": "VF3 giảm 30% từ 15/01", "direction": "out"}]

    class ClaimGraph:
        def domains(self): return ["vinfast_policy"]
        def labels(self, domain): return [{"label": "Product", "count": 1}]
        def nodes(self, domain, label): return [{"id": "vf3", "label": "Product", "description": "VF3 — xe"}]
        def node(self, node_id): return nodes.get(node_id)
        def neighbors(self, node_id):
            return edges if node_id == "vf3" else [
                {**edges[0], "target_id": "vf3", "target_label": "Product", "direction": "in"}]

    class Client:
        model_name = "fake"

        async def decide(self, state, questions):
            on_claim = "(Claim)" in state
            return {"answers": {
                qid: {"type": "noul", "noul": 0.9 if on_claim else 0.1} if q["type"] == "noul"
                else {"type": "choice", "choice": _pick(q["criteria"], "Claim")}
                for qid, q in questions.items()}, "usage": {}}

    result = _new_result()
    asyncio.run(find_answer(Client(), "VF3 được giảm bao nhiêu?", ClaimGraph(), result))
    assert result["status"] == "found" and result["answer_node_id"] == "claim"
    assert result["answer_text"] == "VF3 giảm 30% từ 15/01"
