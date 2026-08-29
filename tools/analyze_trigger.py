"""転移トリガー解析 (Issue #18 / docs/V1.1_転移トリガー解析項目.md)。

## 問い

同じように小型・高光利用化する複数系統のうち、なぜ一系統だけが急速に
席巻するのか。仮説は「繁殖上の小さな優位 → 出生数増 → 変異試行回数増 →
さらに有利な変異 → 正のフィードバック」。

検証したい因果順序:

    形質変化 → 1個体あたり出生率上昇 → 系統人口増加 → sweep

人口が増えた後で形質が変わっているだけなら仮説は弱い。

## なぜ events.csv を使うのか

`lineages.csv` は上位8系統しか記録しないため、支配系統が台頭する前の
履歴が欠ける (Exp03では13転移seed中4seedで転移5,000tick前の記録が無い)。
これは「早くから大きかった系統しか見えない」という**選択バイアス**であり、
まさに検証したい仮説を歪める方向に働く。

events.csv は全個体の出生・死亡を lineage_id 付きで持つため、
**すべての系統の完全な履歴を tick 0 から復元できる**。

    uv run python tools/analyze_trigger.py runs/exp03_20seeds_40k/<run>
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SWEEP_THRESHOLD = 0.5
BIN = 200  # 集計のtick幅


def transition_info(run: Path, threshold: float):
    """転移tickと支配系統id。stats.csv から求める。"""
    with open(run / "stats.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if float(r["top_lineage_frac"]) >= threshold:
                return int(r["tick"]), r["top_lineage_id"]
    return None, None


def lineage_series(run: Path, lineage_ids: set, max_tick: int):
    """events.csv から指定系統の人口・出生数の時系列を復元する。"""
    births = {l: defaultdict(int) for l in lineage_ids}
    deaths = {l: defaultdict(int) for l in lineage_ids}
    all_b, all_d = defaultdict(int), defaultdict(int)
    with open(run / "events.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ev = r["event"]
            if ev not in ("birth", "death"):
                continue
            t = int(r["tick"])
            if t > max_tick:
                break
            b = t // BIN
            if ev == "birth":
                all_b[b] += 1
            else:
                all_d[b] += 1
            lid = r["lineage_id"]
            if lid in lineage_ids:
                (births if ev == "birth" else deaths)[lid][b] += 1

    nbin = max_tick // BIN + 1
    ticks = np.arange(nbin) * BIN
    total = np.cumsum([all_b[i] - all_d[i] for i in range(nbin)])
    out = {}
    for l in lineage_ids:
        bs = np.array([births[l][i] for i in range(nbin)], dtype=float)
        ds = np.array([deaths[l][i] for i in range(nbin)], dtype=float)
        pop = np.cumsum(bs - ds)
        with np.errstate(divide="ignore", invalid="ignore"):
            per_capita = np.where(pop > 0, bs / BIN / np.maximum(pop, 1e-9), np.nan)
            share = np.where(total > 0, pop / np.maximum(total, 1e-9), np.nan)
        out[l] = {"tick": ticks, "pop": pop, "births": bs,
                  "per_capita": per_capita, "share": share}
    return out, ticks, total


def lineage_traits(run: Path, lineage_ids: set) -> dict:
    """スナップショットから系統ごとの平均形質を復元する。"""
    out = {l: defaultdict(dict) for l in lineage_ids}
    for snap in sorted((run / "snapshots").glob("snap_*.csv")):
        t = int(snap.stem.split("_")[1])
        acc = {l: [] for l in lineage_ids}
        with open(snap, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["lineage_id"] in lineage_ids:
                    acc[r["lineage_id"]].append(r)
        for l, rows in acc.items():
            if rows:
                for g in ("body_size", "light_absorption",
                          "reproduction_investment", "mutation_rate"):
                    out[l][g][t] = float(np.mean([float(r[g]) for r in rows]))
    return out


def rates(run: Path, tt: int, top_id: str, lo: int, hi: int):
    """窓 [tt+lo, tt+hi) の 支配系統/集団全体 の出生率・死亡率比と純増を返す。"""
    series, ticks, total = lineage_series(run, {top_id}, tt + max(hi, 0) + BIN)
    d = series[top_id]
    tb = np.zeros_like(total, dtype=float)
    td = np.zeros_like(total, dtype=float)
    with open(run / "events.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ev = r["event"]
            if ev not in ("birth", "death"):
                continue
            t = int(r["tick"])
            if t > tt + max(hi, 0):
                break
            (tb if ev == "birth" else td)[t // BIN] += 1

    def idx(t):
        return int(np.clip(t // BIN, 0, len(ticks) - 1))

    i0, i1 = idx(tt + lo), idx(tt + hi)
    if i1 <= i0:
        return None
    pt_top = float(d["pop"][i0:i1].sum()) * BIN
    pt_all = float(total[i0:i1].sum()) * BIN
    if pt_top <= 0 or pt_all <= 0:
        return None
    nb = float(d["births"][i0:i1].sum())
    nd = nb - (d["pop"][i1 - 1] - d["pop"][max(i0 - 1, 0)])
    b_top, d_top = nb / pt_top, nd / pt_top
    b_all = float(tb[i0:i1].sum()) / pt_all
    d_all = float(td[i0:i1].sum()) / pt_all
    return {
        "birth_ratio": b_top / b_all if b_all else float("nan"),
        "death_ratio": d_top / d_all if d_all else float("nan"),
        "net_top": b_top - d_top, "net_all": b_all - d_all,
        "births": nb, "pop": float(d["pop"][i0:i1].mean()),
    }


def batch_summary(batch: Path, threshold: float) -> None:
    """全転移runについて、sweep前と直前の出生率/死亡率比を並べる。"""
    print("転移seedごとの 支配系統/集団全体 比 (出生率・死亡率)")
    print("  A窓 = 転移6,000〜2,000 tick前 (sweepより十分前)")
    print("  B窓 = 転移1,000 tick前〜転移時点 (sweep開始時)")
    print("  純増余地 = 出生比 / 死亡比。1.0なら繁殖優位が死亡で相殺されている")
    print(f"\n{'seed':>5} {'転移tick':>9} | {'A:出生比':>9} {'A:死亡比':>9} "
          f"{'A:純増余地':>11} | {'B:出生比':>9} {'B:死亡比':>9} {'B:純増余地':>11}")
    agg = {"a_b": [], "a_d": [], "a_g": [], "b_b": [], "b_d": [], "b_g": []}
    for run in sorted(batch.iterdir()):
        if not (run / "stats.csv").exists() or not (run / "events.csv").exists():
            continue
        tt, top_id = transition_info(run, threshold)
        if tt is None:
            continue
        seed = run.name.split("seed")[-1]
        a = rates(run, tt, top_id, -6000, -2000)
        b = rates(run, tt, top_id, -1000, 0)
        if a is None or b is None:
            continue
        ag = a["birth_ratio"] / a["death_ratio"] if a["death_ratio"] else float("nan")
        bg = b["birth_ratio"] / b["death_ratio"] if b["death_ratio"] else float("nan")
        if a["births"] >= 10:
            agg["a_b"].append(a["birth_ratio"])
            agg["a_d"].append(a["death_ratio"])
            agg["a_g"].append(ag)
        agg["b_b"].append(b["birth_ratio"])
        agg["b_d"].append(b["death_ratio"])
        agg["b_g"].append(bg)
        print(f"{seed:>5} {tt:>9,} | {a['birth_ratio']:>9.2f} {a['death_ratio']:>9.2f}"
              f" {ag:>11.2f} | {b['birth_ratio']:>9.2f} {b['death_ratio']:>9.2f}"
              f" {bg:>11.2f}")

    def med(x):
        return float(np.nanmedian(x)) if x else float("nan")

    print(f"\n{'中央値':>5} {'':>9} | {med(agg['a_b']):>9.2f} {med(agg['a_d']):>9.2f}"
          f" {med(agg['a_g']):>11.2f} | {med(agg['b_b']):>9.2f} {med(agg['b_d']):>9.2f}"
          f" {med(agg['b_g']):>11.2f}")
    n_gt = sum(1 for g in agg["b_g"] if g > 1.0)
    print(f"\nA窓 (n={len(agg['a_g'])}, 出生数10以上のみ): 純増余地の中央値 "
          f"{med(agg['a_g']):.2f}")
    print(f"B窓 (n={len(agg['b_g'])}): 純増余地の中央値 {med(agg['b_g']):.2f}   "
          f"1.0超のseed {n_gt}/{len(agg['b_g'])}")


def main() -> None:
    ap = argparse.ArgumentParser(description="転移トリガー解析 (Issue #18)")
    ap.add_argument("run_dir")
    ap.add_argument("--threshold", type=float, default=SWEEP_THRESHOLD)
    ap.add_argument("--out", default=None)
    ap.add_argument("--batch", action="store_true",
                    help="run_dir をバッチとして扱い、全転移runを横断集計する")
    args = ap.parse_args()

    if args.batch:
        batch_summary(Path(args.run_dir), args.threshold)
        return

    run = Path(args.run_dir)
    tt, top_id = transition_info(run, args.threshold)
    if tt is None:
        raise SystemExit(f"{run.name}: 転移していない (share>={args.threshold} 未達)")

    print(f"=== {run.name} ===")
    print(f"転移tick {tt:,}   支配系統 id={top_id}")

    # 比較対象: 支配系統 + 転移直前に大きかった他系統
    rivals = {top_id}
    lin_path = run / "lineages.csv"
    if lin_path.exists():
        with open(lin_path, encoding="utf-8") as f:
            near = [r for r in csv.DictReader(f)
                    if abs(int(r["tick"]) - (tt - 4000)) < BIN]
        for r in sorted(near, key=lambda r: -float(r["population"]))[:3]:
            rivals.add(r["lineage_id"])

    series, ticks, total = lineage_series(run, rivals, tt + 3000)
    d = series[top_id]

    def at(t):
        return int(np.clip(t // BIN, 0, len(ticks) - 1))

    print("\n支配系統の推移 (転移tickを0とした相対時間)")
    print(f"{'相対tick':>10} {'人口':>7} {'シェア':>8} {'出生/tick/個体':>15}")
    for rel in (-12000, -8000, -6000, -4000, -3000, -2000, -1000, 0, 1000, 2000):
        if tt + rel < 0:
            continue
        i = at(tt + rel)
        pc = d["per_capita"][i]
        pc_s = f"{pc:.5f}" if np.isfinite(pc) else "-"
        print(f"{rel:>+10,} {d['pop'][i]:>7.0f} {d['share'][i]:>7.1%} {pc_s:>15}")

    # --- 繁殖優位が sweep に先行するか ---
    #
    # 系統人口が数個体しかない時期は、200 tick binの出生数が0か1で
    # per-capita がノイズに支配される。そこで幅の広い窓で
    # 「窓内の総出生数 / 窓内の延べ個体数」として求め、
    # 同じ窓の集団全体平均と比べる (優位の有無は相対値で判断する)。
    def window_rate(pop: np.ndarray, ev: np.ndarray, lo: int, hi: int):
        i0, i1 = at(tt + lo), at(tt + hi)
        if i1 <= i0:
            return float("nan"), 0.0
        person_ticks = float(pop[i0:i1].sum()) * BIN
        n = float(ev[i0:i1].sum())
        return (n / person_ticks if person_ticks > 0 else float("nan")), n

    total_births = np.zeros_like(total, dtype=float)
    total_deaths = np.zeros_like(total, dtype=float)
    with open(run / "events.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ev = r["event"]
            if ev not in ("birth", "death"):
                continue
            t = int(r["tick"])
            if t > tt + 3000:
                break
            (total_births if ev == "birth" else total_deaths)[t // BIN] += 1

    print("\n繁殖優位は sweep に先行するか")
    print("  出生率・死亡率 = 窓内のイベント数 / 延べ個体数。比 = 支配系統 / 集団全体")
    print(f"{'窓 (相対tick)':>18} {'出生比':>7} {'死亡比':>7} {'純増(系統)':>11} "
          f"{'純増(全体)':>11} {'人口':>8} {'出生数':>7}")
    windows = [(-12000, -8000), (-8000, -6000), (-6000, -4000),
               (-4000, -2000), (-2000, -1000), (-1000, 0), (0, 1000)]
    for lo, hi in windows:
        if tt + lo < 0:
            continue
        b_top, nb = window_rate(d["pop"], d["births"], lo, hi)
        b_all, _ = window_rate(total.astype(float), total_births, lo, hi)
        dth = np.zeros_like(d["births"])
        # 系統の死亡数 = 出生 - 人口増分 から復元する
        i0, i1 = at(tt + lo), at(tt + hi)
        d_top_n = float(d["births"][i0:i1].sum() - (d["pop"][i1 - 1] - d["pop"][max(i0 - 1, 0)]))
        pt = float(d["pop"][i0:i1].sum()) * BIN
        d_top = d_top_n / pt if pt > 0 else float("nan")
        d_all, _ = window_rate(total.astype(float), total_deaths, lo, hi)
        rb = b_top / b_all if (b_all and np.isfinite(b_all)) else float("nan")
        rd = d_top / d_all if (d_all and np.isfinite(d_all)) else float("nan")
        pop_here = d["pop"][i0:i1].mean()
        print(f"{f'{lo:+,}〜{hi:+,}':>18} {rb:>7.2f} {rd:>7.2f} "
              f"{b_top - d_top:>+11.5f} {b_all - d_all:>+11.5f} "
              f"{pop_here:>8.1f} {nb:>7.0f}")
    print("  ※ 出生数10未満の窓は計数ノイズが大きく、単独では判断材料にならない")
    print("  ※ 出生比が高くても純増が集団全体と同程度なら、"
          "その優位は人口増加へ変換されていない")

    traits = lineage_traits(run, {top_id})
    tr = traits[top_id]
    if tr.get("body_size"):
        print("\n支配系統の形質 (スナップショット時点)")
        print(f"{'tick':>8} {'相対':>9} {'body_size':>10} {'light_abs':>10} "
              f"{'repro_inv':>10} {'mut_rate':>9}")
        for t in sorted(tr["body_size"]):
            if t > tt + 3000:
                continue
            print(f"{t:>8,} {t - tt:>+9,} {tr['body_size'][t]:>10.3f} "
                  f"{tr['light_absorption'][t]:>10.3f} "
                  f"{tr['reproduction_investment'][t]:>10.3f} "
                  f"{tr['mutation_rate'][t]:>9.4f}")

    out_dir = Path(args.out) if args.out else run / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    rel_t = ticks - tt
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    for l in sorted(rivals):
        s = series[l]
        is_top = l == top_id
        st = dict(color="tab:red" if is_top else "tab:gray",
                  lw=2.0 if is_top else 1.0, alpha=1.0 if is_top else 0.6,
                  label=f"lineage {l}" + (" (winner)" if is_top else ""))
        axes[0].plot(rel_t, s["share"], **st)
        axes[1].plot(rel_t, np.maximum(s["pop"], 0.5), **st)
        pc = np.nan_to_num(s["per_capita"])
        if len(pc) > 5:
            pc = np.convolve(pc, np.ones(5) / 5, mode="same")
        axes[2].plot(rel_t, pc, **st)
    for ax, title, ylab in zip(
            axes, ["Population share", "Lineage population",
                   "Per-capita birth rate (smoothed)"],
            ["share", "individuals", "births / tick / individual"]):
        ax.axvline(0, color="k", ls="--", lw=0.9)
        ax.set_xlabel("ticks relative to sweep")
        ax.set_ylabel(ylab)
        ax.set_title(title)
    axes[1].set_yscale("log")
    axes[0].legend(fontsize=7)
    fig.suptitle(f"{run.name}: does reproductive advantage precede the sweep?")
    fig.tight_layout()
    path = out_dir / "trigger.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"\n図 -> {path}")


if __name__ == "__main__":
    main()
