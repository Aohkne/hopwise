"""Mẫu câu hỏi và hàm dựng 1 test case từ graph.

Một mẫu = 1 node neo + 1 chuỗi cạnh + 1 câu hỏi tiếng Việt. Câu hỏi chỉ được tạo
khi đi hết chuỗi ra ĐÚNG 1 thực thể ở mỗi bước (xem kg.KG.walk). Mỗi mẫu chỉ là
cách *hỏi* — đáp án luôn do graph quyết định, không có giá trị nào viết tay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from kg import KG, Step, normalize

# Node bị loại khỏi mọi câu hỏi sau khi người duyệt xem lại — mỗi dòng ghi lý do.
EXCLUDED_NODES = {
    "Q850270_concept_car": "Wikidata còn ghi VF 3 là concept car dù xe đã bán đại trà",
}

HUB_DEGREE = 40  # node có từ ngần này cạnh trở lên = "hub", nhiều đường rẽ gây nhiễu


def out(edge: str, label: str | None = None, where: tuple = ()) -> Step:
    return Step(edge, "out", label, where)


def inc(edge: str, label: str | None = None, where: tuple = ()) -> Step:
    return Step(edge, "in", label, where)


@dataclass
class Template:
    id: str
    domain: str
    anchor_label: str
    steps: list[Step]
    text: str  # {a} = tên node neo, {tên_tham_số} = tham số của cạnh
    fmt: dict[str, Callable[[object], str | None]] = field(default_factory=dict)

    @property
    def hops(self) -> int:
        return len(self.steps)


# --- định dạng tham số sang tiếng Việt (trả None = bỏ qua giá trị này) ----------

def vi_percent(value: object) -> str | None:
    return f"{float(value):g}".replace(".", ",") if value not in (None, "") and re.fullmatch(r"[\d.]+", str(value)) else None


# Chỉ dịch các giá trị đã biết chắc nghĩa; giá trị khác bị bỏ qua chứ không đoán.
TITLES = {
    "Independent Director": "thành viên độc lập (Independent Director)",
    "Director": "thành viên (Director)",
}
RELATIONSHIPS = {"Joint Venture": "liên doanh (Joint Venture)"}


def mapped(table: dict[str, str]) -> Callable[[object], str | None]:
    return lambda v: table.get(str(v))


# --- bóng đá ----------------------------------------------------------------------

FOOTBALL = [
    # 1 bước
    Template("f_born", "football_vn", "Player", [out("BORN_IN", "Place")],
             "Cầu thủ {a} sinh ra ở đâu?"),
    Template("f_venue", "football_vn", "Club", [out("HOME_VENUE", "Place")],
             "Sân nhà của câu lạc bộ {a} là sân nào?"),
    Template("f_won", "football_vn", "Club", [out("WON", "Competition")],
             "Câu lạc bộ {a} đã vô địch giải đấu nào?"),
    Template("f_club_of", "football_vn", "Player", [out("PLAYED_FOR", "Club")],
             "Cầu thủ {a} từng thi đấu cho câu lạc bộ nào?"),
    Template("f_player_of", "football_vn", "Club", [inc("PLAYED_FOR", "Player")],
             "Cầu thủ nào từng thi đấu cho câu lạc bộ {a}?"),
    Template("f_venue_of", "football_vn", "Place", [inc("HOME_VENUE", "Club")],
             "Câu lạc bộ nào có sân nhà là {a}?"),
    Template("f_winner", "football_vn", "Competition", [inc("WON", "Club")],
             "Câu lạc bộ nào đã vô địch {a}?"),
    Template("f_born_here", "football_vn", "Place", [inc("BORN_IN", "Player")],
             "Cầu thủ nào sinh ra ở {a}?"),
    # 2 bước
    Template("f_p_club_venue", "football_vn", "Player",
             [out("PLAYED_FOR", "Club"), out("HOME_VENUE", "Place")],
             "Câu lạc bộ mà cầu thủ {a} từng thi đấu có sân nhà là sân nào?"),
    Template("f_p_club_won", "football_vn", "Player",
             [out("PLAYED_FOR", "Club"), out("WON", "Competition")],
             "Câu lạc bộ mà cầu thủ {a} từng thi đấu đã vô địch giải đấu nào?"),
    Template("f_club_player_born", "football_vn", "Club",
             [inc("PLAYED_FOR", "Player"), out("BORN_IN", "Place")],
             "Cầu thủ từng thi đấu cho câu lạc bộ {a} sinh ra ở đâu?"),
    Template("f_venue_player", "football_vn", "Place",
             [inc("HOME_VENUE", "Club"), inc("PLAYED_FOR", "Player")],
             "Cầu thủ nào từng thi đấu cho câu lạc bộ có sân nhà là {a}?"),
    Template("f_comp_player", "football_vn", "Competition",
             [inc("WON", "Club"), inc("PLAYED_FOR", "Player")],
             "Cầu thủ nào từng thi đấu cho câu lạc bộ đã vô địch {a}?"),
    Template("f_born_club", "football_vn", "Place",
             [inc("BORN_IN", "Player"), out("PLAYED_FOR", "Club")],
             "Cầu thủ sinh ra ở {a} từng thi đấu cho câu lạc bộ nào?"),
    Template("f_comp_club_venue", "football_vn", "Competition",
             [inc("WON", "Club"), out("HOME_VENUE", "Place")],
             "Câu lạc bộ đã vô địch {a} có sân nhà là sân nào?"),
    # 3 bước
    Template("f_venue_player_born", "football_vn", "Place",
             [inc("HOME_VENUE", "Club"), inc("PLAYED_FOR", "Player"), out("BORN_IN", "Place")],
             "Cầu thủ từng thi đấu cho câu lạc bộ có sân nhà là {a} sinh ra ở đâu?"),
    Template("f_comp_player_born", "football_vn", "Competition",
             [inc("WON", "Club"), inc("PLAYED_FOR", "Player"), out("BORN_IN", "Place")],
             "Cầu thủ từng thi đấu cho câu lạc bộ đã vô địch {a} sinh ra ở đâu?"),
    Template("f_born_club_venue", "football_vn", "Place",
             [inc("BORN_IN", "Player"), out("PLAYED_FOR", "Club"), out("HOME_VENUE", "Place")],
             "Cầu thủ sinh ra ở {a} từng thi đấu cho câu lạc bộ có sân nhà là sân nào?"),
    Template("f_born_club_won", "football_vn", "Place",
             [inc("BORN_IN", "Player"), out("PLAYED_FOR", "Club"), out("WON", "Competition")],
             "Cầu thủ sinh ra ở {a} từng thi đấu cho câu lạc bộ đã vô địch giải đấu nào?"),
]

# --- VinFast ----------------------------------------------------------------------

VINFAST = [
    # 1 bước
    Template("v_maker", "vinfast", "CarModel", [inc("MANUFACTURES", "Company")],
             "Xe {a} của công ty nào?"),
    Template("v_brand", "vinfast", "CarModel", [out("BELONGS_TO_BRAND", "Brand")],
             "Mẫu xe {a} thuộc thương hiệu nào?"),
    Template("v_based", "vinfast", "CarModel", [out("BASED_ON", "CarModel")],
             "Mẫu xe {a} được phát triển dựa trên mẫu xe nào?"),
    Template("v_made_at", "vinfast", "CarModel", [inc("PRODUCES", "Factory")],
             "Mẫu xe {a} được sản xuất ở nhà máy nào?"),
    Template("v_incorp", "vinfast", "Company", [out("INCORPORATED_IN", "Country")],
             "Công ty {a} được đăng ký ở quốc gia nào?"),
    Template("v_sub_in", "vinfast", "Country", [inc("INCORPORATED_IN", "Company")],
             "Công ty nào của VinFast được đăng ký ở {a}?"),
    Template("v_factory_at", "vinfast", "Factory", [out("LOCATED_IN", "Place")],
             "{a} đặt ở địa điểm nào?"),
    Template("v_factory_in_place", "vinfast", "Place", [inc("LOCATED_IN", "Factory")],
             "Nhà máy nào của VinFast đặt tại {a}?"),
    Template("v_ceo", "vinfast", "Company", [inc("CEO_OF", "Person")],
             "Ai là CEO của {a}?"),
    Template("v_cfo", "vinfast", "Company", [inc("CFO_OF", "Person")],
             "Ai là giám đốc tài chính (CFO) của {a}?"),
    Template("v_founder", "vinfast", "Company", [inc("FOUNDED", "Person")],
             "Ai là người sáng lập {a}?"),
    Template("v_holder_pct", "vinfast", "Company",
             [inc("SHAREHOLDER_OF", None, (("pct", "pct"),))],
             "Ai nắm {pct}% cổ phần của {a}?", {"pct": vi_percent}),
    Template("v_former", "vinfast", "Company",
             [inc("FORMER_BOARD_MEMBER_OF", "Person", (("title", "title"),))],
             "Ai từng giữ chức {title} trong hội đồng quản trị của {a} nhưng nay không còn trong danh sách?",
             {"title": mapped(TITLES)}),
    Template("v_owned_pct", "vinfast", "Company",
             [inc("SUBSIDIARY_OF", "Company", (("direct_ownership_pct", "pct"),))],
             "Công ty nào được {a} sở hữu trực tiếp {pct}% vốn?", {"pct": vi_percent}),
    Template("v_related", "vinfast", "Company",
             [inc("RELATED_PARTY_OF", "Company", (("relationship", "rel"),))],
             "Công ty nào là {rel} của {a}?", {"rel": mapped(RELATIONSHIPS)}),
    Template("v_class", "vinfast", "CarModel", [out("IS_A", "VehicleClass")],
             "Mẫu xe {a} thuộc loại xe nào?"),
    Template("v_class_models", "vinfast", "VehicleClass", [inc("IS_A", "CarModel")],
             "Mẫu xe nào là {a}?"),
    Template("v_sold_region", "vinfast", "Region", [inc("SOLD_IN", "CarModel")],
             "Mẫu xe nào của VinFast được bán ở khu vực {a}?"),
    Template("v_sold_country", "vinfast", "Country", [inc("SOLD_IN", "CarModel")],
             "Mẫu xe nào của VinFast được bán ở {a}?"),
    Template("v_country_place", "vinfast", "Country", [inc("LOCATED_IN", "Place")],
             "Nhà máy VinFast ở {a} nằm ở địa điểm nào?"),
    Template("v_founded_org", "vinfast", "Person", [out("FOUNDED", "Organization")],
             "{a} sáng lập tập đoàn nào?"),
    # 2 bước
    Template("v_made_place", "vinfast", "CarModel",
             [inc("PRODUCES", "Factory"), out("LOCATED_IN", "Place")],
             "Nhà máy sản xuất mẫu xe {a} đặt ở địa điểm nào?"),
    Template("v_based_brand", "vinfast", "CarModel",
             [out("BASED_ON", "CarModel"), out("BELONGS_TO_BRAND", "Brand")],
             "Mẫu xe mà {a} dựa trên thuộc thương hiệu nào?"),
    Template("v_country_factory", "vinfast", "Country",
             [inc("LOCATED_IN", "Place"), inc("LOCATED_IN", "Factory")],
             "Nhà máy nào của VinFast đặt ở {a}?"),
    Template("v_incorp_parent", "vinfast", "Country",
             [inc("INCORPORATED_IN", "Company"), out("SUBSIDIARY_OF", "Company")],
             "Công ty đăng ký ở {a} là công ty con trực tiếp của công ty nào?"),
    Template("v_factory_country", "vinfast", "Factory",
             [out("LOCATED_IN", "Place"), out("LOCATED_IN", "Country")],
             "{a} thuộc quốc gia nào?"),
    Template("v_class_made", "vinfast", "VehicleClass",
             [inc("IS_A", "CarModel"), inc("PRODUCES", "Factory")],
             "Mẫu xe thuộc loại {a} được sản xuất ở nhà máy nào?"),
    Template("v_incorp_place", "vinfast", "Company",
             [out("INCORPORATED_IN", "Country"), inc("LOCATED_IN", "Place")],
             "Nhà máy VinFast ở nước nơi công ty {a} được đăng ký nằm ở địa điểm nào?"),
    # 3 bước
    Template("v_class_place", "vinfast", "VehicleClass",
             [inc("IS_A", "CarModel"), inc("PRODUCES", "Factory"), out("LOCATED_IN", "Place")],
             "Mẫu xe thuộc loại {a} được sản xuất ở nhà máy đặt tại địa điểm nào?"),
    Template("v_incorp_factory", "vinfast", "Company",
             [out("INCORPORATED_IN", "Country"), inc("LOCATED_IN", "Place"), inc("LOCATED_IN", "Factory")],
             "Nhà máy VinFast ở nước nơi công ty {a} được đăng ký tên là gì?"),
    Template("v_made_country", "vinfast", "CarModel",
             [inc("PRODUCES", "Factory"), out("LOCATED_IN", "Place"), out("LOCATED_IN", "Country")],
             "Mẫu xe {a} được sản xuất ở nhà máy thuộc quốc gia nào?"),
    Template("v_based_brand_company", "vinfast", "CarModel",
             [out("BASED_ON", "CarModel"), out("BELONGS_TO_BRAND", "Brand"), inc("HAS_BRAND", "Company")],
             "Thương hiệu của mẫu xe mà {a} dựa trên thuộc công ty nào?"),
    Template("v_country_factory_models", "vinfast", "Country",
             [inc("LOCATED_IN", "Place"), inc("LOCATED_IN", "Factory"), out("PRODUCES", "CarModel")],
             "Nhà máy VinFast ở {a} sản xuất mẫu xe nào?"),
]

TEMPLATES: dict[str, list[Template]] = {"football_vn": FOOTBALL, "vinfast": VINFAST}
BY_ID = {t.id: t for ts in TEMPLATES.values() for t in ts}


# --- dựng 1 test case ---------------------------------------------------------------

def render(kg: KG, tpl: Template, anchor: str, params: dict) -> str | None:
    """Câu hỏi tiếng Việt, hoặc None nếu có tham số không dịch được."""
    shown = {}
    for name, value in params.items():
        text = tpl.fmt.get(name, str)(value)
        if text is None:
            return None
        shown[name] = text
    text = tpl.text
    if normalize(kg.display(anchor)).startswith("cau lac bo"):
        text = re.sub(r"[Cc]âu lạc bộ \{a\}", "{a}", text)  # tên đã có sẵn "Câu lạc bộ"
    return text.format(a=kg.display(anchor), **shown)


def leaks_answer(kg: KG, question: str, answers: list[str]) -> bool:
    """Tên đáp án (mọi cách viết) xuất hiện nguyên từ trong câu hỏi."""
    q = normalize(question)
    for name in kg.variants(answers[0]):
        if len(name) >= 2 and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", q):
            return True
    return False


def build_case(kg: KG, tpl: Template, anchor: str, params: dict) -> dict | None:
    """1 test case (chưa có id) hoặc None nếu không đạt điều kiện nào đó."""
    if kg.nodes[anchor]["label"] != tpl.anchor_label or not kg.name_is_unique(anchor):
        return None
    walk = kg.walk(anchor, tpl.steps, params)
    if walk is None:
        return None
    if any(p["node"] in EXCLUDED_NODES for p in walk.path):
        return None
    last = walk.path[-1]["node"]
    if not kg.name_is_unique(last):  # đáp án trùng tên thực thể khác -> chấm mơ hồ
        return None
    question = render(kg, tpl, anchor, params)
    if question is None or leaks_answer(kg, question, walk.answers):
        return None
    tags = []
    if any(s.dir == "in" for s in tpl.steps):
        tags.append("incoming-edge")
    if any(step.edge.startswith("FORMER_") for step in tpl.steps):
        tags.append("former")
    if any(step.where for step in tpl.steps):
        tags.append("edge-filter")
    if any(kg.degree(p["node"]) >= HUB_DEGREE for p in walk.path):
        tags.append("hub-node")
    case = {
        "question": question,
        "answers": walk.answers,
        "answer_text": kg.display(last),
        "hops": tpl.hops,
        "tags": tags,
        "template": tpl.id,
        "anchors": [anchor],
        "reference_path": walk.path,
    }
    if params:
        case["params"] = params
    return case


def candidates(kg: KG, tpl: Template) -> list[dict]:
    """Mọi test case hợp lệ của 1 mẫu trên graph."""
    found = []
    for node in kg.doc["nodes"]:
        if node["label"] != tpl.anchor_label:
            continue
        for params in kg.param_values(node["id"], tpl.steps[0]):
            case = build_case(kg, tpl, node["id"], params)
            if case:
                found.append(case)
    return found


def vietnam_related(kg: KG, case: dict) -> bool:
    """Câu hỏi có đụng tới thứ gắn với Việt Nam: CLB V.League 1, cầu thủ Việt Nam,
    đội tuyển hay giải đấu của Việt Nam. Dùng để ưu tiên chọn câu quen thuộc với người đọc."""
    for step in case["reference_path"]:
        props = kg.nodes[step["node"]]["properties"]
        label = kg.nodes[step["node"]]["label"]
        if label in ("NationalTeam", "Competition", "Coach"):
            return True
        if label == "Club" and props.get("in_vleague1"):
            return True
        if label == "Player" and props.get("nationality") == "Việt Nam":
            return True
    return False
