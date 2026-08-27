"""Matplotlibグラフ生成 (仕様書 Ver.1.1 §14.3)。

stats.csv / snapshots からPNGを生成する。GUIのGキーおよび tools/plot_run.py から呼ぶ。
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..genome import GENE_NAMES


def _load_stats(run_dir: Path) -> dict[str, np.ndarray]:
    path = run_dir / "stats.csv"
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [[float(v) if v != "" else np.nan for v in r] for r in reader if r]
    data = np.array(rows) if rows else np.zeros((0, len(header)))
    return {name: data[:, i] for i, name in enumerate(header)}


def _disaster_ticks(run_dir: Path) -> list[int]:
    path = run_dir / "events.csv"
    ticks = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["event"] == "disaster":
                    ticks.append(int(row["tick"]))
    return ticks


def _mark_disasters(ax, disasters: list[int]) -> None:
    for t in disasters:
        ax.axvline(t, color="red", ls="--", lw=0.8, alpha=0.6)


def plot_run(run_dir: str | Path) -> Path:
    """実行ディレクトリの全グラフを plots/ に生成する。"""
    run_dir = Path(run_dir)
    out = run_dir / "plots"
    out.mkdir(exist_ok=True)
    s = _load_stats(run_dir)
    dis = _disaster_ticks(run_dir)
    t = s["tick"]

    # --- 個体群動態 ---
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    ax = axes[0, 0]
    ax.plot(t, s["population"], color="tab:blue")
    ax.set_title("Population")
    _mark_disasters(ax, dis)

    ax = axes[0, 1]
    for c, color in [("starvation", "tab:orange"), ("damage", "tab:gray"),
                     ("predation", "tab:red"), ("disaster", "tab:purple")]:
        ax.plot(t, s[f"deaths_{c}"], label=c, color=color)
    ax.set_title("Cumulative deaths by cause")
    ax.legend(fontsize=8)
    _mark_disasters(ax, dis)

    ax = axes[1, 0]
    ax.plot(t, s["mean_age"], label="mean age")
    ax.plot(t, s["max_age"], label="max age", alpha=0.6)
    ax.set_title("Age")
    ax.legend(fontsize=8)
    _mark_disasters(ax, dis)

    ax = axes[1, 1]
    ax.plot(t, s["n_lineages"], color="tab:green")
    ax.set_title("Lineages")
    _mark_disasters(ax, dis)
    for a in axes.flat:
        a.set_xlabel("tick")
    fig.tight_layout()
    fig.savefig(out / "population.png", dpi=110)
    plt.close(fig)

    # --- 遺伝子平均 (分散帯付き) ---
    fig, axes = plt.subplots(4, 4, figsize=(16, 12))
    for i, name in enumerate(GENE_NAMES):
        ax = axes.flat[i]
        mean = s[f"mean_{name}"]
        std = np.sqrt(np.maximum(s[f"var_{name}"], 0.0))
        ax.plot(t, mean, color="tab:blue", lw=1.2)
        ax.fill_between(t, mean - std, mean + std, color="tab:blue", alpha=0.2)
        ax.set_title(name, fontsize=9)
        _mark_disasters(ax, dis)
    for i in range(len(GENE_NAMES), len(axes.flat)):
        axes.flat[i].axis("off")
    fig.suptitle("Gene means ± std (red dashed = disaster)")
    fig.tight_layout()
    fig.savefig(out / "genes.png", dpi=110)
    plt.close(fig)

    # --- エネルギー・物質収支 ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    ax = axes[0]
    ax.plot(t, s["total_energy"], label="organisms E")
    ax.plot(t, s["corpse_energy"], label="corpses E")
    ax.plot(t, s["chemical_total"], label="chemical stock")
    ax.set_title("Energy stocks")
    ax.legend(fontsize=8)
    _mark_disasters(ax, dis)
    ax = axes[1]
    ax.plot(t, s["total_biomass"], label="biomass")
    ax.plot(t, s["corpse_matter"], label="corpse matter")
    ax.plot(t, s["nutrient_total"], label="inorganic nutrients")
    total = s["total_biomass"] + s["corpse_matter"] + s["nutrient_total"]
    ax.plot(t, total, label="TOTAL (conserved)", color="black", ls=":")
    ax.set_title("Matter cycle")
    ax.legend(fontsize=8)
    _mark_disasters(ax, dis)
    for a in axes:
        a.set_xlabel("tick")
    fig.tight_layout()
    fig.savefig(out / "budget.png", dpi=110)
    plt.close(fig)

    # --- 最新スナップショットの遺伝子ヒストグラム ---
    snaps = sorted((run_dir / "snapshots").glob("snap_*.csv"))
    if snaps:
        with open(snaps[-1], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if rows:
            fig, axes = plt.subplots(4, 4, figsize=(16, 12))
            for i, name in enumerate(GENE_NAMES):
                vals = np.array([float(r[name]) for r in rows])
                ax = axes.flat[i]
                ax.hist(vals, bins=40, color="tab:green", alpha=0.8)
                ax.set_title(name, fontsize=9)
            for i in range(len(GENE_NAMES), len(axes.flat)):
                axes.flat[i].axis("off")
            fig.suptitle(f"Gene distributions @ {snaps[-1].stem}")
            fig.tight_layout()
            fig.savefig(out / "histograms.png", dpi=110)
            plt.close(fig)

    return out
