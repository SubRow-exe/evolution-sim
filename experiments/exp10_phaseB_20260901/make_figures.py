"""Exp10 Phase B 集計プロット生成 (docs/実験結果保存方針.md §2)。

数値は正式 Phase B (GitHub Actions / commit 287dc9b8 /
数値実行環境 linux-x86_64-glibc2.39-py3.12.3-np2.5.2) の
summarize_exp10_phaseB.py 出力 (seed中央値、各条件20 seed) をそのまま埋め込む。
図のラベルは英語 (日本語フォントは環境依存で文字化けするため / 計画 §12)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

LABELS = ["B1 light-only\nlightspec", "B2 chem-only\nchemspec",
          "B3 mixed\nlightspec", "B4 mixed\nchemspec", "B5 mixed\ngeneralist"]
X = np.arange(len(LABELS))
W = 0.38
C_CTRL, C_TREAT = "#7f8c9b", "#1b7fbf"

# --- seed medians (Actions 287dc9b8) ---
surv_ctrl = [20, 18, 20, 20, 20]
surv_treat = [20, 20, 20, 20, 20]
pop_ctrl = [784, 16, 803, 368, 972]
pop_treat = [766, 68, 782, 310, 962]
vent_ctrl = [0.000, 0.742, 0.048, 0.280, 0.098]
vent_treat = [0.000, 0.842, 0.077, 0.439, 0.139]
hiq_impr_pp = [1.64, np.nan, 2.57, 10.14, 3.60]   # B2 は指標退化 (hi_q=1.0固定)
frac_impr = [1.00, np.nan, 1.00, 1.00, 1.00]
light_treat = [4_813_445, 0, 4_850_160, 1_353_339, 5_388_469]
chem_treat = [0, 446_536, 97_767, 585_151, 494_822]
# vent距離帯別滞在率 (treatment 中央値): d0-1, d1-2, d2-4, d4+
bands = {
    "B1 light-only": [0.0026, 0.0223, 0.0950, 0.8808],
    "B2 chem-only":  [0.0826, 0.5594, 0.3572, 0.0015],
    "B3 mixed lspec": [0.0069, 0.0506, 0.0943, 0.8497],
    "B4 mixed cspec": [0.0442, 0.2942, 0.2481, 0.4103],
    "B5 mixed gen":  [0.0124, 0.0899, 0.1290, 0.7676],
}
BAND_LABELS = ["d0-1", "d1-2", "d2-4", "d4+"]
BAND_COLORS = ["#c0392b", "#e08e0b", "#2e8b57", "#8a8a8a"]


def _bars(ax, ctrl, treat, ylabel, title, fmt="{:.0f}"):
    ax.bar(X - W / 2, ctrl, W, label="control (gain=0)", color=C_CTRL)
    ax.bar(X + W / 2, treat, W, label="treatment (gain=64)", color=C_TREAT)
    ax.set_xticks(X)
    ax.set_xticklabels(LABELS, fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(axis="y", ls=":", alpha=0.5)


def fig1() -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    axes[0].bar(X - W / 2, surv_ctrl, W, label="control", color=C_CTRL)
    axes[0].bar(X + W / 2, surv_treat, W, label="treatment", color=C_TREAT)
    axes[0].axhline(18, color="#c0392b", ls="--", lw=1,
                    label="§5.5 gate (>=18/20)")
    axes[0].set_ylim(0, 21)
    axes[0].set_xticks(X); axes[0].set_xticklabels(LABELS, fontsize=8)
    axes[0].set_ylabel("seeds surviving 10,000 ticks (of 20)")
    axes[0].set_title("Survival by condition", fontsize=11)
    axes[0].legend(fontsize=8); axes[0].grid(axis="y", ls=":", alpha=0.5)
    _bars(axes[1], pop_ctrl, pop_treat,
          "final population (seed median)", "Final population by condition")
    fig.suptitle("Exp10 Phase B: survival and population "
                 "(evolution OFF, all genes fixed)", fontsize=12)
    fig.tight_layout()
    p = OUT / "fig1_survival_population.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


def fig2() -> Path:
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    _bars(ax, vent_ctrl, vent_treat, "vent-cell residence fraction",
          "Vent residence: treatment stays nearer vents")
    fig.tight_layout()
    p = OUT / "fig2_vent_residence.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


def fig3() -> Path:
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    colors = ["#1b7fbf" if v >= 5 else "#e08e0b" for v in hiq_impr_pp]
    ax.bar(X, hiq_impr_pp, 0.55, color=colors)
    ax.axhline(5.0, color="#c0392b", ls="--", lw=1,
               label="pre-registered +5 pp")
    for i, (v, f) in enumerate(zip(hiq_impr_pp, frac_impr)):
        if np.isnan(v):
            ax.text(i, 0.3, "B2: metric\ndegenerate\n(hi_q=1.0)",
                    ha="center", va="bottom", fontsize=7, color="#666")
        else:
            ax.text(i, v + 0.2, f"+{v:.2f}pp\n{f*100:.0f}% seeds",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(X); ax.set_xticklabels(LABELS, fontsize=8)
    ax.set_ylabel("high-Q residence gain, treatment - control [pp]")
    ax.set_title("§8-3: treatment biases toward high-Q in every condition\n"
                 "(direction: 100% of seeds; magnitude below +5pp = REVIEW)",
                 fontsize=10)
    ax.legend(fontsize=8); ax.grid(axis="y", ls=":", alpha=0.5)
    ax.set_ylim(0, 12)
    fig.tight_layout()
    p = OUT / "fig3_highq_improvement.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


def fig4() -> Path:
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.bar(X - W / 2, light_treat, W, label="light uptake (cum.)",
           color="#e0a80b")
    ax.bar(X + W / 2, chem_treat, W, label="chemical uptake (cum.)",
           color="#1b9e77")
    ax.set_xticks(X); ax.set_xticklabels(LABELS, fontsize=8)
    ax.set_ylabel("cumulative Energy uptake (treatment)")
    ax.set_title("Energy source usage by condition (treatment)", fontsize=11)
    ax.legend(fontsize=8); ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    p = OUT / "fig4_energy_uptake.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


def fig5() -> Path:
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    names = list(bands)
    xb = np.arange(len(names))
    bottom = np.zeros(len(names))
    for j, (bl, col) in enumerate(zip(BAND_LABELS, BAND_COLORS)):
        vals = [bands[n][j] for n in names]
        ax.bar(xb, vals, 0.6, bottom=bottom, label=bl, color=col)
        bottom += np.array(vals)
    ax.set_xticks(xb); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("residence fraction by distance-to-vent band")
    ax.set_title("Vent-distance-band residence (treatment)\n"
                 "chemspec (B4) sits 1-2 cells out; lightspec stays in the "
                 "light gradient (d4+)", fontsize=10)
    ax.legend(fontsize=8, title="band", ncol=4)
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    p = OUT / "fig5_band_residence.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


if __name__ == "__main__":
    for fn in (fig1, fig2, fig3, fig4, fig5):
        print("wrote", fn().relative_to(Path(__file__).resolve().parent))
    sys.exit(0)
