"""Làm 3 GIF minh hoạ (1 GIF/model) từ kết quả chạy hàng loạt, cùng một câu hỏi.

Chạy (cần frontend + backend đang chạy, Playwright cài ở thư mục riêng, ffmpeg):
    python3 benchmarks/make_gifs.py --playwright <thư mục có node_modules/playwright>
    python3 benchmarks/make_gifs.py --list          # chỉ xem các câu ứng viên

Chọn câu: mọi model đều có kết quả, và **số node ít nhất trong 3 model là lớn nhất** (để
cả 3 GIF đều đi qua nhiều node, thể hiện quy mô graph); hoà thì ưu tiên câu nhiều model tìm
đúng hơn, rồi tổng số node. Lưu ý: lượt đi qua nhiều node thường là lượt đi lạc nên câu được
chọn có thể không model nào đúng — vì vậy GIF ẩn các nhãn kết quả (tìm ra/không tìm ra/lỗi,
đúng/sai), kết quả thật của từng model được mô tả bằng chữ dưới hình. Ép dùng câu khác
bằng --case. GIF ghi vào docs/images/trace-<model>.gif.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS = ("jev", "ollama", "nvidia")


def candidates(outputs: pathlib.Path) -> list[dict]:
    runs: dict[str, dict] = {}
    for row in csv.DictReader((outputs / "runs.csv").open(encoding="utf-8")):
        if not row.get("case_id"):
            continue
        run = runs.setdefault(row["run_id"], {"run_id": row["run_id"], "case_id": row["case_id"],
                                              "question": row["question"], "started_at": row["started_at"],
                                              "models": {}})
        run["models"][row["model"]] = {"status": row["status"], "correct": row["correct"] == "true"}
    latest: dict[str, dict] = {}  # mỗi câu lấy lượt mới nhất
    for run in sorted(runs.values(), key=lambda r: r["started_at"]):
        latest[run["case_id"]] = run

    out = []
    for run in latest.values():
        trace = outputs / f"run_{run['run_id']}_trace.csv"
        if not trace.exists() or set(MODELS) - set(run["models"]):
            continue
        visits = dict.fromkeys(MODELS, 0)
        for step in csv.DictReader(trace.open(encoding="utf-8")):
            if step["phase"] == "visit" and step["node_id"] and step["model"] in visits:
                visits[step["model"]] += 1
        correct = sum(run["models"][m]["correct"] for m in MODELS)
        out.append({**run, "visits": visits, "correct": correct,
                    "score": (min(visits.values()), correct, sum(visits.values()))})
    return sorted(out, key=lambda r: r["score"], reverse=True)


def to_gif(frames: list[dict], out: pathlib.Path, width: int) -> None:
    """Ghép PNG theo thời lượng từng khung (concat demuxer) + bảng màu riêng cho GIF đẹp."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for fr in frames:
            f.write(f"file '{fr['file']}'\nduration {fr['hold'] / 1000:.2f}\n")
        f.write(f"file '{frames[-1]['file']}'\n")  # concat cần lặp khung cuối để giữ duration
        listing = f.name
    vf = (f"scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];"
          f"[b][p]paletteuse=dither=bayer:bayer_scale=4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-vf", vf, "-fps_mode", "vfr", "-loop", "0", str(out)], check=True)
    os.unlink(listing)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outputs", type=pathlib.Path, default=ROOT / "outputs")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "docs" / "images")
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--playwright", type=pathlib.Path, help="thư mục chứa node_modules/playwright")
    parser.add_argument("--case", help="ép dùng câu này thay vì tự chọn")
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    cands = candidates(args.outputs)
    if not cands:
        raise SystemExit("Chưa có lượt chạy ground truth nào đủ 3 model trong outputs/")
    for c in cands[:8]:
        print(f"{c['case_id']:13} node ít nhất={c['score'][0]:>2}  đúng={c['correct']}/3  "
              f"node={c['visits']}  {c['question']}")
    if args.list:
        return
    chosen = next((c for c in cands if c["case_id"] == args.case), None) if args.case else cands[0]
    if chosen is None:
        raise SystemExit(f"Không có câu {args.case}")
    print(f"\n-> chọn {chosen['case_id']}: {chosen['question']}")

    if not args.playwright:
        raise SystemExit("Thiếu --playwright <thư mục có node_modules/playwright>")
    for tool in ("node", "ffmpeg"):
        if not shutil.which(tool):
            raise SystemExit(f"Thiếu `{tool}`")
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "NODE_PATH": str(args.playwright / "node_modules")}
        subprocess.run(["node", str(ROOT / "benchmarks" / "record_gifs.cjs"), args.url, chosen["question"], tmp],
                       check=True, env=env)
        manifest = json.loads((pathlib.Path(tmp) / "frames.json").read_text(encoding="utf-8"))
        args.out.mkdir(parents=True, exist_ok=True)
        for key in MODELS:
            gif = args.out / f"trace-{key}.gif"
            to_gif(manifest[key]["frames"], gif, args.width)
            shown = gif.relative_to(ROOT) if gif.is_relative_to(ROOT) else gif
            print(f"ghi {shown} ({gif.stat().st_size / 1e6:.1f} MB, "
                  f"{manifest[key]['nodes']} node)")
    (args.out / "trace-case.json").write_text(json.dumps(
        {k: chosen[k] for k in ("case_id", "question", "run_id", "visits", "correct")}, ensure_ascii=False,
        indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
