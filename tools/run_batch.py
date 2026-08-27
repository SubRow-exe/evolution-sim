"""複数Seed一括実験 (方針版 §52 / ロードマップ Stage 0 基準実験)。

同一条件でSeedだけを変えて多数回実行し、「この現象は必然か、偶然そうなっただけか」
を区別できるようにする。各runは独立プロセスで実行され、内部の決定性は保たれる。

    uv run python tools/run_batch.py --seeds 1-5 --ticks 30000
    uv run python tools/run_batch.py --seeds 1,2,3 --ticks 50000 --workers 3
    uv run python tools/run_batch.py --aggregate runs/batch_20260827_120000
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evosim.genome import GENE_NAMES

# 基準実験で追跡する主要指標 (ロードマップ Stage 0)
KEY_GENES = ["body_size", "light_absorption", "reproduction_investment", "mutation_rate"]


def parse_seeds(spec: str) -> list[int]:
    """"1-5" や "1,3,7" や "1-3,10" を seed のリストに展開する。"""
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def run_one(args: tuple[int, int, str, str | None]) -> tuple[int, bool, str]:
    """1 seed をサブプロセスで実行する。戻り値: (seed, 成功, メッセージ)。"""
    seed, ticks, out_dir, config = args
    cmd = [sys.executable, str(ROOT / "main.py"), "--headless",
           "--ticks", str(ticks), "--seed", str(seed), "--out", out_dir]
    if config:
        cmd += ["--config", config]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    el = time.perf_counter() - t0
    if proc.returncode != 0:
        return seed, False, (proc.stderr or "")[-400:]
    tail = [ln for ln in proc.stdout.splitlines() if ln.startswith("done:")]
    return seed, True, f"{tail[0] if tail else 'finished'}  ({el:.0f}s)"


def _load_stats(path: Path) -> dict[str, np.ndarray]:
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [[float(v) if v != "" else np.nan for v in r] for r in reader if r]
    data = np.array(rows) if rows else np.zeros((0, len(header)))
    return {name: data[:, i] for i, name in enumerate(header)}


def aggregate(batch_dir: Path) -> Path:
    """全seedのstats.csvを重ね描きし、seed間のばらつきを可視化する。"""
    runs = sorted(d for d in batch_dir.iterdir() if (d / "stats.csv").exists())
    if not runs:
        raise SystemExit(f"stats.csv を持つrunが {batch_dir} にありません")

    series = []
    for d in runs:
        s = _load_stats(d / "stats.csv")
        seed = d.name.split("seed")[-1]
        series.append((seed, s))

    out = batch_dir / "aggregate"
    out.mkdir(exist_ok=True)

    panels = ["population", "n_lineages"] + [f"mean_{g}" for g in KEY_GENES]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    for ax, key in zip(axes.flat, panels):
        for seed, s in series:
            if key in s:
                ax.plot(s["tick"], s[key], lw=1.0, alpha=0.8, label=f"seed {seed}")
        ax.set_title(key, fontsize=10)
        ax.set_xlabel("tick")
    axes.flat[0].legend(fontsize=7, ncol=2)
    # 日本語グリフを持たない環境があるため、図中の文字は英語に統一する
    fig.suptitle(f"Baseline across {len(series)} seeds "
                 "(converging lines = deterministic trend, spread = stochastic)")
    fig.tight_layout()
    fig.savefig(out / "across_seeds.png", dpi=110)
    plt.close(fig)

    # 最終時点の要約表 (seed間の中央値・範囲)
    summary_path = out / "summary.csv"
    cols = ["population", "max_generation", "n_lineages", "top_lineage_frac",
            *[f"mean_{g}" for g in GENE_NAMES]]
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "final_tick", *cols])
        finals: dict[str, list[float]] = {c: [] for c in cols}
        for seed, s in series:
            row = [seed, int(s["tick"][-1])]
            for c in cols:
                v = float(s[c][-1]) if c in s else float("nan")
                finals[c].append(v)
                row.append(round(v, 6))
            w.writerow(row)
        w.writerow([])
        for label, fn in (("median", np.nanmedian), ("min", np.nanmin), ("max", np.nanmax)):
            w.writerow([label, "", *[round(float(fn(finals[c])), 6) for c in cols]])

    print(f"\n--- 最終時点の主要指標 (seed {len(series)}件) ---")
    for c in ["population", "n_lineages", *[f"mean_{g}" for g in KEY_GENES]]:
        vals = [float(s[c][-1]) for _, s in series if c in s]
        if vals:
            print(f"  {c:32s} 中央値 {np.median(vals):>10.3f}   "
                  f"範囲 {min(vals):.3f} 〜 {max(vals):.3f}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="複数Seed一括実験")
    ap.add_argument("--seeds", default="1-5", help='例: "1-5" / "1,3,7" / "1-3,10"')
    ap.add_argument("--ticks", type=int, default=30000)
    ap.add_argument("--workers", type=int, default=1, help="並列実行数 (run間のみ)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None, help="バッチ出力先 (省略時 runs/batch_<日時>)")
    ap.add_argument("--aggregate", default=None, help="既存バッチの集計のみ実行")
    args = ap.parse_args()

    if args.aggregate:
        print(f"aggregate -> {aggregate(Path(args.aggregate))}")
        return

    seeds = parse_seeds(args.seeds)
    batch = Path(args.out) if args.out else \
        ROOT / "runs" / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    batch.mkdir(parents=True, exist_ok=True)
    print(f"batch: {batch}\nseeds: {seeds}  ticks: {args.ticks}  workers: {args.workers}\n")

    jobs = [(s, args.ticks, str(batch), args.config) for s in seeds]
    t0 = time.perf_counter()
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(run_one, jobs))
    else:
        results = [run_one(j) for j in jobs]

    for seed, ok, msg in results:
        print(f"  seed {seed:>4}: {'OK ' if ok else 'FAIL'} {msg}")
    print(f"\n全 {len(seeds)} run 完了 ({time.perf_counter() - t0:.0f}s)")
    print(f"aggregate -> {aggregate(batch)}")


if __name__ == "__main__":
    main()
