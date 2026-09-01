"""Exp10 Phase B の要約と最終Green判定 (docs/Exp10_実験計画案.md §5, §8)。

    uv run python tools/summarize_exp10_phaseB.py runs/exp10 --ticks 10000

Phase Bは「Phase Aで選ばれた1候補を通常simulationへ持ち込み、生態を
壊さないこと」を見る。行動則の局所的な正しさはPhase Aが担当する。

## 実行失敗 と 科学的判定 の分離 (Issue #41 再トライアル方針 §6)

このツールの終了コードは **整合性 (integrity)** だけで決める。
実験が正常に完走したうえでの科学的な STOP/REVIEW は workflow failure に
しない (絶滅・低populationは測定結果であり、実行の失敗ではない)。

- **整合性違反 → 非ゼロ終了 (workflow failure)**
  - §8-7: 供給側の物理が control/treatment で食い違う (吸収・Energy/Matter
    物理が行動則で壊れていないことの確認。壊れていればデータの意味が無い)

- **科学的判定 → 終了コード0のまま報告 (STOP / REVIEW)**
  - **重要停止条件 STOP (§5.5)**: B2 chemical-only の treatment で
    20 seed中18 seed以上が10,000 tickまで生存すること。満たさなければ
    V1.6 default化を止める「科学的な」判断材料になる (実行の失敗ではない)。
  - **REVIEW (§8-3)**: 単一刺激gradient (B1/B2) でrandomより高Q領域へ偏るか
  - **REVIEW (§8-4)**: B5 mixed generalist が両刺激の寄与を受けるか

改善は seed対応で 80%以上 かつ 中央値 +5 percentage points 以上とする。

`--cases` を渡すと、そのバッチで走らせた条件だけを判定対象にする
(40 run分割実行で未実行の条件を「判定不能」ではなく N/A として扱う)。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_exp10_configs import CONDITIONS, RULES  # noqa: E402

BANDS = ("d0_1", "d1_2", "d2_4", "d4plus")
SEED_FRAC = 0.80
DELTA_HI_Q_PP = 5.0
SURVIVE_MIN = 18          # §5.5: 20 seed中18以上
SURVIVE_OF = 20


def num(row: dict, key: str) -> float:
    v = row.get(key, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rows_of(run: Path) -> list[dict]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize_run(run: Path, want_ticks: int) -> dict:
    rows = rows_of(run)
    last = rows[-1]
    final_tick = int(last["tick"])
    final_pop = int(last["population"])

    def wmean(key: str, wkey: str) -> float:
        n = d = 0.0
        for r in rows:
            w = num(r, wkey)
            v = num(r, key)
            if w > 0 and not math.isnan(v):
                n += w * v
                d += w
        return n / d if d else float("nan")

    def total(key: str) -> float:
        return sum(v for v in (num(r, key) for r in rows) if not math.isnan(v))

    out = {
        "seed": int(run.name.split("seed")[-1]),
        "final_tick": final_tick, "final_pop": final_pop,
        "survived": final_pop > 0 and final_tick >= want_ticks,
        "hi_q_frac": st.mean([num(r, "hi_q_frac") for r in rows]),
        "hi_q_final": num(last, "hi_q_frac"),
        "vent_frac": st.mean([num(r, "vent_cell_frac") for r in rows]),
        "move": st.mean([num(r, "mean_move_per_org_tick") for r in rows
                         if not math.isnan(num(r, "mean_move_per_org_tick"))]),
        "q": wmean("q_mean", "stim_events"),
        "dq_abs": wmean("dq_abs_mean", "stim_events"),
        "dq_light": wmean("dq_light_mean", "stim_events"),
        "dq_chem": wmean("dq_chem_mean", "stim_events"),
        "sigma_eff": wmean("sigma_eff_mean", "stim_events"),
        "turn_factor": wmean("turn_factor_mean", "stim_events"),
        "light_flow": num(last, "flow_light_cum"),
        "chem_flow": num(last, "flow_chemical_cum"),
        "light_supply": num(last, "light_supply_cum"),
        "north": num(last, "frac_north_band"),
    }
    for b in BANDS:
        n = total(f"band_{b}_n")
        out[f"band_{b}_n"] = n
        out[f"band_{b}_light_e"] = total(f"band_{b}_light_e")
        out[f"band_{b}_chem_e"] = total(f"band_{b}_chem_e")
        out[f"band_{b}_sigma"] = wmean(f"band_{b}_sigma_eff", f"band_{b}_n")
        out[f"band_{b}_dq_chem"] = wmean(f"band_{b}_dq_chem", f"band_{b}_n")
    tot_n = sum(out[f"band_{b}_n"] for b in BANDS)
    for b in BANDS:
        out[f"band_{b}_frac"] = (out[f"band_{b}_n"] / tot_n) if tot_n else 0.0
    return out


def load(base: Path, want_ticks: int) -> dict[str, list[dict]]:
    names = [f"{c}_{r}" for c in CONDITIONS for r in RULES]
    data: dict[str, list[dict]] = {}
    for d in sorted(x for x in base.iterdir() if x.is_dir() and x.name in names):
        runs = [r for r in sorted(d.iterdir())
                if r.is_dir() and (r / "stats.csv").exists()]
        if runs:
            data[d.name] = sorted((summarize_run(r, want_ticks) for r in runs),
                                  key=lambda s: s["seed"])
    return data


def paired(treat: list[dict], ctrl: list[dict], key: str) -> list[float]:
    cmap = {r["seed"]: r[key] for r in ctrl}
    return [r[key] - cmap[r["seed"]] for r in treat if r["seed"] in cmap]


def med(v: list[float]) -> float:
    v = [x for x in v if not math.isnan(x)]
    return st.median(v) if v else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp10 Phase B の要約と判定")
    ap.add_argument("exp_dir")
    ap.add_argument("--ticks", type=int, default=10000)
    ap.add_argument("--cases", default="",
                    help="このバッチで走らせた条件 (カンマ区切り。省略で全10条件)")
    args = ap.parse_args()

    base = Path(args.exp_dir)
    data = load(base, args.ticks)
    if not data:
        print(f"★ {base} に Exp10 Phase B の run が無い")
        return 1

    all_names = [f"{c}_{r}" for c in CONDITIONS for r in RULES]
    expected = ([c.strip() for c in args.cases.split(",") if c.strip()]
                if args.cases else all_names)
    na = [n for n in expected if n not in data]
    if na:
        print(f"（このバッチ外 / N/A: {', '.join(sorted(na))}）\n")

    # 整合性違反 (→ 非ゼロ終了) と 科学的判定 (STOP/REVIEW、→ 終了コード0) を分ける
    integrity_fails: list[str] = []
    science_stop: list[str] = []
    science_review: list[str] = []

    # --- 重要停止条件 (§5.5): 科学的 STOP ---
    print("=== 重要停止条件 (§5.5): chemical-only treatment の生存 ===")
    key = "b2_chem_only_chemspec_treatment"
    if key in data:
        surv = sum(1 for s in data[key] if s["survived"])
        n = len(data[key])
        ok = surv >= SURVIVE_MIN
        print(f"  {key}: {surv}/{n} seed が {args.ticks:,} tick まで生存 "
              f"(必要 {SURVIVE_MIN}/{SURVIVE_OF})  → {'OK' if ok else 'STOP'}")
        if not ok:
            science_stop.append(f"§5.5 chemical-only生存 {surv}/{n} (必要 "
                                f"{SURVIVE_MIN}/{SURVIVE_OF})")
    else:
        print(f"  N/A ({key} はこのバッチ外)")

    # --- 生存とpopulation ---
    print("\n=== 条件別サマリ (seed中央値) ===")
    print(f"{'条件':<38}{'生存':>7}{'最終pop':>9}{'hi_q':>8}{'vent':>7}"
          f"{'移動':>9}{'|dQ|':>10}{'sigma':>8}{'light flow':>12}{'chem flow':>11}")
    for name in [f"{c}_{r}" for c in CONDITIONS for r in RULES]:
        if name not in data:
            continue
        v = data[name]
        print(f"{name:<38}{sum(s['survived'] for s in v):>4}/{len(v):<2}"
              f"{med([s['final_pop'] for s in v]):>9,.0f}"
              f"{med([s['hi_q_frac'] for s in v]):>8.4f}"
              f"{med([s['vent_frac'] for s in v]):>7.3f}"
              f"{med([s['move'] for s in v]):>9.4f}"
              f"{med([s['dq_abs'] for s in v]):>10.2e}"
              f"{med([s['sigma_eff'] for s in v]):>8.4f}"
              f"{med([s['light_flow'] for s in v]):>12,.0f}"
              f"{med([s['chem_flow'] for s in v]):>11,.0f}")

    # --- §8-3: high-Q滞在率の改善 ---
    print("\n=== §8-3: treatment は control より high-Q領域へ偏るか ===")
    print(f"{'条件':<28}{'改善seed率':>11}{'改善量中央値[pp]':>18}{'判定':>7}")
    for c in CONDITIONS:
        t, ctl = f"{c}_treatment", f"{c}_control"
        if t not in data or ctl not in data:
            continue
        d = paired(data[t], data[ctl], "hi_q_frac")
        frac = sum(1 for x in d if x > 0) / len(d) if d else 0.0
        pp = med(d) * 100.0
        ok = frac >= SEED_FRAC and pp >= DELTA_HI_Q_PP
        print(f"{c:<28}{frac:>11.2f}{pp:>18.2f}{'OK' if ok else 'REVIEW':>7}")
        if c in ("b1_light_only_lightspec", "b2_chem_only_chemspec") and not ok:
            science_review.append(f"§8-3 {c} の high-Q改善")

    # --- §8-4: 混合generalist が両刺激の寄与を受けるか ---
    print("\n=== §8-4: mixed generalist の dQ 寄与分解 ===")
    for name in ("b5_mixed_generalist_control", "b5_mixed_generalist_treatment"):
        if name not in data:
            continue
        v = data[name]
        dl, dc = med([s["dq_light"] for s in v]), med([s["dq_chem"] for s in v])
        print(f"  {name:<40} dQ_light={dl:+.3e}  dQ_chem={dc:+.3e}")
    t = data.get("b5_mixed_generalist_treatment", [])
    if t:
        both = sum(1 for s in t
                   if abs(s["dq_light"]) > 0 and abs(s["dq_chem"]) > 0)
        ok = both / len(t) >= SEED_FRAC
        print(f"  両寄与が非ゼロのseed: {both}/{len(t)} → {'OK' if ok else 'REVIEW'}")
        if not ok:
            science_review.append("§8-4 generalistの両刺激統合")

    # --- vent距離帯別 (§5.4) ---
    print("\n=== vent距離帯別 (treatment, seed中央値) ===")
    print(f"{'条件':<30}{'帯':>8}{'滞在率':>9}{'sigma_eff':>11}"
          f"{'dQ_chem':>12}{'chem E':>11}{'light E':>12}")
    for c in CONDITIONS:
        name = f"{c}_treatment"
        if name not in data:
            continue
        v = data[name]
        for b in BANDS:
            print(f"{c if b == BANDS[0] else '':<30}{b:>8}"
                  f"{med([s[f'band_{b}_frac'] for s in v]):>9.4f}"
                  f"{med([s[f'band_{b}_sigma'] for s in v]):>11.4f}"
                  f"{med([s[f'band_{b}_dq_chem'] for s in v]):>12.2e}"
                  f"{med([s[f'band_{b}_chem_e'] for s in v]):>11,.0f}"
                  f"{med([s[f'band_{b}_light_e'] for s in v]):>12,.0f}")

    # --- §8-7: 供給側の物理が変わっていない ---
    print("\n=== §8-7: control と treatment で光供給が一致するか ===")
    all_ok = True
    for c in CONDITIONS:
        t, ctl = f"{c}_treatment", f"{c}_control"
        if t not in data or ctl not in data:
            continue
        a = med([s["light_supply"] for s in data[t]])
        b = med([s["light_supply"] for s in data[ctl]])
        ok = (a == b) or (math.isnan(a) and math.isnan(b))
        all_ok = all_ok and ok
        print(f"  {c:<30} treatment={a:,.0f}  control={b:,.0f} "
              f"→ {'OK' if ok else 'NG'}")
    if not all_ok:
        integrity_fails.append("§8-7 供給側の物理が control/treatment で不一致")

    # --- 判定: 整合性 (終了コード) と 科学的判定 (報告のみ) を分けて出す ---
    print("\n" + "=" * 60)
    if science_stop:
        print("科学的判定: STOP — 重要停止条件が未達 (実行の失敗ではない)")
        for s in science_stop:
            print(f"  - {s}")
    if science_review:
        print("科学的判定: REVIEW — 事前登録の改善が未確認 (要人間判断)")
        for s in science_review:
            print(f"  - {s}")
    if not science_stop and not science_review:
        print("科学的判定: PASS — Phase B の事前登録条件をすべて満たした")

    if integrity_fails:
        print(f"\n整合性: NG {len(integrity_fails)} 件 → workflow failure")
        for f in integrity_fails:
            print(f"  - {f}")
        return 1
    print("\n整合性: OK — 供給側の物理は保たれている")
    return 0


if __name__ == "__main__":
    sys.exit(main())
