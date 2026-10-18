"""Đọc Knowledge Graph từ data/*.json và đi theo chuỗi cạnh — dùng chung cho
generate_cases.py (sinh câu hỏi) và verify_cases.py (kiểm tra lại).

Chỉ dùng thư viện chuẩn. Ý tưởng chính: một câu hỏi hợp lệ khi đi từ node neo
(anchor) theo chuỗi cạnh cố định thì MỖI bước chỉ ra đúng 1 node. Khi đó đáp án
là duy nhất và tính ra được từ graph, không cần ai viết tay.
"""

from __future__ import annotations

import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

NAME_KEYS = ("name", "name_vi", "name_en", "short_name")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    no_marks = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return no_marks.replace("đ", "d").replace("Đ", "D").lower().strip()


def normalize(text: str) -> str:
    """Bỏ dấu, thường hoá, gộp khoảng trắng — để so tên không phụ thuộc cách gõ."""
    return re.sub(r"\s+", " ", strip_accents(text))


@dataclass(frozen=True)
class Step:
    """1 bước đi: theo cạnh `edge` (out = đi theo chiều cạnh, in = đi ngược)."""

    edge: str
    dir: str  # "out" | "in"
    label: str | None = None  # node đích phải có label này
    where: tuple[tuple[str, str], ...] = ()  # (thuộc tính của cạnh, tên tham số)


@dataclass
class Walk:
    """Kết quả đi hết 1 chuỗi: đường đi (mỗi bước đúng 1 node) và tập đáp án."""

    path: list[dict]  # [{"node": id, "edge": None | "TYPE (out|in)"}]
    answers: list[str]  # mọi node cùng thực thể với node cuối (qua SAME_AS)


@dataclass
class KG:
    domain: str
    doc: dict
    nodes: dict[str, dict] = field(default_factory=dict)
    out: dict[str, list[dict]] = field(default_factory=dict)
    inc: dict[str, list[dict]] = field(default_factory=dict)
    _cls: dict[str, frozenset[str]] = field(default_factory=dict)
    _names: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, domain: str) -> "KG":
        return cls.from_doc(domain, json.loads((DATA / f"{domain}.json").read_text(encoding="utf-8")))

    @classmethod
    def from_doc(cls, domain: str, doc: dict) -> "KG":
        kg = cls(domain=domain, doc=doc)
        kg.nodes = {n["id"]: n for n in doc["nodes"]}
        for i in kg.nodes:
            kg.out[i], kg.inc[i] = [], []
        for e in doc["edges"]:
            kg.out[e["from"]].append(e)
            kg.inc[e["to"]].append(e)
        kg._build_classes()
        kg._build_names()
        return kg

    # --- thực thể trùng (SAME_AS) ------------------------------------------
    def _build_classes(self) -> None:
        parent = {i: i for i in self.nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for e in self.doc["edges"]:
            if e["type"] == "SAME_AS":
                parent[find(e["from"])] = find(e["to"])
        groups: dict[str, set[str]] = {}
        for i in self.nodes:
            groups.setdefault(find(i), set()).add(i)
        self._cls = {i: frozenset(groups[find(i)]) for i in self.nodes}

    def members(self, node_id: str) -> frozenset[str]:
        return self._cls[node_id]

    def key(self, node_id: str) -> str:
        return min(self._cls[node_id])

    # --- tên ---------------------------------------------------------------
    def variants(self, node_id: str) -> set[str]:
        """Mọi tên đã chuẩn hoá của thực thể (gồm cả node SAME_AS)."""
        out = set()
        for m in self.members(node_id):
            props = self.nodes[m]["properties"]
            out |= {normalize(props[k]) for k in NAME_KEYS if isinstance(props.get(k), str) and props[k]}
            out.add(normalize(self.display(m)))
        return {v for v in out if v}

    def display(self, node_id: str) -> str:
        """Tên dùng trong câu hỏi. Mẫu xe VinFast bỏ tiền tố "VinFast " ("VF 8")
        để tên hãng không lộ vào câu hỏi."""
        node = self.nodes[node_id]
        props = node["properties"]
        name = next((props[k] for k in ("name_vi", "name", "name_en") if props.get(k)), node_id)
        if node["label"] == "CarModel" and name.startswith("VinFast ") and len(name) > 9:
            name = name[len("VinFast "):]
        # Bỏ phần chú thích kiểu Wikipedia: "Nguyễn Minh Châu (cầu thủ bóng đá)"
        short = re.sub(r"\s*\([^)]*\)\s*$", "", name)
        return short or name

    def _build_names(self) -> None:
        for i in self.nodes:
            for v in self.variants(i):
                self._names.setdefault(v, set()).add(self.key(i))

    def name_is_unique(self, node_id: str) -> bool:
        """Tên hiển thị của node không trùng thực thể nào khác trong domain."""
        shown = normalize(self.display(node_id))
        if re.fullmatch(r"q\d+", shown):  # node chưa có nhãn, chỉ có QID
            return False
        return self._names.get(shown, set()) == {self.key(node_id)}

    def degree(self, node_id: str) -> int:
        return sum(len(self.out[m]) + len(self.inc[m]) for m in self.members(node_id))

    # --- đi theo chuỗi cạnh --------------------------------------------------
    def _step(self, cur: frozenset[str], step: Step, params: dict) -> dict[str, tuple[str, dict]]:
        """Các node đạt được sau 1 bước: key thực thể -> (node đích, cạnh đi qua)."""
        hits: dict[str, tuple[str, dict]] = {}
        for m in sorted(cur):
            for e in (self.out[m] if step.dir == "out" else self.inc[m]):
                if e["type"] != step.edge:
                    continue
                other = e["to"] if step.dir == "out" else e["from"]
                if step.label and self.nodes[other]["label"] != step.label:
                    continue
                if any(e["properties"].get(k) != params.get(p) for k, p in step.where):
                    continue
                hits.setdefault(self.key(other), (other, e))
        return hits

    def walk(self, start: str, steps: list[Step], params: dict) -> Walk | None:
        """Đi từ `start`; trả None nếu có bước ra 0 hoặc ≥2 node, hoặc đường quay lại node cũ."""
        cur = self.members(start)
        seen = {self.key(start)}
        path = [{"node": start, "edge": None}]
        for step in steps:
            hits = self._step(cur, step, params)
            if len(hits) != 1:
                return None
            (k, (other, _edge)), = hits.items()
            if k in seen:
                return None
            seen.add(k)
            path.append({"node": other, "edge": f"{step.edge} ({step.dir})"})
            cur = self.members(other)
        return Walk(path=path, answers=sorted(cur))

    def param_values(self, start: str, step: Step) -> list[dict]:
        """Các giá trị tham số có thể có ở bước đầu (VD mọi `pct` của cạnh SHAREHOLDER_OF)."""
        if not step.where:
            return [{}]
        combos: list[dict] = []
        for m in sorted(self.members(start)):
            for e in (self.out[m] if step.dir == "out" else self.inc[m]):
                if e["type"] == step.edge and all(k in e["properties"] for k, _ in step.where):
                    combo = {p: e["properties"][k] for k, p in step.where}
                    if combo not in combos:
                        combos.append(combo)
        return combos
