"""Exp07 診断結果の要約 (docs/Exp07_実験計画.md §8-9)。

    uv run python tools/summarize_exp07.py runs/exp07 --ticks 120000

judgement の順序は計画 §9 と同じ:

  段階1: C (chem2.0/vent) が長期持続する chem_vent_flux 境界
  段階2: C成立域で B (祖先/vent) の進化bootstrap
  段階3: C成立域で D (chem2.0/random) の空間access

Bは生存/絶滅の二値で読まない。祖先の収支上、chemical吸収だけで黒字化するには
`chemical_absorption ≈ 0.9` (実効1.0前後) が必要で、初期値0.3の約3倍である。
そのため到達マイルストーンと初回tickを併記する。

出力は機械的な整理であり、結論と次に動かす1軸は人が決める。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIR_RE = re.compile(r"^flux(\d+)_(.+)$")
MILESTONES = (0.5, 0.9, 1.2, 1.5, 2.0)   # 0.9 = 祖先の黒字化ライン (計画 §8)
COND_ORDER = ["c_chem_vent", "b_ancestor_vent", "d_chem_random"]
SHORT = {"c_chem_vent": "C", "b_ancestor_vent": "B", "d_chem_random": "D"}


def rows_of(run: Path) -> list[dict]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(row: dict, key: str) -> float:
    v = row.get(key, "")
    return float(v) if v not in ("", None) else float("nan")


def summarize_run(run: Path, want_ticks: int) -> dict:
    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    rows = rows_of(run)
    last = rows[-1]
    pops = [(int(r["tick"]), int(r["population"])) for r in rows]
    final_tick, final_pop = pops[-1]
    extinct = final_pop == 0
    ext_tick = next((t for t, p in pops if p == 0), None)
    halted = (not extinct) and final_tick < want_ticks
    alive = [(t, p) for t, p in pops if p > 0]
    peak_tick, peak_pop = max(alive, key=lambda tp: (tp[1], -tp[0])) if alive else (0, 0)

    half = want_ticks // 2
    pop_half = next((p for t, p in pops if t >= half), 0)
    if extinct:
        trend = "絶滅"
    elif halted:
        trend = "halt"
    elif pop_half == 0:
        trend = "-"
    elif final_pop > pop_half * 1.1:
        trend = "増加"
    elif final_pop < pop_half * 0.9:
        trend = "減少"
    else:
        trend = "維持"

    # chemical収支。環境損失は台帳の恒等式から導く:
    #   loss = influx - uptake - (stock_final - stock_initial)
    source_per_tick = cfg["n_vents"] * cfg["chem_vent_flux"]
    influx = source_per_tick * final_tick
    uptake = num(last, "flow_chemical_cum")
    stock0 = num(rows[0], "chemical_total")
    stock1 = num(last, "chemical_total")
    loss = influx - uptake - (stock1 - stock0)
    use_rate = uptake / influx if influx > 0 else float("nan")

    chem_rows = [r for r in rows if r["population"] != "0"]
    chem_abs_max = max((num(r, "mean_chemical_absorption") for r in chem_rows),
                       default=float("nan"))
    milestones = {}
    for m in MILESTONES:
        hit = next((int(r["tick"]) for r in chem_rows
                    if num(r, "mean_chemical_absorption") >= m), None)
        milestones[m] = hit
    vent_frac_last = num(last, "vent_cell_frac")
    vent_frac_max = max((num(r, "vent_cell_frac") for r in chem_rows),
                        default=float("nan"))
    stock_mean = (sum(num(r, "chemical_total") for r in rows) / len(rows)) if rows else 0.0

    return {
        "seed": int(run.name.split("seed")[-1]),
        "final_tick": final_tick, "extinct": extinct, "ext_tick": ext_tick,
        "halted": halted, "peak_pop": peak_pop, "peak_tick": peak_tick,
        "pop_half": pop_half, "final_pop": final_pop, "trend": trend,
        "uptake": uptake, "influx": influx, "loss": loss, "use_rate": use_rate,
        "stock_mean": stock_mean, "stock_final": stock1,
        "chem_abs_max": chem_abs_max, "milestones": milestones,
        "vent_frac_last": vent_frac_last, "vent_frac_max": vent_frac_max,
        "light_flow": num(last, "flow_light_cum"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp07 診断結果の要約")
    ap.add_argument("exp_dir")
    ap.add_argument("--ticks", type=int, default=120000)
    args = ap.parse_args()

    base = Path(args.exp_dir)
    data: dict[tuple[int, str], list[dict]] = {}
    for d in sorted(x for x in base.iterdir() if x.is_dir() and DIR_RE.match(x.name)):
        m = DIR_RE.match(d.name)
        flux, name = int(m.group(1)), m.group(2)
        runs = sorted(r for r in d.iterdir()
                      if r.is_dir() and (r / "stats.csv").exists())
        if runs:
            data[(flux, name)] = sorted((summarize_run(r, args.ticks) for r in runs),
                                        key=lambda s: s["seed"])

    fluxes = sorted({f for f, _ in data})
    conds = [c for c in COND_ORDER if any((f, c) in data for f in fluxes)]

    bad_light = [(f, c, s["seed"]) for (f, c), v in data.items()
                 for s in v if s["light_flow"] != 0.0]
    if bad_light:
        print(f"★ light flow が0でないrun: {bad_light} — 光0条件が崩れている\n")

    # --- 条件 × flux の生存率 ---
    print("=== 生存率 (指定tickまで絶滅もhaltもしなかったrun / 全run) ===")
    print(f"{'flux':>5} {'世界source':>10} " + " ".join(f"{SHORT[c]:>12}" for c in conds))
    for f in fluxes:
        cells = []
        for c in conds:
            v = data.get((f, c))
            if not v:
                cells.append(f"{'-':>12}")
                continue
            surv = sum(1 for s in v if not s["extinct"] and not s["halted"])
            halt = sum(1 for s in v if s["halted"])
            mark = f"{surv}/{len(v)}" + (f" (halt{halt})" if halt else "")
            cells.append(f"{mark:>12}")
        print(f"{f:>5} {f*4:>10} " + " ".join(cells))

    frail = [(f, SHORT[c], s["seed"], s["final_pop"])
             for (f, c), v in data.items() for s in v
             if not s["extinct"] and not s["halted"] and s["final_pop"] < 20]
    if frail:
        print("\n  ※ 最終個体数が20未満のrun (崩壊途中の可能性。生存と読まない):")
        for f, c, seed, pop in sorted(frail):
            print(f"     flux {f} {c} seed {seed}: 最終 {pop} 個体")

    # --- 条件ごとの詳細 ---
    for c in conds:
        print(f"\n===== {SHORT[c]} — {c} =====")
        print(f"{'flux':>5} {'seed':>5} {'最終tick':>9} {'絶滅tick':>9} {'ピーク':>8} "
              f"{'中間':>8} {'最終':>8} {'推移':>5} {'uptake':>12} {'利用率':>7} "
              f"{'平均stock':>10} {'vent滞在':>8} {'chem_abs最大':>12}")
        for f in fluxes:
            for s in data.get((f, c), []):
                ext = format(s["ext_tick"], ",") if s["ext_tick"] is not None else "-"
                print(f"{f:>5} {s['seed']:>5} {s['final_tick']:>9,} {ext:>9} "
                      f"{s['peak_pop']:>8,} {s['pop_half']:>8,} {s['final_pop']:>8,} "
                      f"{s['trend']:>5} {s['uptake']:>12,.0f} {s['use_rate']:>7.3f} "
                      f"{s['stock_mean']:>10,.1f} {s['vent_frac_last']:>8.3f} "
                      f"{s['chem_abs_max']:>12.3f}")

    # --- B の進化bootstrap ---
    if ("b_ancestor_vent" in conds):
        print("\n=== B: chemical_absorption 到達マイルストーン "
              "(到達seed数 / 初回tick中央値) ===")
        print("  0.9 は祖先の黒字化ライン (維持費 0.320+0.04x vs 吸収 0.40x)。")
        print("  初期値0.3の約3倍であり、Bの絶滅はsource flux不足の証拠にならない。")
        print(f"{'flux':>5} " + " ".join(f"{'>='+str(m):>16}" for m in MILESTONES))
        for f in fluxes:
            v = data.get((f, "b_ancestor_vent"), [])
            cells = []
            for m in MILESTONES:
                hits = [s["milestones"][m] for s in v if s["milestones"][m] is not None]
                med = sorted(hits)[len(hits)//2] if hits else None
                cells.append(f"{f'{len(hits)}/{len(v)}' + (f' @{med:,}' if med else ''):>16}")
            print(f"{f:>5} " + " ".join(cells))

    # --- D の空間access ---
    if ("d_chem_random" in conds):
        print("\n=== D: vent滞在率 (random配置からventへ定着できたか) ===")
        print(f"{'flux':>5} {'最終vent滞在 中央値':>22} {'最大':>8} {'生存':>8}")
        for f in fluxes:
            v = data.get((f, "d_chem_random"), [])
            if not v:
                continue
            vals = sorted(s["vent_frac_last"] for s in v)
            med = vals[len(vals)//2]
            surv = sum(1 for s in v if not s["extinct"] and not s["halted"])
            print(f"{f:>5} {med:>22.3f} {max(vals):>8.3f} {surv:>4}/{len(v):<3}")

    # --- 段階判定の候補 ---
    print("\n" + "=" * 60)
    print("§9 判定 (機械的な当てはめ。結論と次の1軸は人が決める)")

    def surv_of(f, c):
        v = data.get((f, c))
        return (sum(1 for s in v if not s["extinct"] and not s["halted"]), len(v)) if v else None

    c_ok = [f for f in fluxes if (r := surv_of(f, "c_chem_vent")) and r[0] > r[1] // 2]
    if not c_ok:
        print("  段階1: Cが過半数生存するfluxが無い。V1.3 sourceモデルでも")
        print("         chemical nicheが成立しない → uptake/生理/founder密度を再監査")
    else:
        print(f"  段階1: Cが過半数生存する flux = {c_ok} (最小 {min(c_ok)})")
        thin = [f for f in c_ok
                if sorted(s["final_pop"] for s in data[(f, "c_chem_vent")])[
                    len(data[(f, "c_chem_vent")]) // 2] < 20]
        if thin:
            print(f"    ※ flux {thin} は最終個体数の中央値が20未満。"
                  "生存とせず崩壊途中として扱うか要判断")
        for f in c_ok:
            b, d = surv_of(f, "b_ancestor_vent"), surv_of(f, "d_chem_random")
            note = []
            if b:
                note.append(f"B {b[0]}/{b[1]}" + ("" if b[0] else " → 進化bootstrapが障害"))
            if d:
                note.append(f"D {d[0]}/{d[1]}" + ("" if d[0] else " → 空間accessが障害"))
            print(f"    flux {f}: " + " / ".join(note))
    halts = [(f, c) for (f, c), v in data.items() if any(s["halted"] for s in v)]
    if halts:
        print(f"  max_population_halt 到達: {sorted(halts)} → 供給過多側の科学結果")
    return 0


if __name__ == "__main__":
    sys.exit(main())
