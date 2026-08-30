"""空間スナップショットのPNG/GIF描画 (V1.2.1)。

docs/V1.2_V1.2.1_詳細実装仕様.md §7。

環境をヒートマップ背景にし、その上へ個体を系統ごとの色で重ねる。
「どの系統がどの光環境に、どう分布しているか」を目で見るための後処理ツール。

    uv run python tools/render_spatial.py runs/<run> --background light --gif --fps 6
    uv run python tools/render_spatial.py runs/<run> --background chemical

背景: light | chemical | nutrient

後処理なので、失敗しても科学run自体は無効にならない。
系統の色は lineage_id から決定的に決める (Python の hash() は
実行ごとに変わるため使わない)。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BACKGROUNDS = ("light", "chemical", "nutrient")
CMAPS = {"light": "inferno", "chemical": "magma", "nutrient": "YlGn"}


def lineage_color(lineage_id: int) -> tuple[float, float, float]:
    """lineage_id から決定的に色を作る。

    黄金比による色相回転で、近い id でも色が離れるようにする。
    Python の hash() は実行ごとに変わるため使わない (再現性のため)。
    """
    import colorsys
    h = (lineage_id * 0.6180339887498949) % 1.0
    s = 0.60 + 0.30 * ((lineage_id * 7) % 5) / 4.0
    v = 0.75 + 0.25 * ((lineage_id * 13) % 3) / 2.0
    return colorsys.hsv_to_rgb(h, s, v)


def load_snapshots(run: Path) -> list[tuple[int, list[dict]]]:
    out = []
    for p in sorted((run / "snapshots").glob("snap_*.csv")):
        tick = int(p.stem.split("_")[1])
        with open(p, encoding="utf-8") as f:
            out.append((tick, list(csv.DictReader(f))))
    return out


def load_background(run: Path, kind: str, tick: int) -> np.ndarray | None:
    env = run / "environment"
    if kind == "light":
        f = env / "static.npz"
        if not f.exists():
            return None
        with np.load(f) as d:
            return d["light"]
    f = env / f"env_{tick:08d}.npz"
    if not f.exists():
        return None
    key = "chemical" if kind == "chemical" else "nutrients"
    with np.load(f) as d:
        return d[key] if key in d else None


def render_frame(run: Path, tick: int, rows: list[dict], bg_kind: str,
                 out_path: Path, bg_vmax: float | None,
                 world_w: float, world_h: float, title_extra: str = "") -> None:
    bg = load_background(run, bg_kind, tick)
    fig, ax = plt.subplots(figsize=(7.2, 7.2))

    if bg is not None:
        # 配列は [ix, iy]。画像は行=y なので転置して origin='upper' で北を上にする
        ax.imshow(bg.T, origin="upper", cmap=CMAPS[bg_kind],
                  extent=(0, world_w, world_h, 0),
                  vmin=0.0, vmax=bg_vmax, interpolation="nearest")
    else:
        ax.set_facecolor("black")

    if rows:
        xs = np.array([float(r["x"]) for r in rows])
        ys = np.array([float(r["y"]) for r in rows])
        matter = np.array([float(r["matter"]) for r in rows])
        colors = [lineage_color(int(r["lineage_id"])) for r in rows]
        sizes = 6.0 + 26.0 * np.clip(matter / 2.0, 0.0, 1.0)
        ax.scatter(xs, ys, s=sizes, c=colors, linewidths=0.3,
                   edgecolors="black", alpha=0.85)

    ax.set_xlim(0, world_w)
    ax.set_ylim(world_h, 0)  # 北 (y=0) を上に
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"tick {tick:,}   pop {len(rows):,}   bg={bg_kind}{title_extra}",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="空間スナップショットの描画 (V1.2.1)")
    ap.add_argument("run_dir")
    ap.add_argument("--background", choices=BACKGROUNDS, default="light")
    ap.add_argument("--gif", action="store_true", help="PNG群からGIFも作る")
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run = Path(args.run_dir)
    if not (run / "snapshots").is_dir():
        raise SystemExit(f"{run}/snapshots がありません")

    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    world_w = cfg.get("world_width", 800.0)
    world_h = cfg.get("world_height", 800.0)
    pattern = cfg.get("light_pattern", "?")

    snaps = load_snapshots(run)
    if not snaps:
        raise SystemExit("スナップショットがありません")

    out = Path(args.out) if args.out else run / "spatial" / args.background
    out.mkdir(parents=True, exist_ok=True)

    # 全フレームで色スケールを揃える (フレーム間で明るさが変わると誤読するため)
    vmax = 0.0
    for tick, _ in snaps:
        bg = load_background(run, args.background, tick)
        if bg is not None:
            vmax = max(vmax, float(bg.max()))
    vmax = vmax or None

    paths = []
    for tick, rows in snaps:
        p = out / f"frame_{tick:08d}.png"
        render_frame(run, tick, rows, args.background, p, vmax,
                     world_w, world_h, title_extra=f"   {pattern}")
        paths.append(p)
    print(f"PNG {len(paths)} 枚 -> {out}")

    if args.gif:
        try:
            from PIL import Image
        except ImportError:
            print("GIF生成にはPillowが必要 (matplotlib同梱のはず)。PNGのみ出力した。")
            return
        frames = [Image.open(p).convert("P", palette=Image.ADAPTIVE) for p in paths]
        gif = out / f"{args.background}.gif"
        frames[0].save(gif, save_all=True, append_images=frames[1:],
                       duration=int(1000 / max(args.fps, 0.1)), loop=0)
        print(f"GIF -> {gif}")


if __name__ == "__main__":
    main()
