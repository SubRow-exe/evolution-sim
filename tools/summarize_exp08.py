"""Exp08 校正結果の要約 (docs/Exp08_実験計画.md §4.5, §5.3, §8)。

    uv run python tools/summarize_exp08.py runs/exp08 --ticks 60000

Exp08は光とchemicalの優劣を決める実験ではない。V1.4吸収則が意図どおり働くか、
恒久default候補 (`light_uptake_coef` / `chem_vent_flux`) を絞れるかを見る。

出力の順序は計画と同じ:

  Phase A: L0 を `light_uptake_coef` 順に並べ、収支差が出るかを見る
           L2 (完成光型 positive control) を並記
  Phase B: `chem_vent_flux` 8/16/24 の population / 利用率 / stock / vent滞在

V1.4では未利用光が増え、光利用率がV1.3以前より大幅に下がる。これは
低能力個体が使えない光を捨てる新仕様の意図した結果であり、異常ではない。

出力は機械的な整理であり、結論と恒久defaultは人が決める。
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

A_RE = re.compile(r"^a_(l0|l2)_coef(\d+p\d+)$")
B_RE = re.compile(r"^b_flux(\d+)_chem$")
BANDS = ("north", "middle", "south")


def rows_of(run: Path) -> list[dict]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(row: dict, key: str) -> float:
    v = row.get(key, "")
    return float(v) if v not in ("", None) else float("nan")


def _trend(pops: list[tuple[int, int]], want_ticks: int) -> tuple[str, int, int]:
    final_tick, final_pop = pops[-1]
    half = want_ticks // 2
    pop_half = next((p for t, p in pops if t >= half), 0)
    if final_pop == 0:
        return "絶滅", pop_half, final_pop
    if final_tick < want_ticks:
        return "halt", pop_half, final_pop
    if pop_half == 0:
        return "-", pop_half, final_pop
    if final_pop > pop_half * 1.1:
        return "増加", pop_half, final_pop
    if final_pop < pop_half * 0.9:
        return "減少", pop_half, final_pop
    return "維持", pop_half, final_pop


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
    peak_tick, peak_pop = (max(alive, key=lambda tp: (tp[1], -tp[0]))
                           if alive else (0, 0))
    trend, pop_half, _ = _trend(pops, want_ticks)

    supply = num(last, "light_supply_cum")
    light = num(last, "flow_light_cum")
    chem = num(last, "flow_chemical_cum")
    use_rate = light / supply if supply > 0 else float("nan")

    # chemical収支 (V1.3と同じく台帳の恒等式から環境損失を導く)
    source_per_tick = cfg["n_vents"] * cfg["chem_vent_flux"]
    influx = source_per_tick * final_tick
    stock0 = num(rows[0], "chemical_total")
    stock1 = num(last, "chemical_total")
    chem_loss = influx - chem - (stock1 - stock0)
    chem_use = chem / influx if influx > 0 else float("nan")

    live = [r for r in rows if r["population"] != "0"]
    per_org_light = (light / final_tick / final_pop) if final_pop else float("nan")
    per_org_chem = (chem / final_tick / final_pop) if final_pop else float("nan")
    stock_mean = (sum(num(r, "chemical_total") for r in rows) / len(rows)
                  if rows else 0.0)
    biomass = num(last, "total_biomass")
    mean_matter = biomass / final_pop if final_pop else float("nan")
    bands = {b: num(last, f"frac_{b}_band") for b in BANDS}

    return {
        "seed": int(run.name.split("seed")[-1]),
        "coef": cfg["light_uptake_coef"], "flux": cfg["chem_vent_flux"],
        "final_tick": final_tick, "extinct": extinct, "ext_tick": ext_tick,
        "halted": halted, "peak_pop": peak_pop, "peak_tick": peak_tick,
        "pop_half": pop_half, "final_pop": final_pop, "trend": trend,
        "biomass": biomass, "mean_matter": mean_matter,
        "light": light, "supply": supply, "use_rate": use_rate,
        "unused": supply - light, "per_org_light": per_org_light,
        "chem": chem, "chem_use": chem_use, "chem_loss": chem_loss,
        "per_org_chem": per_org_chem,
        "stock_mean": stock_mean, "stock_final": stock1,
        "vent_frac_last": num(last, "vent_cell_frac"),
        "mean_body": num(last, "mean_body_size"),
        "mean_local_light": num(last, "mean_local_light"),
        "bands": bands,
        "n_lineages": num(last, "n_lineages"),
        "live_rows": len(live),
    }


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    return s[len(s) // 2] if s else float("nan")


def _surv(v: list[dict]) -> tuple[int, int]:
    return sum(1 for s in v if not s["extinct"] and not s["halted"]), len(v)


def print_phase_a(data: dict, want_ticks: int) -> None:
    l0 = {k[1]: v for k, v in data.items() if k[0] == "l0"}
    l2 = {k[1]: v for k, v in data.items() if k[0] == "l2"}
    if not l0 and not l2:
        return

    print("=== Phase A 生存率 (指定tickまで絶滅もhaltもしなかったrun / 全run) ===")
    print(f"{'coef':>6} {'L0':>10} {'L2':>10}")
    for coef in sorted(set(l0) | set(l2)):
        cells = []
        for group in (l0, l2):
            v = group.get(coef)
            if not v:
                cells.append(f"{'-':>10}")
                continue
            surv, total = _surv(v)
            halt = sum(1 for s in v if s["halted"])
            mark = f"{surv}/{total}" + (f" (halt{halt})" if halt else "")
            cells.append(f"{mark:>10}")
        print(f"{coef:>6.1f} " + " ".join(cells))

    for label, group in (("L0 — 祖先 light_absorption=0.3固定", l0),
                         ("L2 — 完成光型 light_absorption=2.0固定", l2)):
        if not group:
            continue
        print(f"\n===== {label} =====")
        print(f"{'coef':>6} {'seed':>5} {'最終tick':>9} {'絶滅tick':>9} {'ピーク':>8} "
              f"{'中間':>8} {'最終':>8} {'推移':>5} {'biomass':>9} {'平均matter':>10} "
              f"{'光利用率':>8} {'個体光/tick':>11} {'body_size':>9} "
              f"{'north':>6} {'middle':>6} {'south':>6}")
        for coef in sorted(group):
            for s in group[coef]:
                ext = (format(s["ext_tick"], ",") if s["ext_tick"] is not None
                       else "-")
                b = s["bands"]
                print(f"{coef:>6.1f} {s['seed']:>5} {s['final_tick']:>9,} {ext:>9} "
                      f"{s['peak_pop']:>8,} {s['pop_half']:>8,} "
                      f"{s['final_pop']:>8,} {s['trend']:>5} {s['biomass']:>9.1f} "
                      f"{s['mean_matter']:>10.3f} {s['use_rate']:>8.4f} "
                      f"{s['per_org_light']:>11.4f} {s['mean_body']:>9.3f} "
                      f"{b['north']:>6.2f} {b['middle']:>6.2f} {b['south']:>6.2f}")

    print("\n=== Phase A 係数別サマリ (中央値) ===")
    print(f"{'cond':>4} {'coef':>6} {'生存':>8} {'最終pop':>9} {'光利用率':>9} "
          f"{'未利用光累計':>14} {'個体光/tick':>11} {'平均matter':>10}")
    for name, group in (("L0", l0), ("L2", l2)):
        for coef in sorted(group):
            v = group[coef]
            surv, total = _surv(v)
            print(f"{name:>4} {coef:>6.1f} {f'{surv}/{total}':>8} "
                  f"{_median([s['final_pop'] for s in v]):>9,.0f} "
                  f"{_median([s['use_rate'] for s in v]):>9.4f} "
                  f"{_median([s['unused'] for s in v]):>14,.0f} "
                  f"{_median([s['per_org_light'] for s in v]):>11.4f} "
                  f"{_median([s['mean_matter'] for s in v]):>10.3f}")
    print("\n  ※ V1.4では未利用光が増えて光利用率が下がる。これは新吸収則の"
          "意図した結果であり異常ではない (計画 §4.5)。")
    print("  ※ break-even近傍の係数は世代時間が長い。生存/絶滅の二値ではなく"
          "推移欄と中間tickの人口で読む。")


def print_phase_b(data: dict) -> None:
    if not data:
        return
    print("\n=== Phase B 生存率 (chemical単独 / chemical_absorption=2.0固定) ===")
    print(f"{'flux':>5} {'世界source':>10} {'生存':>8}")
    for flux in sorted(data):
        surv, total = _surv(data[flux])
        print(f"{flux:>5} {flux * 4:>10} {f'{surv}/{total}':>8}")

    print("\n===== Phase B 各run =====")
    print(f"{'flux':>5} {'seed':>5} {'最終tick':>9} {'絶滅tick':>9} {'ピーク':>8} "
          f"{'中間':>8} {'最終':>8} {'推移':>5} {'uptake':>12} {'利用率':>7} "
          f"{'環境損失':>12} {'平均stock':>10} {'vent滞在':>8} {'個体chem/tick':>13} "
          f"{'平均matter':>10}")
    for flux in sorted(data):
        for s in data[flux]:
            ext = format(s["ext_tick"], ",") if s["ext_tick"] is not None else "-"
            print(f"{flux:>5} {s['seed']:>5} {s['final_tick']:>9,} {ext:>9} "
                  f"{s['peak_pop']:>8,} {s['pop_half']:>8,} {s['final_pop']:>8,} "
                  f"{s['trend']:>5} {s['chem']:>12,.0f} {s['chem_use']:>7.3f} "
                  f"{s['chem_loss']:>12,.0f} {s['stock_mean']:>10,.1f} "
                  f"{s['vent_frac_last']:>8.3f} {s['per_org_chem']:>13.4f} "
                  f"{s['mean_matter']:>10.3f}")

    print("\n=== Phase B flux別サマリ (中央値) ===")
    print(f"{'flux':>5} {'生存':>8} {'最終pop':>9} {'利用率':>8} {'平均stock':>10} "
          f"{'vent滞在':>9} {'個体chem/tick':>13}")
    for flux in sorted(data):
        v = data[flux]
        surv, total = _surv(v)
        print(f"{flux:>5} {f'{surv}/{total}':>8} "
              f"{_median([s['final_pop'] for s in v]):>9,.0f} "
              f"{_median([s['chem_use'] for s in v]):>8.3f} "
              f"{_median([s['stock_mean'] for s in v]):>10,.1f} "
              f"{_median([s['vent_frac_last'] for s in v]):>9.3f} "
              f"{_median([s['per_org_chem'] for s in v]):>13.4f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp08 校正結果の要約")
    ap.add_argument("exp_dir")
    ap.add_argument("--ticks", type=int, default=60000)
    args = ap.parse_args()

    base = Path(args.exp_dir)
    phase_a: dict[tuple[str, float], list[dict]] = {}
    phase_b: dict[int, list[dict]] = {}

    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        runs = sorted(r for r in d.iterdir()
                      if r.is_dir() and (r / "stats.csv").exists())
        if not runs:
            continue
        summaries = sorted((summarize_run(r, args.ticks) for r in runs),
                           key=lambda s: s["seed"])
        ma = A_RE.match(d.name)
        mb = B_RE.match(d.name)
        if ma:
            phase_a[(ma.group(1), float(ma.group(2).replace("p", ".")))] = summaries
        elif mb:
            phase_b[int(mb.group(1))] = summaries

    bad_chem = [(k, s["seed"]) for k, v in phase_a.items() for s in v
                if s["chem"] != 0.0]
    if bad_chem:
        print(f"★ Phase A で chemical flow が0でないrun: {bad_chem}\n")
    bad_light = [(k, s["seed"]) for k, v in phase_b.items() for s in v
                 if s["light"] != 0.0]
    if bad_light:
        print(f"★ Phase B で light flow が0でないrun: {bad_light}\n")

    print_phase_a(phase_a, args.ticks)
    print_phase_b(phase_b)

    print("\n" + "=" * 60)
    print("判定材料 (計画 §8。結論と恒久defaultは人が決める)")
    l0 = {c: v for (k, c), v in phase_a.items() if k == "l0"}
    l2 = {c: v for (k, c), v in phase_a.items() if k == "l2"}
    if l0:
        rates = {c: _surv(v)[0] for c, v in l0.items()}
        pops = {c: _median([s["final_pop"] for s in v]) for c, v in l0.items()}
        print(f"  L0 生存 seed数: " + " / ".join(
            f"coef {c:g}: {rates[c]}/{len(l0[c])}" for c in sorted(l0)))
        print(f"  L0 最終pop中央値: " + " / ".join(
            f"coef {c:g}: {pops[c]:,.0f}" for c in sorted(l0)))
        if len(l0) >= 2:
            spread = max(pops.values()) - min(pops.values())
            print(f"  → 係数によるpopulation差 {spread:,.0f} "
                  f"({'係数が効いている' if spread > 0 else '係数にほぼ非感受'})")
        else:
            print("  → 係数水準が1つしかないため感受性は判定しない")
    if l2:
        for c, v in sorted(l2.items()):
            surv, total = _surv(v)
            print(f"  L2 positive control (coef {c:g}): {surv}/{total} 生存")
    if phase_b:
        print("  Phase B: " + " / ".join(
            f"flux {f}: {_surv(v)[0]}/{len(v)}" for f, v in sorted(phase_b.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
