"""転移（selective sweep）の発生率と時期を解析する汎用ツール。

単一の「転移率◯%」ではなく累積発生率曲線として報告する。
観測終了tickまでに閾値へ未到達のrunは打ち切りデータとして扱い、
「転移しない」とは断定しない。

例:
    uv run python tools/analyze_transitions.py runs/exp05/control

## 転移の定義

転移の実体は単一系統による選択的一掃として扱い、
**最大系統シェアが閾値を超えた最初のtick** を転移時期とする。

閾値依存の結論にならないよう、複数閾値での感度も併せて出力する。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SWEEP_THRESHOLD = 0.5          # 主判定: 最大系統シェアがこれを超えたら「一掃」
SENSITIVITY = (0.3, 0.5, 0.7)  # 閾値依存でないことの確認用


def load(run_dir: Path) -> dict[str, np.ndarray]:
    with open(run_dir / "stats.csv", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r)
        rows = [[float(v) if v != "" else np.nan for v in row] for row in r if row]
    data = np.array(rows) if rows else np.zeros((0, len(header)))
    return {n: data[:, i] for i, n in enumerate(header)}


def transition_tick(s: dict, threshold: float) -> float | None:
    """最大系統シェアが閾値を初めて超えたtick。超えなければ None。"""
    frac = s.get("top_lineage_frac")
    if frac is None:
        return None
    hit = np.flatnonzero(frac >= threshold)
    return float(s["tick"][hit[0]]) if hit.size else None


def main() -> None:
    ap = argparse.ArgumentParser(description="転移（selective sweep）の発生率と時期を解析")
    ap.add_argument("batch_dir")
    ap.add_argument("--threshold", type=float, default=SWEEP_THRESHOLD)
    args = ap.parse_args()

    batch = Path(args.batch_dir)
    runs = sorted(d for d in batch.iterdir() if (d / "stats.csv").exists())
    if not runs:
        raise SystemExit(f"stats.csv を持つrunが {batch} にありません")

    series = [(d.name.split("seed")[-1], load(d)) for d in runs]
    n = len(series)
    max_tick = max(float(s["tick"][-1]) for _, s in series)

    # --- 転移の検出 ---
    rows = []
    for seed, s in series:
        t = transition_tick(s, args.threshold)
        last = -1
        rows.append({
            "seed": seed, "t": t,
            "pop": float(s["population"][last]),
            "share": float(s["top_lineage_frac"][last]),
            "body": float(s["mean_body_size"][last]),
            "light": float(s["mean_light_absorption"][last]),
            "mut": float(s["mean_mutation_rate"][last]),
            "lineages": float(s["n_lineages"][last]),
        })
    trans = [r for r in rows if r["t"] is not None]
    non = [r for r in rows if r["t"] is None]

    print(f"=== Sweep analysis: {n} seed / {int(max_tick):,} tick / 閾値 share>={args.threshold} ===\n")
    print(f"{int(max_tick):,} tickまでに転移: {len(trans)}/{n} "
          f"({len(trans) / n:.0%})   未転移: {len(non)}/{n}")
    print("※ これは『転移率』ではなく『この時点までの累積発生率』である\n")

    print(f"{'seed':>5} {'転移tick':>9} {'個体数':>8} {'最大シェア':>9} "
          f"{'body_size':>10} {'light_abs':>10} {'mut_rate':>9} {'系統数':>7}")
    for r in sorted(rows, key=lambda x: (x["t"] is None, x["t"] or 0)):
        t = f"{int(r['t']):,}" if r["t"] is not None else "-"
        print(f"{r['seed']:>5} {t:>9} {r['pop']:>8.0f} {r['share']:>9.1%} "
              f"{r['body']:>10.3f} {r['light']:>10.3f} {r['mut']:>9.4f} {r['lineages']:>7.0f}")

    # --- 閾値感度 ---
    print("\n--- 閾値感度 (結論が閾値依存でないかの確認) ---")
    for th in SENSITIVITY:
        c = sum(1 for _, s in series if transition_tick(s, th) is not None)
        print(f"  share>={th}: {c}/{n} ({c / n:.0%})")

    # --- 転移群 vs 未転移群 ---
    if trans and non:
        print("\n--- 転移群 vs 未転移群 (最終時点の中央値) ---")
        print(f"{'指標':<12} {'転移群':>12} {'未転移群':>12}")
        for k, label in [("pop", "個体数"), ("body", "body_size"),
                         ("light", "light_abs"), ("mut", "mutation_rate"),
                         ("lineages", "系統数")]:
            a = np.median([r[k] for r in trans])
            b = np.median([r[k] for r in non])
            print(f"{label:<12} {a:>12.3f} {b:>12.3f}")

    # --- 未転移seedは「転移しない」のか「まだ」なのか ---
    if non:
        print("\n--- 未転移seedの終盤の傾向 (最後の20%区間の変化) ---")
        print("  light_absorptionが上昇中なら『まだ転移していないだけ』の可能性")
        print(f"{'seed':>5} {'light終値':>10} {'light変化':>10} {'share終値':>10} {'share変化':>10}")
        for r in non:
            s = dict(series)[r["seed"]]
            i0 = int(len(s["tick"]) * 0.8)
            dl = float(s["mean_light_absorption"][-1] - s["mean_light_absorption"][i0])
            ds = float(s["top_lineage_frac"][-1] - s["top_lineage_frac"][i0])
            print(f"{r['seed']:>5} {r['light']:>10.3f} {dl:>+10.3f} "
                  f"{r['share']:>10.1%} {ds:>+10.1%}")

    # --- 図 ---
    out = batch / "aggregate"
    out.mkdir(exist_ok=True)
    grid = np.linspace(0, max_tick, 400)
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    ax = axes[0]
    for th in SENSITIVITY:
        ts = [transition_tick(s, th) for _, s in series]
        cum = [sum(1 for t in ts if t is not None and t <= g) / n for g in grid]
        ax.step(grid, cum, where="post", lw=1.8 if th == args.threshold else 1.0,
                alpha=1.0 if th == args.threshold else 0.5,
                label=f"share>={th}")
    ax.set_xlabel("tick")
    ax.set_ylabel("cumulative fraction transitioned")
    ax.set_ylim(0, 1)
    ax.set_title(f"Cumulative incidence (n={n}, right-censored)")
    ax.legend(fontsize=8)

    ax = axes[1]
    for seed, s in series:
        t = transition_tick(s, args.threshold)
        ax.plot(s["tick"], s["top_lineage_frac"],
                color="tab:red" if t is not None else "tab:gray",
                lw=1.0, alpha=0.8)
    ax.axhline(args.threshold, color="k", ls="--", lw=0.8)
    ax.set_xlabel("tick")
    ax.set_ylabel("top lineage share")
    ax.set_title("Selective sweep (red = transitioned)")

    ax = axes[2]
    for seed, s in series:
        t = transition_tick(s, args.threshold)
        ax.plot(s["tick"], s["mean_light_absorption"],
                color="tab:red" if t is not None else "tab:gray",
                lw=1.0, alpha=0.8)
    ax.set_xlabel("tick")
    ax.set_ylabel("mean light_absorption")
    ax.set_title("Light absorption (gray = not yet transitioned)")

    fig.suptitle(f"Sweep incidence across seeds: {batch.name}")
    fig.tight_layout()
    fig.savefig(out / "transitions.png", dpi=110)
    plt.close(fig)
    print(f"\n図 -> {out / 'transitions.png'}")


if __name__ == "__main__":
    main()
