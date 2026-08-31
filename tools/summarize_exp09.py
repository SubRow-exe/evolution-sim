"""Exp09 診断結果の要約 (docs/Exp09_実験計画.md §8-9)。

    uv run python tools/summarize_exp09.py runs/exp09 --ticks 5000

Exp09は光とchemicalの優劣を測る実験ではない。V1.5の異種刺激比較則が
事前登録した式どおりに働いているかを見る。

主判定 (§9):

> その時点のchemical stockが事前計算した交差点stockより上ならchemical、
> 下ならlight という score順位と、実際の一次Energy候補選択が一致すること。

`sel_agree == sel_light + sel_chemical` が全区間で成り立つかを最優先で出し、
そのうえで選択率・response・stock・vent滞在・明暗帯滞在を並べる。

出力は機械的な整理であり、結論は人が決める。
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

from tools.make_exp09_configs import CONDITIONS, PHENOTYPES  # noqa: E402

COND_ORDER = list(CONDITIONS)
LIGHT_LEVELS = (("明部", 1.2), ("中間", 0.78), ("暗部", 0.36))


def num(row: dict, key: str) -> float:
    v = row.get(key, "")
    return float(v) if v not in ("", None) else float("nan")


def rows_of(run: Path) -> list[dict]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def crossover_stock(cfg: dict, light_val: float, light_abs: float,
                    chem_abs: float) -> float:
    kl = cfg["light_stimulus_half"]
    kc = cfg["chemical_stimulus_half"]
    r_l = light_val / (light_val + kl) if light_val > 0 else 0.0
    t = (light_abs / chem_abs) * r_l
    return math.inf if t >= 1.0 else kc * t / (1.0 - t)


def summarize_run(run: Path, want_ticks: int) -> dict:
    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    rows = rows_of(run)
    last = rows[-1]
    final_tick = int(last["tick"])
    final_pop = int(last["population"])

    def total(key: str) -> float:
        return sum(num(r, key) for r in rows if not math.isnan(num(r, key)))

    sel_l, sel_c = total("sel_light"), total("sel_chemical")
    tie, walk = total("sel_tie"), total("sel_walk")
    both, agree = total("sel_both_events"), total("sel_agree")
    picks = sel_l + sel_c
    # 区間平均の重み付き平均 (both_events で重み付け)
    def weighted(key: str) -> float:
        num_, den = 0.0, 0.0
        for r in rows:
            w = num(r, "sel_both_events")
            v = num(r, key)
            if w > 0 and not math.isnan(v):
                num_ += w * v
                den += w
        return num_ / den if den else float("nan")

    return {
        "seed": int(run.name.split("seed")[-1]),
        "final_tick": final_tick, "final_pop": final_pop,
        "extinct": final_pop == 0, "halted": final_pop > 0 and final_tick < want_ticks,
        "sel_light": sel_l, "sel_chemical": sel_c, "tie": tie, "walk": walk,
        "both": both, "agree": agree, "picks": picks,
        "chem_pick_frac": (sel_c / picks) if picks else float("nan"),
        "tie_frac": (tie / both) if both else float("nan"),
        "light_resp": weighted("sel_light_resp_mean"),
        "chem_resp": weighted("sel_chem_resp_mean"),
        "chem_stock": weighted("sel_chem_stock_mean"),
        "lost_light": total("sel_lost_light"),
        "lost_chemical": total("sel_lost_chemical"),
        "light_flow": num(last, "flow_light_cum"),
        "chem_flow": num(last, "flow_chemical_cum"),
        "vent_frac": num(last, "vent_cell_frac"),
        "north": num(last, "frac_north_band"),
        "middle": num(last, "frac_middle_band"),
        "south": num(last, "frac_south_band"),
        "cfg": cfg,
    }


def _median(vals: list[float]) -> float:
    vals = [v for v in vals if not math.isnan(v)]
    if not vals:
        return float("nan")
    return sorted(vals)[len(vals) // 2]


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp09 診断結果の要約")
    ap.add_argument("exp_dir")
    ap.add_argument("--ticks", type=int, default=5000)
    args = ap.parse_args()

    base = Path(args.exp_dir)
    data: dict[str, list[dict]] = {}
    for d in sorted(x for x in base.iterdir() if x.is_dir() and x.name in CONDITIONS):
        runs = sorted(r for r in d.iterdir()
                      if r.is_dir() and (r / "stats.csv").exists())
        if runs:
            data[d.name] = sorted((summarize_run(r, args.ticks) for r in runs),
                                  key=lambda s: s["seed"])
    if not data:
        print(f"★ {base} に Exp09 の run が無い")
        return 0

    conds = [c for c in COND_ORDER if c in data]

    # --- 主判定: score順位と実選択の一致 ---
    print("=== 主判定: 無次元scoreの順位と実際のsource選択が一致するか ===")
    print(f"{'条件':<24}{'一致':>10}{'選択回数':>12}{'一致率':>9}")
    bad = []
    for c in conds:
        agree = sum(s["agree"] for s in data[c])
        picks = sum(s["picks"] for s in data[c])
        rate = agree / picks if picks else float("nan")
        print(f"{c:<24}{agree:>10,.0f}{picks:>12,.0f}{rate:>9.4f}")
        if picks and agree != picks:
            bad.append(c)
    print("  → 1.0000 でなければV1.5比較則の実装不整合 (停止条件)"
          if bad else "  → 全条件で一致 (交差点式どおり)")

    # --- 交差点stock (事前計算値) ---
    print("\n=== 事前計算した交差点stock [E/cell] ===")
    cfg0 = data[conds[0]][0]["cfg"]
    print(f"{'表現型':<22}" + "".join(f"{n + ' L=' + f'{v:g}':>16}"
                                      for n, v in LIGHT_LEVELS))
    for pheno, genes in PHENOTYPES.items():
        row = f"{pheno:<22}"
        for _, lv in LIGHT_LEVELS:
            s = crossover_stock(cfg0, lv, genes["light_absorption"],
                                genes["chemical_absorption"])
            row += f"{'交差点なし':>16}" if math.isinf(s) else f"{s:>16.2f}"
        print(row)

    # --- 条件ごとの選択統計 ---
    print("\n=== 条件別 選択統計 (seed集計) ===")
    print(f"{'条件':<24}{'seed':>5}{'最終pop':>8}{'chem選択率':>11}{'tie率':>8}"
          f"{'walk':>10}{'light応答':>10}{'chem応答':>10}{'chem stock':>11}"
          f"{'vent滞在':>9}")
    for c in conds:
        for s in data[c]:
            print(f"{c:<24}{s['seed']:>5}{s['final_pop']:>8,}"
                  f"{s['chem_pick_frac']:>11.4f}{s['tie_frac']:>8.4f}"
                  f"{s['walk']:>10,.0f}{s['light_resp']:>10.4f}"
                  f"{s['chem_resp']:>10.4f}{s['chem_stock']:>11.4f}"
                  f"{s['vent_frac']:>9.3f}")

    print("\n=== 条件別サマリ (中央値) ===")
    print(f"{'条件':<24}{'最終pop':>9}{'chem選択率':>11}{'chem stock':>11}"
          f"{'vent滞在':>9}{'light flow':>12}{'chem flow':>12}"
          f"{'north':>7}{'middle':>7}{'south':>7}")
    for c in conds:
        v = data[c]
        print(f"{c:<24}{_median([s['final_pop'] for s in v]):>9,.0f}"
              f"{_median([s['chem_pick_frac'] for s in v]):>11.4f}"
              f"{_median([s['chem_stock'] for s in v]):>11.4f}"
              f"{_median([s['vent_frac'] for s in v]):>9.3f}"
              f"{_median([s['light_flow'] for s in v]):>12,.0f}"
              f"{_median([s['chem_flow'] for s in v]):>12,.0f}"
              f"{_median([s['north'] for s in v]):>7.2f}"
              f"{_median([s['middle'] for s in v]):>7.2f}"
              f"{_median([s['south'] for s in v]):>7.2f}")

    # --- legacy scoreとの二重尺度の影響 ---
    print("\n=== 一次Energy候補が他刺激 (栄養/死骸/捕食) に負けた回数 ===")
    print(f"{'条件':<24}{'light由来':>12}{'chemical由来':>14}{'選択回数':>12}")
    for c in conds:
        v = data[c]
        print(f"{c:<24}{sum(s['lost_light'] for s in v):>12,.0f}"
              f"{sum(s['lost_chemical'] for s in v):>14,.0f}"
              f"{sum(s['picks'] for s in v):>12,.0f}")

    print("\n" + "=" * 60)
    print("読み方 (計画 §9):")
    print("  - 主判定は score順位と実選択の一致。選択率やvent滞在率の水準では判定しない")
    print("  - 占有中のventはstockが下がるため、交差点を下回ればlightを選ぶのが式どおり")
    print("  - 絶滅・低population・低vent滞在率はそれだけでは実装異常ではない")
    return 0


if __name__ == "__main__":
    sys.exit(main())
