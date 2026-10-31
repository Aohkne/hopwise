"""Vòng lặp tìm câu trả lời trên Knowledge Graph — dùng CHUNG cho Jev và LLM.

Model tự tìm điểm vào (cách A đã thống nhất), không có bước tìm từ khoá bằng code:
  1. chọn domain
  2. chọn loại node (label) trong domain
  3. chọn node cụ thể — nếu loại đó có quá CHUNK node thì chia lô, chọn node tốt
     nhất từng lô rồi chọn lại 1 lần giữa các node thắng
  4. đi theo cạnh (hai chiều): ở mỗi node hỏi song song "node này đã là câu trả
     lời chưa?" (Noul) và "đi tiếp cạnh nào?" (Choice). Lưu node đã thăm, gặp ngõ
     cụt thì quay lui (DFS). Hết node chưa thăm = "không tìm ra".

Mọi quyết định đều đi qua `client.decide(state, questions)` theo schema TypeSafe
System One, nên 2 model chạy đúng một quy trình. Giới hạn thời gian (5 phút) do
benchmark.py áp lên toàn bộ hàm này bằng asyncio.wait_for.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

from app.config import get_settings
from app.services import neo4j_client

# Số lựa chọn mỗi câu Choice, đặt bằng BENCH_CHUNK trong .env, áp như nhau cho cả
# 2 model. Jev cho tối đa 255 lựa chọn mỗi câu.
CHUNK = get_settings().bench_chunk
# Chốt an toàn số lần gọi model — KHÔNG dùng để so sánh model, chỉ tránh tốn
# tiền vô ích nếu có lỗi (Jev trả lời vài trăm ms, có thể gọi hàng nghìn lần/5p).
MAX_CALLS = 300
ANSWER_THRESHOLD = 0.5

DOMAIN_DESCRIPTIONS = {
    "football_vn": "Bóng đá Việt Nam: đội tuyển quốc gia, V.League 1, cầu thủ, câu lạc bộ, "
    "huấn luyện viên, sân vận động, nơi sinh, danh hiệu",
    "vinfast": "VinFast: hãng xe ô tô Việt Nam, hội đồng quản trị, cổ đông, công ty con, nhà máy, "
    "thương hiệu và các mẫu xe, thị trường bán xe, người sáng lập, công ty mẹ Vingroup",
    "vinfast_policy": "Chính sách bán hàng và ưu đãi ô tô điện VinFast trích xuất từ văn bản: chương "
    "trình ưu đãi, mức giảm giá, điều kiện áp dụng, thời hạn, mẫu xe, đối tượng khách hàng, đại lý",
}


class Graph(Protocol):
    def domains(self) -> list[str]: ...
    def labels(self, domain: str) -> list[dict]: ...
    def nodes(self, domain: str, label: str) -> list[dict]: ...
    def node(self, node_id: str) -> dict | None: ...
    def neighbors(self, node_id: str) -> list[dict]: ...


class Neo4jGraph:
    """Graph thật, đọc từ Neo4j."""

    def domains(self) -> list[str]:
        return neo4j_client.list_domains()

    def labels(self, domain: str) -> list[dict]:
        return neo4j_client.list_labels(domain)

    def nodes(self, domain: str, label: str) -> list[dict]:
        return neo4j_client.list_nodes(domain, label)

    def node(self, node_id: str) -> dict | None:
        return neo4j_client.get_node(node_id)

    def neighbors(self, node_id: str) -> list[dict]:
        return neo4j_client.get_neighbors(node_id)


class _Budget:
    def __init__(self, result: dict) -> None:
        self.result = result

    def check(self) -> None:
        if len(self.result["steps"]) >= MAX_CALLS:
            raise _SafetyCapReached


class _SafetyCapReached(Exception):
    pass


def _usage(raw: dict) -> tuple[int, float]:
    """Gộp usage của 3 client về (tokens đầu vào, chi phí USD)."""
    tokens = raw.get("input_tokens") or raw.get("prompt_tokens") or 0
    cost = raw.get("cost") or 0.0
    return int(tokens), float(cost)


async def _ask(client: Any, result: dict, phase: str, state: str, questions: dict,
               **extra: Any) -> dict:
    """1 lần gọi model, ghi lại 1 bước vào trace."""
    _Budget(result).check()
    started = time.perf_counter()
    reply = await client.decide(state, questions)
    tokens, cost = _usage(reply.get("usage", {}))
    step = {
        "step": len(result["steps"]) + 1,
        "phase": phase,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "tokens": tokens,
        "cost": cost,
        **extra,
    }
    result["steps"].append(step)
    if reply.get("model_version"):
        result["model_version"] = reply["model_version"]
    result["tokens"] += tokens
    result["cost"] += cost
    return reply["answers"]


def _choice(answers: dict, qid: str) -> str | None:
    value = answers.get(qid, {}).get("choice")
    return str(value) if value is not None else None


def _noul(answers: dict, qid: str) -> float:
    value = answers.get(qid, {}).get("noul")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def _pick_node(client: Any, result: dict, question: str, candidates: list[dict]) -> dict:
    """Chọn 1 node trong danh sách; chia lô nếu quá CHUNK."""
    if len(candidates) == 1:
        return candidates[0]
    pool = candidates
    while len(pool) > 1:
        winners = []
        for start in range(0, len(pool), CHUNK):
            chunk = pool[start:start + CHUNK]
            if len(chunk) == 1:
                winners.append(chunk[0])
                continue
            options = {f"n{i}": c for i, c in enumerate(chunk)}
            answers = await _ask(
                client, result, "pick", f"Câu hỏi: {question}",
                {"node": {
                    "type": "choice",
                    "instructions": "Node nào là điểm bắt đầu tốt nhất để tìm câu trả lời "
                                    "cho câu hỏi?",
                    "criteria": {k: (c["description"] or c["id"]) for k, c in options.items()},
                }},
                candidates=len(chunk),
            )
            key = _choice(answers, "node")
            winners.append(options.get(key, chunk[0]))
            result["steps"][-1]["decision"] = winners[-1]["id"]
        pool = winners
    return pool[0]


def _edge_options(page: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """Lô cạnh -> (key -> neighbor, criteria cho câu Choice "next", kèm "none")."""
    options = {f"e{i}": n for i, n in enumerate(page)}
    criteria = {k: _edge_text(n) for k, n in options.items()}
    criteria["none"] = "Không còn hướng nào liên quan tới câu hỏi"
    return options, criteria


def _edge_text(n: dict) -> str:
    text = (f"{n['edge_type']} {'→' if n.get('direction') == 'out' else '←'} "
            f"{n['target_label']}: {n['target_description'] or n['target_id']}")
    # Cạnh sinh từ văn bản (bản 2.0.0) đều mang loại RELATED_TO; chỉ mô tả của cạnh mới cho
    # model biết quan hệ là gì. Cạnh cũ không có mô tả nên prompt không đổi.
    detail = (n.get("edge_props") or {}).get("description")
    return f"{text} [{detail}]" if detail else text


async def find_answer(client: Any, question: str, graph: Graph, result: dict) -> None:
    """Chạy toàn bộ quy trình, ghi tiến độ thẳng vào `result` (để API đọc giữa chừng).

    Kết thúc với result["status"] ∈ {"found", "not_found"}; timeout/stop/lỗi do
    benchmark.py đặt.
    """
    try:
        await _run(client, question, graph, result)
    except _SafetyCapReached:
        result["status"] = "not_found"
        result["error"] = f"chạm chốt an toàn {MAX_CALLS} lần gọi"


async def _run(client: Any, question: str, graph: Graph, result: dict) -> None:
    # 1. domain
    domains = graph.domains()
    if not domains:
        result["status"] = "not_found"
        result["error"] = "KB chưa có dữ liệu"
        return
    if len(domains) == 1:
        domain = domains[0]
    else:
        answers = await _ask(
            client, result, "domain", f"Câu hỏi: {question}",
            {"domain": {
                "type": "choice",
                "instructions": "Câu hỏi thuộc chủ đề (domain) nào của knowledge base?",
                "criteria": {d: DOMAIN_DESCRIPTIONS.get(d, d) for d in domains},
            }},
        )
        domain = _choice(answers, "domain") or domains[0]
        if domain not in domains:
            domain = domains[0]
        result["steps"][-1]["decision"] = domain
    result["domain"] = domain

    # 2. loại node
    labels = graph.labels(domain)
    if len(labels) == 1:
        label = labels[0]["label"]
    else:
        answers = await _ask(
            client, result, "label", f"Câu hỏi: {question}\nDomain: {domain}",
            {"label": {
                "type": "choice",
                "instructions": "Nên bắt đầu tìm từ loại thực thể nào?",
                "criteria": {lb["label"]: f"{lb['label']} ({lb['count']} thực thể)"
                             for lb in labels},
            }},
        )
        names = [lb["label"] for lb in labels]
        label = _choice(answers, "label")
        if label not in names:
            label = names[0]
        result["steps"][-1]["decision"] = label
    result["label"] = label

    # 3. node bắt đầu
    candidates = graph.nodes(domain, label)
    if not candidates:
        result["status"] = "not_found"
        result["error"] = f"loại {label} trong {domain} không có node nào"
        return
    start = await _pick_node(client, result, question, candidates)

    # 4. đi theo cạnh, DFS có quay lui
    visited: set[str] = set()
    stack: list[str] = []
    current = start["id"]
    via: tuple[str | None, str | None] = (None, None)  # (from_node_id, edge mô tả)

    while True:
        visited.add(current)
        node = graph.node(current) or {"id": current, "label": "?", "properties": {}}
        caption = node["properties"].get("description") or current
        unvisited = [n for n in graph.neighbors(current) if n["target_id"] not in visited]
        # Node nhiều cạnh (VD đội tuyển QG ~142) -> chia lô CHUNK cạnh: lô đầu hỏi kèm
        # "đã là đáp án chưa?", model chọn "none" thì đưa lô tiếp theo (phase "more").
        pages = [unvisited[i:i + CHUNK] for i in range(0, len(unvisited), CHUNK)] or [[]]

        options, criteria = _edge_options(pages[0])
        answers = await _ask(
            client, result, "visit",
            f"Câu hỏi: {question}\nNode hiện tại ({node['label']}): {caption}",
            {
                # Phải định nghĩa rõ true/false: hỏi mơ hồ "có phải câu trả lời
                # không?" thì Jev coi node ĐƯỢC NHẮC trong câu hỏi (VD "VF 8" trong
                # "Xe VF8 của công ty nào?") là đáp án — đã gặp khi chạy thật.
                "answer": {
                    "type": "noul",
                    "instructions": "Câu hỏi đang hỏi về một thực thể chưa biết. Node hiện tại "
                                    "có CHÍNH LÀ thực thể mà câu hỏi muốn tìm (đáp án) không?",
                    "criteria": {
                        "true": "Node hiện tại là đáp án của câu hỏi.",
                        "false": "Node hiện tại chỉ là thực thể được nhắc tới trong câu hỏi, "
                                 "hoặc chỉ liên quan, chưa phải đáp án.",
                    },
                },
                "next": {
                    "type": "choice",
                    "instructions": "Nên đi tiếp theo cạnh nào để tới câu trả lời?",
                    "criteria": criteria,
                },
            },
            node_id=current, node_label=node["label"], node_caption=caption,
            from_node_id=via[0], via_edge=via[1], candidates=len(pages[0]),
        )
        score = _noul(answers, "answer")
        result["steps"][-1]["answer_score"] = round(score, 3)

        if score >= ANSWER_THRESHOLD:
            result["status"] = "found"
            result["answer_node_id"] = current
            result["answer_text"] = str(
                node["properties"].get("name")
                or node["properties"].get("name_vi")
                or caption
            )
            return

        key = _choice(answers, "next")
        for page in pages[1:]:
            if key in options:
                break
            result["steps"][-1]["decision"] = "none"
            options, criteria = _edge_options(page)
            answers = await _ask(
                client, result, "more",
                f"Câu hỏi: {question}\nNode hiện tại ({node['label']}): {caption}",
                {"next": {
                    "type": "choice",
                    "instructions": "Nên đi tiếp theo cạnh nào để tới câu trả lời?",
                    "criteria": criteria,
                }},
                node_id=current, node_label=node["label"], node_caption=caption,
                candidates=len(page),
            )
            key = _choice(answers, "next")

        if key in options:
            nxt = options[key]
            result["steps"][-1]["decision"] = nxt["target_id"]
            stack.append(current)
            edge = f"{nxt['edge_type']} ({'out' if nxt.get('direction') == 'out' else 'in'})"
            via = (current, edge)
            current = nxt["target_id"]
            continue

        # ngõ cụt: quay lui tới node gần nhất còn neighbor chưa thăm
        result["steps"][-1]["decision"] = "none"
        while stack:
            back = stack.pop()
            if any(n["target_id"] not in visited for n in graph.neighbors(back)):
                via = (back, "backtrack")
                current = back
                visited.discard(back)  # cho phép hỏi lại tại node này với tập neighbor mới
                break
        else:
            result["status"] = "not_found"
            return
