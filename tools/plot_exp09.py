"""Exp09 集計プロットの生成 (docs/実験結果保存方針.md §2)。

    uv run python tools/plot_exp09.py runs/exp09 --out experiments/<exp_id>/figures

Exp09は光とchemicalの優劣を測る実験ではなく、V1.5の異種刺激比較則
(無次元response `x/(x+K)` による比較) が事前登録した式どおりに働いているかを
見る診断実験である。したがって図も「式どおりか」を見るためのものにする。

出力 (6枚):

    fig1_agreement.png      主判定: score順位と実選択の一致率 (条件別)
    fig2_score_curves.png   理論: chemical stockに対するscore曲線と交差点
    fig3_stock_vs_pick.png  実測: 区間ごとの (chem stock, chem選択率) と交差点
    fig4_timeseries.png     時間推移: population / chem stock / chem選択率 / vent滞在
    fig5_response.png       response水準 (light応答 vs chemical応答)
    fig6_flows.png          Energy取得の累積内訳 (light / chemical)

図中のラベルは英語にする。日本語フォントは環境依存で、CIや他マシンで
文字化けするため。図の日本語説明は figures/README.md と
docs/Exp09_結果考察.md に置く。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from tools.make_exp09_configs import CONDITIONS, PHENOTYPES  # noqa: E402

COND_ORDER = list(CONDITIONS)
# 条件ごとの色 (全図で統一)
COLORS = {
    "a_light_only_lightspec": "#d95f02",
    "b_chem_only_chemspec": "#1b9e77",
    "c_mixed_lightspec": "#7570b3",
    "d_mixed_chemspec": "#e7298a",
    "e_mixed_generalist": "#666666",
}
# 光の代表水準 (vertical patternの明部/中間/暗部)
LIGHT_LEVELS = (("bright L=1.2", 1.2), ("mid L=0.78", 0.78), ("dark L=0.36", 0.36))


def num(row: dict, key: str) -> float:
    v = row.get(key, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(base: Path) -> dict[str, list[tuple[int, list[dict], dict]]]:
    """条件名 -> [(seed, stats行, config), ...]"""
    data: dict[str, list[tuple[int, list[dict], dict]]] = {}
    for d in sorted(x for x in base.iterdir() if x.is_dir() and x.name in CONDITIONS):
        runs = []
        for r in sorted(d.iterdir()):
            if not (r / "stats.csv").exists():
                continue
            with open(r / "stats.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            cfg = json.loads((r / "config.json").read_text(encoding="utf-8"))
            runs.append((int(r.name.split("seed")[-1]), rows, cfg))
        if runs:
            data[d.name] = sorted(runs, key=lambda t: t[0])
    return data


def crossover_stock(kl: float, kc: float, light_val: float,
                    light_abs: float, chem_abs: float) -> float:
    """light_score == chemical_score となる chemical stock [E/cell]。

    t = (light_abs/chem_abs) * response(L, Kl) が1以上なら交差点は存在しない
    (どれだけstockを上げてもchemicalがlightに追いつけない)。
    """
    r_l = light_val / (light_val + kl) if light_val > 0 else 0.0
    t = (light_abs / chem_abs) * r_l
    return math.inf if t >= 1.0 else kc * t / (1.0 - t)


def totals(rows: list[dict], key: str) -> float:
    return float(np.nansum([num(r, key) for r in rows]))


def fig1_agreement(data, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    conds = [c for c in COND_ORDER if c in data]
    rates, labels, picks_all = [], [], []
    for c in conds:
        agree = sum(totals(rows, "sel_agree") for _, rows, _ in data[c])
        picks = sum(totals(rows, "sel_light") + totals(rows, "sel_chemical")
                    for _, rows, _ in data[c])
        rates.append(agree / picks if picks else float("nan"))
        picks_all.append(picks)
        labels.append(c)
    xs = np.arange(len(conds))
    ax.bar(xs, rates, color=[COLORS[c] for c in conds], width=0.6)
    ax.axhline(1.0, color="black", lw=1.0, ls="--")
    for x, r, p in zip(xs, rates, picks_all):
        ax.text(x, r + 0.012, f"{r:.4f}\n{p:,.0f} picks", ha="center",
                fontsize=8)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=8, rotation=12, ha="right")
    ax.set_ylim(0.0, 1.12)
    ax.set_ylabel("agreement (sel_agree / picks)")
    ax.set_title("Fig.1  Main judgement: score order vs actual source choice")
    fig.tight_layout()
    p = out / "fig1_agreement.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig2_score_curves(data, out: Path) -> Path:
    cfg = next(iter(data.values()))[0][2]
    kl, kc = cfg["light_stimulus_half"], cfg["chemical_stimulus_half"]
    stocks = np.linspace(0.0, 20.0, 400)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), sharey=True)
    for ax, (pheno, genes) in zip(axes, PHENOTYPES.items()):
        la, ca = genes["light_absorption"], genes["chemical_absorption"]
        n_cross = 0
        ax.plot(stocks, ca * stocks / (stocks + kc), color="#1b9e77", lw=2.0,
                label=f"chemical_score (a={ca})")
        for (name, lv), ls in zip(LIGHT_LEVELS, ("-", "--", ":")):
            score = la * lv / (lv + kl)
            ax.axhline(score, color="#d95f02", lw=1.5, ls=ls,
                       label=f"light_score {name}")
            s = crossover_stock(kl, kc, lv, la, ca)
            if math.isfinite(s) and s <= stocks[-1]:
                ax.plot([s], [score], "ko", ms=5)
                # 交差点が近接する表現型があるので注記を段違いにする
                ax.annotate(f"{s:.2f}", (s, score), textcoords="offset points",
                            xytext=(10 + 30 * n_cross, 10 + 16 * n_cross), fontsize=8,
                            arrowprops=dict(arrowstyle="-", lw=0.6))
                n_cross += 1
        ax.set_title(f"{pheno}  (light_abs={la}, chem_abs={ca})", fontsize=10)
        ax.set_xlabel("chemical stock [E/cell]")
        ax.grid(alpha=0.25)
        if n_cross == 0:
            ax.text(0.5, 0.06, "no crossover: chemical never overtakes light",
                    transform=ax.transAxes, ha="center", fontsize=8,
                    style="italic")
    axes[0].set_ylabel("dimensionless score")
    axes[0].legend(fontsize=7, loc="upper left")
    fig.suptitle("Fig.2  V1.5 score curves and crossover stock "
                 f"(K_light={kl}, K_chem={kc})", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = out / "fig2_score_curves.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig3_stock_vs_pick(data, out: Path) -> Path:
    """区間ごとの (感知chemical stock平均, chemical選択率) 散布。

    交差点stockより上ならchemical、下ならlightを選ぶはず — という
    式の含意を集団水準で確認する。

    横軸の`sel_chem_stock_mean`は「選択時に感知範囲内で見えた最良の
    chemical stock」の平均であり、個体が乗っているセルのstockではない。
    ventが感知範囲に無い個体では0になるため、混合条件では0に強く引かれる。
    """
    cfg = next(iter(data.values()))[0][2]
    kl, kc = cfg["light_stimulus_half"], cfg["chemical_stimulus_half"]
    conds = [c for c in COND_ORDER if c in data]
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    for c in conds:
        xs, ys = [], []
        for _, rows, _ in data[c]:
            for r in rows:
                both = num(r, "sel_both_events")
                picks = num(r, "sel_light") + num(r, "sel_chemical")
                if both > 0 and picks > 0:
                    xs.append(num(r, "sel_chem_stock_mean"))
                    ys.append(num(r, "sel_chemical") / picks)
        ax.scatter(xs, ys, s=5, alpha=0.30, color=COLORS[c], label=c,
                   linewidths=0)
    for pheno, ls in zip(("chemspec", "generalist"), ("--", ":")):
        genes = PHENOTYPES[pheno]
        for (name, lv), alpha in zip(LIGHT_LEVELS, (1.0, 0.6, 0.35)):
            s = crossover_stock(kl, kc, lv, genes["light_absorption"],
                                genes["chemical_absorption"])
            if math.isfinite(s):
                ax.axvline(s, color="black", ls=ls, lw=1.0, alpha=alpha)
                ax.text(s, 1.03, f"{pheno[:4]} {name.split()[0]}\n{s:.2f}",
                        rotation=90, fontsize=6, va="bottom", ha="center")
    ax.set_xscale("symlog", linthresh=0.05)
    ax.set_xlim(left=0.0)
    ax.set_xlabel("mean best perceived chemical stock at choice [E/cell]  (symlog)")
    ax.set_ylabel("chemical pick fraction per stats interval")
    ax.set_ylim(-0.05, 1.15)
    ax.legend(fontsize=7, markerscale=3, loc="center left")
    ax.grid(alpha=0.25)
    ax.set_title("Fig.3  Chemical pick fraction vs best perceived chemical stock")
    fig.tight_layout()
    p = out / "fig3_stock_vs_pick.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig4_timeseries(data, out: Path) -> Path:
    conds = [c for c in COND_ORDER if c in data]
    panels = [
        ("population", lambda r: num(r, "population"), "population"),
        ("best perceived chem stock at choice",
         lambda r: num(r, "sel_chem_stock_mean"), "chemical stock [E/cell]"),
        ("chemical pick fraction", None, "chemical pick fraction"),
        ("vent cell fraction", lambda r: num(r, "vent_cell_frac"),
         "vent_cell_frac"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.4))
    for ax, (title, fn, ylab) in zip(axes.ravel(), panels):
        for c in conds:
            for i, (seed, rows, _) in enumerate(data[c]):
                t = [num(r, "tick") for r in rows]
                if fn is None:
                    y = []
                    for r in rows:
                        p = num(r, "sel_light") + num(r, "sel_chemical")
                        y.append(num(r, "sel_chemical") / p if p > 0 else np.nan)
                else:
                    y = [fn(r) for r in rows]
                ax.plot(t, y, color=COLORS[c], lw=0.8, alpha=0.55,
                        label=c if i == 0 else None)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("tick")
        ax.set_ylabel(ylab, fontsize=9)
        ax.grid(alpha=0.25)
    axes[0][0].legend(fontsize=7)
    fig.suptitle("Fig.4  Time series (5 seeds per condition)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = out / "fig4_timeseries.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig5_response(data, out: Path) -> Path:
    """選択時のresponse水準。light側は表現型で決まりほぼ一定、
    chemical側はstockに追随することを見る。"""
    conds = [c for c in COND_ORDER if c in data]
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.4), sharex=True)
    for ax, key, ylab in ((axes[0], "sel_light_resp_mean", "light response"),
                          (axes[1], "sel_chem_resp_mean", "chemical response")):
        for c in conds:
            for i, (seed, rows, _) in enumerate(data[c]):
                t = [num(r, "tick") for r in rows]
                y = [num(r, key) for r in rows]
                ax.plot(t, y, color=COLORS[c], lw=0.8, alpha=0.55,
                        label=c if i == 0 else None)
        ax.set_ylabel(ylab)
        ax.set_xlabel("tick")
        ax.grid(alpha=0.25)
    axes[0].legend(fontsize=7)
    fig.suptitle("Fig.5  Mean response x/(x+K) of the best perceived cell at choice",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out / "fig5_response.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def fig6_flows(data, out: Path) -> Path:
    conds = [c for c in COND_ORDER if c in data]
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.4))
    lights, chems = [], []
    for c in conds:
        lights.append(np.median([num(rows[-1], "flow_light_cum")
                                 for _, rows, _ in data[c]]))
        chems.append(np.median([num(rows[-1], "flow_chemical_cum")
                                for _, rows, _ in data[c]]))
    xs = np.arange(len(conds))
    axes[0].bar(xs - 0.2, lights, width=0.4, color="#d95f02", label="light")
    axes[0].bar(xs + 0.2, chems, width=0.4, color="#1b9e77", label="chemical")
    axes[0].set_yscale("symlog", linthresh=100)
    axes[0].set_xticks(xs)
    axes[0].set_xticklabels(conds, fontsize=7, rotation=15, ha="right")
    axes[0].set_ylabel("cumulative energy intake [E]  (symlog)")
    axes[0].set_title("Median cumulative intake at tick 5000", fontsize=10)
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25, axis="y")

    for c in conds:
        for i, (seed, rows, _) in enumerate(data[c]):
            t = [num(r, "tick") for r in rows]
            tot = [num(r, "flow_light_cum") + num(r, "flow_chemical_cum")
                   for r in rows]
            y = [(num(r, "flow_chemical_cum") / v) if v > 0 else np.nan
                 for r, v in zip(rows, tot)]
            axes[1].plot(t, y, color=COLORS[c], lw=0.8, alpha=0.55,
                         label=c if i == 0 else None)
    axes[1].set_xlabel("tick")
    axes[1].set_ylabel("chemical share of primary energy intake")
    axes[1].set_ylim(-0.05, 1.05)
    axes[1].grid(alpha=0.25)
    axes[1].legend(fontsize=7)
    axes[1].set_title("Chemical share of cumulative intake", fontsize=10)
    fig.suptitle("Fig.6  Where the primary energy actually came from",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out / "fig6_flows.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp09 集計プロットの生成")
    ap.add_argument("exp_dir", help="条件ディレクトリを含むディレクトリ")
    ap.add_argument("--out", required=True, help="図の出力先")
    args = ap.parse_args()

    data = load(Path(args.exp_dir))
    if not data:
        print(f"★ {args.exp_dir} に Exp09 の run が無い")
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for fn in (fig1_agreement, fig2_score_curves, fig3_stock_vs_pick,
               fig4_timeseries, fig5_response, fig6_flows):
        p = fn(data, out)
        print(f"{p}  ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
