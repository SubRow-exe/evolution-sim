"""Exp06 診断結果の要約 (docs/Exp06_実験計画.md §7-8)。

    uv run python tools/summarize_exp06.py runs/exp06

Exp06はsweep率ではなく「chemical経路が成立するか、どこがボトルネックか」を見る。
そこで条件ごとに以下を出す。

- 絶滅の有無と絶滅tick
- 個体数のピークと終盤の推移 (維持/増加/減少)
- chemical利用量と vent 滞在
- 祖先条件で chemical_absorption がどこまで進化したか

判定は §8 の切り分け表をそのまま当てはめた**候補**を示すだけで、
結論そのものは人が決める。この出力だけで条件を変更しない。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHEM_MILESTONES = (0.5, 1.0, 1.5)
ORDER = ["a_ancestor_random", "b_ancestor_vent", "c_chem_vent", "d_chem_random"]
SHORT = {"a_ancestor_random": "A", "b_ancestor_vent": "B",
         "c_chem_vent": "C", "d_chem_random": "D"}


def load(run: Path) -> list[dict]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f(row: dict, key: str) -> float:
    v = row.get(key, "")
    return float(v) if v not in ("", None) else float("nan")


def summarize_run(run: Path, want_ticks: int) -> dict:
    rows = load(run)
    last = rows[-1]
    pops = [(int(r["tick"]), int(r["population"])) for r in rows]
    alive = [(t, p) for t, p in pops if p > 0]
    peak_tick, peak_pop = max(alive, key=lambda tp: (tp[1], -tp[0])) if alive else (0, 0)
    final_pop = pops[-1][1]
    extinct = final_pop == 0
    # 絶滅tick: 個体数が0になった最初の記録tick
    ext_tick = next((t for t, p in pops if p == 0), None)

    half = want_ticks // 2
    pop_half = next((p for t, p in pops if t >= half), 0)
    if extinct:
        trend = "絶滅"
    elif pop_half == 0:
        trend = "-"
    elif final_pop > pop_half * 1.1:
        trend = "増加"
    elif final_pop < pop_half * 0.9:
        trend = "減少"
    else:
        trend = "維持"

    chem_max = max((f(r, "mean_chemical_absorption") for r in rows
                    if r["population"] != "0"), default=float("nan"))
    vent_frac = max((f(r, "vent_cell_frac") for r in rows
                     if r["population"] != "0"), default=float("nan"))
    return {
        "seed": int(run.name.split("seed")[-1]),
        "last_tick": int(last["tick"]),
        "extinct": extinct,
        "ext_tick": ext_tick,
        "peak_pop": peak_pop,
        "peak_tick": peak_tick,
        "pop_half": pop_half,
        "final_pop": final_pop,
        "trend": trend,
        "chem_flow": f(last, "flow_chemical_cum"),
        "light_flow": f(last, "flow_light_cum"),
        "chem_abs_max": chem_max,
        "vent_frac_max": vent_frac,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp06 診断結果の要約")
    ap.add_argument("exp_dir")
    ap.add_argument("--ticks", type=int, default=10000)
    args = ap.parse_args()

    base = Path(args.exp_dir)
    conds = [d for d in sorted(base.iterdir()) if d.is_dir()]
    conds.sort(key=lambda d: ORDER.index(d.name) if d.name in ORDER else 99)

    survival: dict[str, int] = {}
    totals: dict[str, int] = {}
    for cond in conds:
        runs = sorted(d for d in cond.iterdir()
                      if d.is_dir() and (d / "stats.csv").exists())
        if not runs:
            continue
        stats = [summarize_run(r, args.ticks) for r in runs]
        stats.sort(key=lambda s: s["seed"])
        alive = sum(0 if s["extinct"] else 1 for s in stats)
        survival[cond.name] = alive
        totals[cond.name] = len(stats)

        print(f"\n===== {cond.name} ({SHORT.get(cond.name, '?')}) "
              f"— 生存 {alive}/{len(stats)} =====")
        print(f"{'seed':>5} {'最終tick':>9} {'絶滅tick':>9} {'ピーク人口':>10} "
              f"{'中間人口':>9} {'最終人口':>9} {'推移':>5} "
              f"{'chem_flow':>11} {'chem_abs最大':>12} {'vent滞在最大':>12}")
        for s in stats:
            ext = format(s["ext_tick"], ",") if s["ext_tick"] is not None else "-"
            print(f"{s['seed']:>5} {s['last_tick']:>9,} {ext:>9} "
                  f"{s['peak_pop']:>10,} {s['pop_half']:>9,} {s['final_pop']:>9,} "
                  f"{s['trend']:>5} {s['chem_flow']:>11,.1f} "
                  f"{s['chem_abs_max']:>12.3f} {s['vent_frac_max']:>12.3f}")

        bad_light = [s["seed"] for s in stats if s["light_flow"] != 0.0]
        if bad_light:
            print(f"  ★ light flow が0でないrun: {bad_light} (光0条件が崩れている)")

        if cond.name in ("a_ancestor_random", "b_ancestor_vent"):
            for m in CHEM_MILESTONES:
                hit = [s["seed"] for s in stats if s["chem_abs_max"] >= m]
                print(f"  mean chemical_absorption >= {m}: "
                      f"{len(hit)}/{len(stats)} seed {hit if hit else ''}")

    print("\n" + "=" * 60)
    print("§8 切り分け (生存run数から機械的に当てはめた候補。結論は人が決める)")
    a = survival.get("a_ancestor_random")
    b = survival.get("b_ancestor_vent")
    c = survival.get("c_chem_vent")
    d = survival.get("d_chem_random")
    print(f"  生存run数: A={a} B={b} C={c} D={d}")
    if c == 0:
        print("  → ケース1候補: Cも全滅。chemical生態自体が現行資源・生理では"
              "成立しにくい (chem_capacity / chem_regen / vent面積・生理収支を再検討)")
    elif c and not b:
        print("  → ケース2候補: C生存・B全滅。祖先0.3からの到達に進化上の谷"
              " (初期chemical_absorption / 変異幅 / 収支曲線を再検討)")
    elif b and not a:
        print("  → ケース3候補: B生存・A全滅。ventへの接触・探索がボトルネック"
              " (sensory_range / vent密度 / 探索ルールを再検討)")
    if c and not d:
        print("  → ケース4候補: C生存・D全滅。能力があっても空間アクセスが障害")
    if a:
        print("  → ケース5候補: Aでも成立。chemical経路は閉じていない")
    if any(v is None for v in (a, b, c, d)):
        print("  ※ 4条件が揃っていないため切り分けは不完全")
    mixed = [n for n, v in survival.items() if 0 < v < totals[n]]
    if mixed:
        print(f"  ※ 生存と絶滅が混在する条件: {mixed} "
              "→ 事前規定どおり、その条件だけ seed 11-20 を追加する候補")
    return 0


if __name__ == "__main__":
    sys.exit(main())
