"""Exp10 の集計プロット生成 (docs/Exp10_実験計画案.md §12)。

    # Phase A の図
    uv run python tools/plot_exp10.py phase-a runs/exp10_phaseA --out <figures>
    # Phase B の図
    uv run python tools/plot_exp10.py phase-b runs/exp10 --out <figures>

計画 §12 が求める最低限:

    1. dQ vs turn rate
    2. 各方式の軌跡比較
    3. high-Q領域滞在率の比較
    4. K3/K4 での空間分布
    5. パラメータスイープheatmap
    6. 代表seedのGIF          ← render_spatial.py が担当 (本ツール外)

図中のラベルは英語にする。日本語フォントは環境依存でCIや他マシンだと
文字化けするため。意味の説明は figures/README.md と結果考察に置く。
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from tools.arena_exp10 import (CONTROL_GAIN, ENVIRONMENTS,  # noqa: E402
                               MEMORY_TAUS, PHENOTYPES, RESPONSE_GAINS,
                               run_arena)
from tools.summarize_exp10 import load, pick  # noqa: E402

PHENO_COLORS = {"lightspec": "#d95f02", "chemspec": "#1b9e77",
                "generalist": "#7570b3"}


# --- Phase A ------------------------------------------------------------

def fig1_turn_response(out: Path) -> Path:
    """dQ と turn rate (曲がり幅) の関係。理論曲線と実測平均。"""
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.4))
    dq = np.linspace(-0.05, 0.05, 400)
    for gain, ls in zip(RESPONSE_GAINS, ("-", "--", "-.", ":")):
        axes[0].plot(dq, 2.0 / (1.0 + np.exp(gain * dq)), ls=ls,
                     label=f"gain={gain:g}")
    axes[0].axhline(1.0, color="black", lw=0.8)
    axes[0].axvline(0.0, color="black", lw=0.8)
    axes[0].set_xlabel("dQ = Q_now - Q_memory")
    axes[0].set_ylabel("turn factor  (sigma_eff / wander_turn_sigma)")
    axes[0].set_title("turn_factor = 2 / (1 + exp(gain * dQ))", fontsize=10)
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25)

    axes[1].annotate("dQ > 0 (improving)\n-> turn less -> keep going",
                     xy=(0.62, 0.72), xycoords="axes fraction", fontsize=10,
                     ha="center", color="#1b9e77")
    axes[1].annotate("dQ < 0 (worsening)\n-> turn more -> re-orient",
                     xy=(0.35, 0.28), xycoords="axes fraction", fontsize=10,
                     ha="center", color="#d95f02")
    axes[1].plot(dq, 2.0 / (1.0 + np.exp(64.0 * dq)), color="#666666", lw=2)
    axes[1].axhline(1.0, color="black", lw=0.8, ls="--")
    axes[1].axvline(0.0, color="black", lw=0.8, ls="--")
    axes[1].set_xlabel("dQ")
    axes[1].set_ylabel("turn factor")
    axes[1].set_title("direction is never computed from dQ", fontsize=10)
    axes[1].grid(alpha=0.25)
    fig.suptitle("Fig.1  Temporal signal only modulates how much the walk turns",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out / "fig1_turn_response.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig3_hi_q(rows, out: Path) -> Path:
    """high-Q領域滞在率: 環境 × 表現型 × gain。"""
    envs = list(ENVIRONMENTS)
    fig, axes = plt.subplots(1, len(envs), figsize=(3.1 * len(envs), 4.2),
                             sharey=True)
    gains = (CONTROL_GAIN,) + RESPONSE_GAINS
    xs = np.arange(len(gains))
    for ax, env in zip(axes, envs):
        for pheno, color in PHENO_COLORS.items():
            ys, lo, hi = [], [], []
            for g in gains:
                tau = MEMORY_TAUS[0] if g == CONTROL_GAIN else 10.0
                v = [r["hi_q_frac"] for r in pick(rows, env, pheno, tau, g)]
                ys.append(st.median(v) if v else np.nan)
                lo.append(min(v) if v else np.nan)
                hi.append(max(v) if v else np.nan)
            ax.plot(xs, ys, "o-", color=color, ms=4, label=pheno)
            ax.fill_between(xs, lo, hi, color=color, alpha=0.15, linewidth=0)
        ax.axhline(0.25, color="black", lw=0.8, ls="--")
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{g:g}" for g in gains], fontsize=8)
        ax.set_xlabel("response_gain")
        ax.set_title(env, fontsize=9)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("high-Q residence fraction  (top-25% cells)")
    axes[0].legend(fontsize=7)
    fig.suptitle("Fig.3  High-Q residence vs response_gain "
                 "(memory_tau=10, band = seed min-max, dashed = chance 0.25)",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    p = out / "fig3_hi_q_residence.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig5_heatmap(rows, out: Path) -> Path:
    """パラメータスイープheatmap: (tau, gain) → high-Q改善量 [pp]。"""
    pairs = (("K1_light_Y", "lightspec"), ("K2_chem_X", "chemspec"),
             ("K3_orthogonal", "generalist"), ("K4_conflict", "generalist"))
    fig, axes = plt.subplots(1, len(pairs), figsize=(3.5 * len(pairs), 4.3))
    vmax = 0.0
    grids = []
    for env, pheno in pairs:
        g = np.full((len(MEMORY_TAUS), len(RESPONSE_GAINS)), np.nan)
        ctrl = {r["seed"]: r["hi_q_frac"]
                for r in pick(rows, env, pheno, MEMORY_TAUS[0], CONTROL_GAIN)}
        for i, tau in enumerate(MEMORY_TAUS):
            for j, gain in enumerate(RESPONSE_GAINS):
                t = pick(rows, env, pheno, tau, gain)
                d = [r["hi_q_frac"] - ctrl[r["seed"]]
                     for r in t if r["seed"] in ctrl]
                if d:
                    g[i, j] = st.median(d) * 100.0
        grids.append(g)
        vmax = max(vmax, float(np.nanmax(np.abs(g))))
    for ax, (env, pheno), g in zip(axes, pairs, grids):
        im = ax.imshow(g, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
        for i in range(g.shape[0]):
            for j in range(g.shape[1]):
                if not math.isnan(g[i, j]):
                    ax.text(j, i, f"{g[i, j]:+.1f}", ha="center", va="center",
                            fontsize=8,
                            color="white" if abs(g[i, j]) > vmax * 0.6 else "black")
        ax.set_xticks(range(len(RESPONSE_GAINS)))
        ax.set_xticklabels([f"{g_:g}" for g_ in RESPONSE_GAINS], fontsize=8)
        ax.set_yticks(range(len(MEMORY_TAUS)))
        ax.set_yticklabels([f"{t:g}" for t in MEMORY_TAUS], fontsize=8)
        ax.set_xlabel("response_gain")
        ax.set_title(f"{env}\n{pheno}", fontsize=9, pad=6)
    axes[0].set_ylabel("memory_tau [tick]")
    fig.colorbar(im, ax=axes, shrink=0.8,
                 label="high-Q residence gain over control [pp]")
    fig.suptitle("Fig.5  Parameter sweep: improvement over the "
                 "response_gain=0 control", fontsize=11, y=1.04)
    p = out / "fig5_param_sweep.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def fig2_fig4_tracks(out: Path, tau: float, gain: float, ticks: int,
                     n_org: int) -> list[Path]:
    """軌跡比較 (Fig.2) と K3/K4 の空間分布 (Fig.4)。

    Phase A本体はCSVしか残さないので、代表条件だけここで再実行して
    軌跡と最終位置を取る。同一seed・同一パラメータなので本体と同じ結果。
    """
    tmp = out / "_tracks"
    tmp.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []

    # --- Fig.2 軌跡比較 (K1 lightspec / control vs treatment) ---
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 5.4))
    for ax, (g, label) in zip(axes, ((CONTROL_GAIN, "control (gain=0)"),
                                     (gain, f"temporal (gain={gain:g})"))):
        f = tmp / f"K1_lightspec_g{g:g}.npz"
        run_arena("K1_light_Y", "lightspec", 1, tau, g, ticks, n_org,
                  track_out=f)
        d = np.load(f)
        cs = float(d["cell_size"])
        qf = d["q_field"]
        ax.imshow(qf.T, origin="upper", cmap="cividis",
                  extent=(0, qf.shape[0] * cs, qf.shape[1] * cs, 0),
                  interpolation="nearest", alpha=0.85)
        for tr in d["tracks"]:
            ax.plot(tr[:, 0], tr[:, 1], lw=0.9, alpha=0.9)
            ax.plot(tr[0, 0], tr[0, 1], "o", ms=3, color="white",
                    markeredgecolor="black", markeredgewidth=0.4)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"K1 light-Y / lightspec — {label}", fontsize=10)
    fig.suptitle("Fig.2  Trajectories (12 individuals, background = Q field; "
                 "bright = high Q). White dot = start.", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out / "fig2_trajectories.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    made.append(p)

    # --- Fig.4 K3 / K4 の最終分布 ---
    cases = [("K3_orthogonal", "generalist"), ("K4_conflict", "lightspec"),
             ("K4_conflict", "chemspec"), ("K4_conflict", "generalist")]
    fig, axes = plt.subplots(2, len(cases), figsize=(3.3 * len(cases), 7.0))
    for col, (env, pheno) in enumerate(cases):
        for row, (g, label) in enumerate(((CONTROL_GAIN, "control"),
                                          (gain, "temporal"))):
            f = tmp / f"{env}_{pheno}_g{g:g}.npz"
            run_arena(env, pheno, 1, tau, g, ticks, n_org, track_out=f)
            d = np.load(f)
            cs = float(d["cell_size"])
            qf = d["q_field"]
            ax = axes[row][col]
            ax.imshow(qf.T, origin="upper", cmap="cividis",
                      extent=(0, qf.shape[0] * cs, qf.shape[1] * cs, 0),
                      interpolation="nearest")
            ax.scatter(d["final_x"], d["final_y"], s=7, c="#ff3d6e",
                       linewidths=0.2, edgecolors="black")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(f"{env}\n{pheno} / {label}", fontsize=8)
    fig.suptitle("Fig.4  Final positions after the arena run "
                 "(background = Q field, bright = high Q)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = out / "fig4_spatial_K3_K4.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    made.append(p)
    return made


# --- Phase B ------------------------------------------------------------

def phase_b_figs(base: Path, out: Path) -> list[Path]:
    from tools.make_exp10_configs import CONDITIONS
    from tools.summarize_exp10_phaseB import load as load_b

    data = load_b(base, 10_000)
    made: list[Path] = []
    conds = [c for c in CONDITIONS if f"{c}_control" in data]

    # Fig.B1 生存とpopulation
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4))
    xs = np.arange(len(conds))
    for k, (rule, off, col) in enumerate((("control", -0.2, "#999999"),
                                          ("treatment", 0.2, "#d95f02"))):
        surv = [sum(s["survived"] for s in data[f"{c}_{rule}"]) for c in conds]
        pops = [st.median([s["final_pop"] for s in data[f"{c}_{rule}"]])
                for c in conds]
        hiq = [st.median([s["hi_q_frac"] for s in data[f"{c}_{rule}"]])
               for c in conds]
        axes[0].bar(xs + off, surv, width=0.4, color=col, label=rule)
        axes[1].bar(xs + off, pops, width=0.4, color=col, label=rule)
        axes[2].bar(xs + off, hiq, width=0.4, color=col, label=rule)
    axes[0].axhline(18, color="red", lw=1.2, ls="--", label="§5.5 threshold 18")
    axes[0].set_ylabel("surviving seeds / 20")
    axes[0].set_title("Survival to 10,000 ticks", fontsize=10)
    axes[1].set_ylabel("final population (median)")
    axes[1].set_title("Final population", fontsize=10)
    axes[2].axhline(0.25, color="black", lw=0.8, ls=":")
    axes[2].set_ylabel("high-Q residence fraction")
    axes[2].set_title("High-Q residence", fontsize=10)
    for ax in axes:
        ax.set_xticks(xs)
        ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=7)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.25, axis="y")
    fig.suptitle("Fig.B1  Phase B: does the temporal rule break the ecology?",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out / "figB1_survival_population.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    made.append(p)

    # Fig.B2 vent距離帯別
    bands = ("d0_1", "d1_2", "d2_4", "d4plus")
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4))
    xs = np.arange(len(bands))
    for c in conds:
        for rule, ls in (("control", "--"), ("treatment", "-")):
            v = data[f"{c}_{rule}"]
            axes[0].plot(xs, [st.median([s[f"band_{b}_frac"] for s in v])
                              for b in bands], ls, marker="o", ms=3,
                         label=f"{c[:2]} {rule}")
            axes[1].plot(xs, [st.median([s[f"band_{b}_sigma"] for s in v])
                              for b in bands], ls, marker="o", ms=3)
            axes[2].plot(xs, [st.median([s[f"band_{b}_chem_e"] for s in v])
                              for b in bands], ls, marker="o", ms=3)
    for ax, ylab, title in ((axes[0], "residence fraction", "Residence"),
                            (axes[1], "sigma_eff", "Turn width"),
                            (axes[2], "cumulative chemical E", "Chemical intake")):
        ax.set_xticks(xs)
        ax.set_xticklabels(bands)
        ax.set_xlabel("distance from nearest vent [cell]")
        ax.set_ylabel(ylab)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)
    axes[2].set_yscale("symlog", linthresh=1.0)
    axes[0].legend(fontsize=6, ncol=2)
    fig.suptitle("Fig.B2  Stratified by distance from the nearest vent "
                 "(where multi-stimulus integration can act)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out / "figB2_vent_bands.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    made.append(p)
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp10 の集計プロット生成")
    ap.add_argument("phase", choices=["phase-a", "phase-b"])
    ap.add_argument("run_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tau", type=float, default=10.0)
    ap.add_argument("--gain", type=float, default=64.0)
    ap.add_argument("--ticks", type=int, default=2000)
    ap.add_argument("--n-org", type=int, default=100)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    if args.phase == "phase-a":
        rows = load(Path(args.run_dir) / "phaseA.csv")
        made.append(fig1_turn_response(out))
        made.append(fig3_hi_q(rows, out))
        made.append(fig5_heatmap(rows, out))
        made += fig2_fig4_tracks(out, args.tau, args.gain, args.ticks,
                                 args.n_org)
    else:
        made += phase_b_figs(Path(args.run_dir), out)
    for p in sorted(made):
        print(f"{p}  ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
