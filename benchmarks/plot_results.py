"""Vẽ biểu đồ benchmark bằng TikZ (pgfplots) từ kết quả chạy hàng loạt.

Chạy:  python3 benchmarks/plot_results.py [--runs outputs/runs.csv] [--out docs/images]

Đầu vào là `runs.csv` do `backend/run_cases.py` ghi ra (mỗi câu lấy lượt chạy mới nhất).
Script sinh 2 file .tex (standalone), biên dịch bằng `tectonic` rồi đổi sang PNG bằng
`pdftoppm`; file .tex được giữ cạnh PNG để sửa/biên dịch lại.

  benchmark-outcomes.png : mỗi câu hỏi là một vị trí trên đường chéo (câu thứ i ở điểm (i, i)). Mỗi
      model có một chấm cho mỗi câu (Jev xanh, Gemma đỏ, gpt-oss vàng), nối liền thành một đường:
      ĐÚNG -> chấm nằm TRÊN đường chéo; SAI (kết luận sai node) -> lệch xuống dưới đường;
      KHÔNG TÌM THẤY (không tìm ra / quá giờ / dừng) -> lệch lên phía trên đường.
      Câu bị lỗi không có chấm.
  benchmark-latency.png  : biểu đồ cột, mỗi model 3 cột: độ chính xác, thời gian trung bình tới
      kết quả, chi phí trung bình mỗi câu. Mỗi chỉ số quy về % so với model cao nhất (để vẽ
      chung một trục); giá trị thật ghi trên đầu cột.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import statistics
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

MODELS = [("jev", "Jev"), ("ollama", "Gemma 4 12B"), ("nvidia", "gpt-oss-20b")]
COLORS = {"jev": "jevblue", "ollama": "gemmared", "nvidia": "gptyellow"}
FOOTBALL_CASES = 30  # câu VinFast được xếp sau 30 câu bóng đá trên trục x
# 3 chấm của cùng một câu được tách dọc theo đường chéo (vẫn nằm đúng trên đường) để không đè nhau
DIAG_OFFSET = {"jev": -0.3, "ollama": 0.0, "nvidia": 0.3}
MISS = 7  # độ lệch khỏi đường chéo (trục chạy 0–60): sai -> xuống dưới, không tìm thấy -> lên trên

PREAMBLE = r"""\documentclass[border=8pt]{standalone}
\usepackage{fontspec}
\setmainfont{Arial}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18, every axis/.append style={/pgf/number format/assume math mode=true,
  tick label style={font=\small}, /pgf/number format/use comma, /pgf/number format/1000 sep={.}}}
\definecolor{jevblue}{HTML}{2F7FBF}
\definecolor{gemmared}{HTML}{D1495B}
\definecolor{gptyellow}{HTML}{EDB92E}
\definecolor{lineGray}{HTML}{6B6B66}
\definecolor{timeDark}{HTML}{1F3A5F}
\definecolor{costOrange}{HTML}{D9692B}
\definecolor{accTeal}{HTML}{2E9E8F}
\begin{document}
"""


# --------------------------------------------------------------------------- #
# Đọc dữ liệu
# --------------------------------------------------------------------------- #

def load_runs(runs_csv: pathlib.Path) -> dict[str, dict[str, dict]]:
    """case_id -> model -> {status, correct, elapsed_s, cost}; mỗi câu lấy lượt mới nhất."""
    by_run: dict[str, dict] = {}
    for row in csv.DictReader(runs_csv.open(encoding="utf-8")):
        if not row.get("case_id"):
            continue
        run = by_run.setdefault(row["run_id"], {"started_at": row["started_at"], "case_id": row["case_id"],
                                                "models": {}})
        run["models"][row["model"]] = {
            "status": row["status"],
            "correct": {"true": True, "false": False}.get(row["correct"]),
            "elapsed_s": float(row["elapsed_ms"] or 0) / 1000,
            "cost": float(row["cost"] or 0),
        }
    latest: dict[str, dict] = {}
    for run in sorted(by_run.values(), key=lambda r: r["started_at"]):
        latest[run["case_id"]] = run["models"]
    return latest


def case_x(case_id: str) -> int:
    """football-007 -> 7; vinfast-007 -> 37 (vị trí trên trục x)."""
    domain, number = case_id.rsplit("-", 1)
    return int(number) + (FOOTBALL_CASES if domain == "vinfast" else 0)


def dots(cases: dict[str, dict[str, dict]], model: str) -> list[tuple[float, float]]:
    """Chấm của model: câu i đúng -> (i, i) trên đường chéo; kết luận sai node -> lệch xuống MISS đơn
    vị; không tìm thấy (không tìm ra / quá giờ / dừng) -> lệch lên MISS đơn vị; câu bị lỗi không có
    chấm. Cộng DIAG_OFFSET dọc đường chéo để 3 model không đè nhau."""
    shift = DIAG_OFFSET[model]
    points = []
    for case_id in sorted(cases, key=case_x):
        result = cases[case_id].get(model)
        if result is None or result["status"] == "error":
            continue
        x = case_x(case_id) + shift
        if result["status"] != "found":
            points.append((x, x + MISS))          # không tìm thấy -> phía trên đường
        else:
            points.append((x, x if result["correct"] else x - MISS))  # đúng -> trên đường; sai -> dưới
    return points


def averages(cases: dict[str, dict[str, dict]], model: str) -> dict:
    """Thời gian TB của các lượt model đưa ra kết luận (đúng hoặc sai) và chi phí TB mỗi câu."""
    results = [c[model] for c in cases.values() if model in c]
    answered = [r["elapsed_s"] for r in results if r["status"] == "found"]
    return {
        "n_answered": len(answered),
        "mean_time_s": statistics.fmean(answered) if answered else None,
        "mean_cost": statistics.fmean(r["cost"] for r in results) if results else 0.0,
        "correct": sum(1 for r in results if r["status"] == "found" and r["correct"]),
        "total": len(results),
        "errors": sum(1 for r in results if r["status"] == "error"),
    }


def vi(number: float, digits: int) -> str:
    """Số kiểu Việt Nam: dấu phẩy thập phân."""
    return f"{number:.{digits}f}".replace(".", ",")


# --------------------------------------------------------------------------- #
# Sinh TikZ
# --------------------------------------------------------------------------- #

def outcomes_tex(cases: dict[str, dict[str, dict]]) -> str:
    stats = {key: averages(cases, key) for key, _ in MODELS}
    total = len(cases)
    plots = [f"\\addplot[color=lineGray, line width=2pt, forget plot] coordinates {{(0,0) ({total},{total})}};"]
    for key, name in MODELS:
        coords = " ".join(f"({x:.2f},{y:.2f})" for x, y in dots(cases, key))
        s_ = stats[key]
        plots.append(f"\\addplot[color={COLORS[key]}, mark=*, mark size=2.3pt, line width=0.9pt, opacity=0.9] "
                     f"coordinates {{{coords}}};\n\\addlegendentry{{{name} ({s_['correct']}/{s_['total']} đúng)}}")
    return PREAMBLE + r"""\begin{tikzpicture}
\begin{axis}[
  title={Kết quả trên bộ ground truth},
  width=22cm, height=16cm, xmin=-1, xmax=@XMAX@, ymin=@YMIN@, ymax=@YMAX@,
  title style={font=\Large\bfseries}, tick label style={font=\large}, label style={font=\large},
  xtick={1,20,40,60}, xlabel={Thứ tự câu hỏi (1–30 bóng đá, 31–60 VinFast)},
  hide y axis, axis x line*=bottom, xmajorgrids, grid style={gray!18}, clip=true,
  legend columns=-1,
  legend style={at={(0.5,-0.12)}, anchor=north, draw=none, font=\large, /tikz/every even column/.append style={column sep=16pt}},
]
@PLOTS@
\end{axis}
\end{tikzpicture}
\end{document}
""".replace("@XMAX@", str(total + 1)).replace("@YMIN@", str(-MISS - 3)).replace("@YMAX@", str(total + MISS + 3)) \
   .replace("@PLOTS@", "\n".join(plots))


def tradeoff_rows(cases: dict[str, dict[str, dict]]) -> list[dict]:
    """Mỗi chỉ số: giá trị thật + chữ hiển thị của từng model + giá trị quy về [0, 1] theo max."""
    stats = {key: averages(cases, key) for key, _ in MODELS}
    metrics = [
        ("Độ chính xác\\\\(\\% số câu đúng)",
         {k: s["correct"] / s["total"] for k, s in stats.items() if s["total"]},
         lambda v: f"{vi(100 * v, 0)}\\%"),
        ("Thời gian trung bình\\\\tới kết quả",
         {k: s["mean_time_s"] for k, s in stats.items() if s["mean_time_s"] is not None},
         lambda v: f"{vi(v, 1)}\\,s"),
        ("Chi phí trung bình\\\\mỗi câu",
         {k: s["mean_cost"] for k, s in stats.items()},
         lambda v: "\\$0" if not v else f"\\${vi(v, 4)}"),
    ]
    rows = []
    for label, values, fmt in metrics:
        top = max(values.values(), default=0) or 1
        rows.append({"label": label, "text": {k: fmt(v) for k, v in values.items()},
                     "norm": {k: v / top for k, v in values.items()}})
    return rows


def latency_tex(cases: dict[str, dict[str, dict]]) -> str:
    """Cột nhóm: mỗi model 3 cột (độ chính xác, thời gian, chi phí), quy về % so với model cao nhất."""
    rows = tradeoff_rows(cases)
    colors = ["accTeal", "timeDark", "costOrange"]
    names = ["Độ chính xác (\\% số câu đúng)", "Thời gian trung bình tới kết quả", "Chi phí trung bình mỗi câu"]
    symbolic = ",".join(name for _, name in MODELS)
    plots = []
    for row, color, legend in zip(rows, colors, names):
        coords = " ".join(f"({name},{row['norm'][key]:.4f}) [{row['text'][key]}]"
                          for key, name in MODELS if key in row["norm"])
        plots.append(f"\\addplot+[ybar, fill={color}, draw=white] coordinates {{{coords}}};\n\\addlegendentry{{{legend}}}")
    return PREAMBLE + r"""\begin{tikzpicture}
\begin{axis}[
  title={Đánh đổi giữa độ chính xác, thời gian và chi phí}, title style={font=\bfseries},
  ybar, bar width=17pt, width=16cm, height=9.5cm, symbolic x coords={@SYMBOLIC@}, xtick=data,
  xticklabel style={font=\small}, enlarge x limits=0.22,
  ymin=0, ymax=1.18, ytick={0,0.25,0.5,0.75,1}, yticklabels={0,25\%,50\%,75\%,100\%},
  ylabel={Mức so với model cao nhất ở từng chỉ số},
  axis lines*=left, ymajorgrids, grid style={gray!25}, clip=false,
  nodes near coords={\pgfplotspointmeta}, point meta=explicit symbolic,
  every node near coord/.append style={font=\scriptsize\bfseries, text=black, rotate=0, anchor=south, yshift=1pt},
  legend columns=-1, area legend,
  legend style={at={(0.5,-0.13)}, anchor=north, draw=none, font=\small, /tikz/every even column/.append style={column sep=10pt}},
]
@PLOTS@
\end{axis}
\end{tikzpicture}
\end{document}
""".replace("@SYMBOLIC@", symbolic).replace("@PLOTS@", "\n".join(plots))


def build(tex: str, name: str, out_dir: pathlib.Path) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.tex").write_text(tex, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / f"{name}.tex"
        src.write_text(tex, encoding="utf-8")
        subprocess.run(["tectonic", "--chatter", "minimal", "--outdir", tmp, str(src)], check=True)
        subprocess.run(["pdftoppm", "-png", "-r", "200", "-singlefile", str(pathlib.Path(tmp) / f"{name}.pdf"),
                        str(pathlib.Path(tmp) / name)], check=True)
        shutil.copy(pathlib.Path(tmp) / f"{name}.png", out_dir / f"{name}.png")
    return out_dir / f"{name}.png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=pathlib.Path, default=ROOT / "outputs" / "runs.csv")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "docs" / "images")
    args = parser.parse_args()
    for tool in ("tectonic", "pdftoppm"):
        if not shutil.which(tool):
            raise SystemExit(f"Thiếu `{tool}` — cài bằng `brew install tectonic poppler`")
    cases = load_runs(args.runs)
    if not cases:
        raise SystemExit(f"{args.runs} chưa có lượt chạy ground truth nào")
    for name, tex in (("benchmark-outcomes", outcomes_tex(cases)), ("benchmark-latency", latency_tex(cases))):
        png = build(tex, name, args.out)
        print("ghi", png.relative_to(ROOT) if png.is_relative_to(ROOT) else png)


if __name__ == "__main__":
    main()
