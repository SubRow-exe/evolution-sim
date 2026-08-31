"""Exp10 Phase A の判定と最終候補の選定 (docs/Exp10_実験計画案.md §4.6-4.7)。

    uv run python tools/summarize_exp10.py runs/exp10_phaseA

事前登録されたGreen条件をそのまま機械的に当てる。結果を見てから閾値も
パラメータ候補も足さない (計画 §11)。

## 事前登録のGreen条件 (§4.6)

1. K0: gain>0 でも方向driftなし。gain=0との差は統計誤差内
2. K1/K2: 対応表現型でrandom controlよりhigh-Q領域滞在率が
   - 10 seed中8 seed以上で改善
   - 改善量中央値 +5 percentage points以上
3. K3 generalist: X/Yの両方向が期待符号となるseedが10中8以上
4. K4: light specialistとchemical specialistが期待する逆方向へ偏り、
   generalistは両寄与を受ける
5. Greenが単独1点ではなく、少なくとも隣接する複数パラメータ組で成立

## 本ツールで固定する運用上の定義

計画に書かれていない判定の細部はここで固定し、結果を見て変えない。

- **seed比率**: 条件は「10 seed中8以上」= **80%**。20 seedで走らせた場合も
  同じ80%を使う (16/20)。参考として先頭10 seedだけの結果も併記する。
- **統計誤差内 (条件1)**: treatmentとcontrolのdriftをWelchのt検定で比べ、
  `|t| < 2.0` を「差が統計誤差内」とする。
- **期待符号**:
  - K1 light-Y   : lightを使う表現型は +Y (drift_y > 0)
  - K2 chemical-X: chemicalを使う表現型は +X (drift_x > 0)
  - K3 orthogonal: generalist は +X かつ +Y
  - K4 conflict  : lightspec は +Y、chemspec は -Y
- **隣接 (条件5)**: `memory_taus` / `response_gains` の候補列で添字が1違う組。

## 最終候補の選び方 (§4.7)

Green領域の中から
  1. 最小 response_gain
  2. 同gainなら最短 memory_tau
の順で1組だけ選ぶ。「効く中で最も弱い変更」を採る。
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

from tools.arena_exp10 import (CONTROL_GAIN, MEMORY_TAUS,  # noqa: E402
                               RESPONSE_GAINS)

SEED_FRAC = 0.80          # 「10 seed中8以上」= 80%
DELTA_HI_Q_PP = 5.0       # 改善量中央値の下限 [percentage points]
T_CRIT = 2.0              # 条件1「統計誤差内」の判定


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("seed", "ticks", "n_org", "dq_pos", "dq_neg", "dq_zero"):
            r[k] = int(float(r[k]))
        for k, v in r.items():
            if k in ("env", "phenotype") or isinstance(v, int):
                continue
            r[k] = float(v)
    return rows


def pick(rows, env=None, pheno=None, tau=None, gain=None) -> list[dict]:
    out = rows
    if env is not None:
        out = [r for r in out if r["env"] == env]
    if pheno is not None:
        out = [r for r in out if r["phenotype"] == pheno]
    if tau is not None:
        out = [r for r in out if r["memory_tau"] == tau]
    if gain is not None:
        out = [r for r in out if r["response_gain"] == gain]
    return sorted(out, key=lambda r: r["seed"])


def welch_t(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    if se == 0.0:
        return 0.0
    return (st.mean(a) - st.mean(b)) / se


def _paired(treat: list[dict], ctrl: list[dict], key: str) -> list[float]:
    """seedで対応づけた差 (treatment - control)。"""
    cmap = {r["seed"]: r[key] for r in ctrl}
    return [r[key] - cmap[r["seed"]] for r in treat if r["seed"] in cmap]


def _frac_ok(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def evaluate(rows: list[dict], seeds_limit: int | None = None) -> dict:
    """(tau, gain) ごとに条件1-4の成否を返す。"""
    if seeds_limit:
        rows = [r for r in rows if r["seed"] <= seeds_limit]
    result: dict[tuple[float, float], dict] = {}
    for tau in MEMORY_TAUS:
        for gain in RESPONSE_GAINS:
            checks: dict[str, object] = {}

            # --- 条件1: K0 で偽driftが出ない ---
            c1_ok = True
            c1_detail = []
            for pheno in ("lightspec", "chemspec", "generalist"):
                t = pick(rows, "K0_uniform", pheno, tau, gain)
                c = pick(rows, "K0_uniform", pheno, MEMORY_TAUS[0], CONTROL_GAIN)
                for axis in ("drift_x", "drift_y"):
                    tt = welch_t([r[axis] for r in t], [r[axis] for r in c])
                    ok = (not math.isnan(tt)) and abs(tt) < T_CRIT
                    c1_ok = c1_ok and ok
                    c1_detail.append((pheno, axis, round(tt, 3), ok))
            checks["c1_K0_no_false_drift"] = c1_ok
            checks["c1_detail"] = c1_detail

            # --- 条件2: K1/K2 で対応表現型のhigh-Q滞在率が改善 ---
            c2_ok = True
            c2_detail = []
            for env, pheno in (("K1_light_Y", "lightspec"),
                               ("K2_chem_X", "chemspec")):
                t = pick(rows, env, pheno, tau, gain)
                c = pick(rows, env, pheno, MEMORY_TAUS[0], CONTROL_GAIN)
                d = _paired(t, c, "hi_q_frac")
                frac = _frac_ok([x > 0 for x in d])
                med_pp = st.median(d) * 100.0 if d else float("nan")
                ok = frac >= SEED_FRAC and med_pp >= DELTA_HI_Q_PP
                c2_ok = c2_ok and ok
                c2_detail.append((env, pheno, round(frac, 3),
                                  round(med_pp, 2), ok))
            checks["c2_gradient_improves_hi_q"] = c2_ok
            checks["c2_detail"] = c2_detail

            # --- 条件3: K3 generalist が X/Y 両方向で期待符号 ---
            t = pick(rows, "K3_orthogonal", "generalist", tau, gain)
            flags = [r["drift_x"] > 0 and r["drift_y"] > 0 for r in t]
            c3_frac = _frac_ok(flags)
            checks["c3_K3_generalist_both_axes"] = c3_frac >= SEED_FRAC
            checks["c3_frac"] = round(c3_frac, 3)

            # --- 条件4: K4 で specialist が逆向き / generalist が両寄与 ---
            tl = pick(rows, "K4_conflict", "lightspec", tau, gain)
            tc = pick(rows, "K4_conflict", "chemspec", tau, gain)
            tg = pick(rows, "K4_conflict", "generalist", tau, gain)
            f_l = _frac_ok([r["drift_y"] > 0 for r in tl])
            f_c = _frac_ok([r["drift_y"] < 0 for r in tc])
            gen_both = _frac_ok([abs(r["dq_light_mean"]) > 0.0
                                 and abs(r["dq_chem_mean"]) > 0.0 for r in tg])
            checks["c4_K4_opposite_and_integrated"] = (
                f_l >= SEED_FRAC and f_c >= SEED_FRAC and gen_both >= SEED_FRAC)
            checks["c4_frac"] = (round(f_l, 3), round(f_c, 3), round(gen_both, 3))

            checks["green"] = bool(checks["c1_K0_no_false_drift"]
                                   and checks["c2_gradient_improves_hi_q"]
                                   and checks["c3_K3_generalist_both_axes"]
                                   and checks["c4_K4_opposite_and_integrated"])
            result[(tau, gain)] = checks
    return result


def adjacent(a: tuple[float, float], b: tuple[float, float]) -> bool:
    ti, tj = MEMORY_TAUS.index(a[0]), MEMORY_TAUS.index(b[0])
    gi, gj = RESPONSE_GAINS.index(a[1]), RESPONSE_GAINS.index(b[1])
    return abs(ti - tj) + abs(gi - gj) == 1


def select(result: dict) -> tuple[tuple[float, float] | None, bool, list]:
    """Green組から最終候補を選ぶ。(候補, 条件5成立, Green組一覧)"""
    green = sorted(k for k, v in result.items() if v["green"])
    has_neighbor = any(adjacent(a, b) for i, a in enumerate(green)
                       for b in green[i + 1:])
    if not green or not has_neighbor:
        return None, has_neighbor, green
    # §4.7: 最小 response_gain → 同gainなら最短 memory_tau
    best = min(green, key=lambda k: (k[1], k[0]))
    return best, has_neighbor, green


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp10 Phase A の判定と候補選定")
    ap.add_argument("phase_a_dir")
    ap.add_argument("--write-selection", action="store_true",
                    help="phaseA_selection.json を書き出す")
    args = ap.parse_args()

    base = Path(args.phase_a_dir)
    rows = load(base / "phaseA.csv")
    meta = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    seeds = sorted({r["seed"] for r in rows})
    print(f"Phase A: {len(rows):,} run / {len(seeds)} seed / "
          f"{meta['ticks']:,} tick / {meta['n_org']} 個体")
    print(f"判定: seed比率 {SEED_FRAC:.0%} 以上 / high-Q改善量中央値 "
          f"{DELTA_HI_Q_PP:+.0f} pp 以上 / K0のWelch |t| < {T_CRIT}")

    # --- 参考: 環境×表現型ごとのhigh-Q滞在率 (gain別) ---
    print("\n=== high-Q領域滞在率 (中央値。tau=10固定) ===")
    print(f"{'env':<16}{'phenotype':<12}" +
          "".join(f"{'g=' + str(int(g)):>9}" for g in (CONTROL_GAIN,) + RESPONSE_GAINS))
    for env in meta["environments"]:
        for pheno in meta["phenotypes"]:
            line = f"{env:<16}{pheno:<12}"
            for g in (CONTROL_GAIN,) + RESPONSE_GAINS:
                tau = MEMORY_TAUS[0] if g == CONTROL_GAIN else 10.0
                v = [r["hi_q_frac"] for r in pick(rows, env, pheno, tau, g)]
                line += f"{st.median(v):>9.4f}" if v else f"{'-':>9}"
            print(line)

    print("\n=== 集団重心drift [cell] (中央値。tau=10固定) ===")
    print(f"{'env':<16}{'phenotype':<12}{'axis':>6}" +
          "".join(f"{'g=' + str(int(g)):>9}" for g in (CONTROL_GAIN,) + RESPONSE_GAINS))
    for env in meta["environments"]:
        for pheno in meta["phenotypes"]:
            for axis in ("drift_x", "drift_y"):
                line = f"{env:<16}{pheno:<12}{axis[-1]:>6}"
                for g in (CONTROL_GAIN,) + RESPONSE_GAINS:
                    tau = MEMORY_TAUS[0] if g == CONTROL_GAIN else 10.0
                    v = [r[axis] for r in pick(rows, env, pheno, tau, g)]
                    line += f"{st.median(v):>9.2f}" if v else f"{'-':>9}"
                print(line)

    # --- Green判定 ---
    result = evaluate(rows)
    print("\n=== 事前登録Green条件の判定 (全seed) ===")
    print(f"{'tau':>6}{'gain':>7}  {'C1 K0':>6}{'C2 grad':>8}{'C3 K3':>7}"
          f"{'C4 K4':>7}   {'Green':>6}   詳細(C2: 改善seed率 / 改善量中央値pp)")
    for tau in MEMORY_TAUS:
        for gain in RESPONSE_GAINS:
            v = result[(tau, gain)]
            c2 = " ".join(f"{e.split('_')[0]}:{f:.2f}/{p:+.1f}"
                          for e, _, f, p, _ in v["c2_detail"])
            print(f"{tau:>6.0f}{gain:>7.0f}  "
                  f"{'OK' if v['c1_K0_no_false_drift'] else 'NG':>6}"
                  f"{'OK' if v['c2_gradient_improves_hi_q'] else 'NG':>8}"
                  f"{'OK' if v['c3_K3_generalist_both_axes'] else 'NG':>7}"
                  f"{'OK' if v['c4_K4_opposite_and_integrated'] else 'NG':>7}"
                  f"   {'GREEN' if v['green'] else '-':>6}   {c2}")

    best, has_neighbor, green = select(result)
    print(f"\nGreen組: {len(green)} / {len(MEMORY_TAUS) * len(RESPONSE_GAINS)}")
    print(f"条件5 (隣接する複数組で成立): {'OK' if has_neighbor else 'NG'}")

    if len(seeds) >= 10:
        r10 = evaluate(rows, seeds_limit=10)
        g10 = sorted(k for k, v in r10.items() if v["green"])
        print(f"参考 (先頭10 seedのみ): Green組 {len(g10)} → {g10}")

    if best is None:
        print("\n★ Phase A Green条件を満たす組が無い (または単独1点のみ)。")
        print("  計画 §4.6-5 によりPhase Bへ進まない。")
        return 1

    print(f"\n=== 最終候補 (§4.7: 最小gain → 最短tau) ===")
    print(f"  memory_tau    = {best[0]:g}")
    print(f"  response_gain = {best[1]:g}")

    if args.write_selection:
        sel = {"memory_tau": best[0], "response_gain": best[1],
               "green_combos": [[t, g] for t, g in green],
               "adjacent_green": has_neighbor,
               "seed_frac": SEED_FRAC, "delta_hi_q_pp": DELTA_HI_Q_PP,
               "t_crit": T_CRIT, "n_seeds": len(seeds),
               "rule": "§4.7 最小response_gain → 同gainなら最短memory_tau"}
        p = base / "phaseA_selection.json"
        p.write_text(json.dumps(sel, indent=2, ensure_ascii=False),
                     encoding="utf-8")
        print(f"\n-> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
