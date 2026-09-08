"""Exp18 V1.10.1 Phase 0 — source calibration / mechanical validation.

正本: docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md §2 (P0-A..E)。
formal experimentではない。parameter sweep/tuningは行わない。

flux/temporal/turnoverのmechanical propertyそのもの (ledger厳密性・
paired-staggered恒常性・turnover制約・RNG隔離) は
tests/test_v1101_dynamic_vent.py で既に単体検証済み。ここではExp18が
実際に使うF0 (Phase0 P0-Aで実測) を使い、formal configの文脈で
同じ性質を再確認し、`F0`実測値と`vent_schedule`をExp18成果物として残す。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp18_core as core  # noqa: E402


def p0_a() -> dict:
    """legacy Dirichlet source flux measurement (docs Exp18 §2 P0-A)。"""
    result = core.measure_legacy_f0(warmup_s=6 * 3600.0, measure_s=3600.0)
    f0 = result["f0_mol_s"]
    pass_ = bool(f0 > 0.0 and np.isfinite(f0))
    return {
        "pass": pass_,
        "f0_mol_s": f0,
        "f_total_legacy_mol_s": result["f_total_legacy_mol_s"],
        "warmup_s": result["warmup_s"],
        "measure_s": result["measure_s"],
    }, result["h2_field_snapshot"]


def p0_b(f0: float, h2_field: np.ndarray) -> dict:
    """finite flux source sanity: 4 vents x F0固定供給 (docs Exp18 §2 P0-B)。"""
    cfg = core.make_flux_cfg(f0, temporal=False, turnover=False, initial_population=0)
    from evosim.world import World
    rng = np.random.Generator(np.random.PCG64(180001))
    w = World(cfg, rng)
    w.configure_flux_vents(core.LEGACY_FOUR_CENTERS)
    w.h2 = h2_field.copy()
    total_in = 0.0
    n_steps = int(round(3600.0 / cfg.dt_seconds))
    for _ in range(n_steps):
        inflow, _loss = w.update()
        total_in += inflow
    expected = f0 * len(core.LEGACY_FOUR_CENTERS) * 3600.0
    ledger_ok = abs(total_in - expected) <= 1e-9 * max(expected, 1e-30)
    nonneg = bool((w.h2 >= 0.0).all())
    finite = bool(np.isfinite(w.h2).all())
    gradient = bool(w.h2.max() > w.h2.min())
    pass_ = bool(ledger_ok and nonneg and finite and gradient)
    return {
        "pass": pass_, "source_in_mol": total_in, "expected_mol": expected,
        "ledger_relative_error": abs(total_in - expected) / max(expected, 1e-30),
        "nonnegative": nonneg, "finite": finite, "gradient_formed": gradient,
    }


def p0_c(f0: float) -> dict:
    """temporal supply equivalence: static vs 12h paired-staggered (docs Exp18 §2 P0-C)。"""
    from evosim.world import World

    def total_source(temporal: bool, on_mult: float) -> float:
        cfg = core.make_flux_cfg(f0, temporal=temporal, turnover=False, initial_population=0,
                                 h2_vent_on_flux_multiplier=on_mult)
        rng = np.random.Generator(np.random.PCG64(180002))
        w = World(cfg, rng)
        w.configure_flux_vents(core.LEGACY_FOUR_CENTERS)
        total = 0.0
        n_steps = int(round(43200.0 / cfg.dt_seconds))
        for _ in range(n_steps):
            inflow, _ = w.update()
            total += inflow
        return total

    static_total = total_source(False, 1.0)
    temporal_total = total_source(True, 2.0)
    rel_err = abs(static_total - temporal_total) / max(static_total, 1e-30)
    pass_ = bool(rel_err <= 1e-9)
    return {"pass": pass_, "static_total_mol": static_total,
           "temporal_total_mol": temporal_total, "relative_error": rel_err}


def p0_d(f0: float) -> dict:
    """turnover geometry / RNG (docs Exp18 §2 P0-D)。"""
    from evosim.world import World

    def build(seed):
        cfg = core.make_flux_cfg(f0, temporal=False, turnover=True, initial_population=0,
                                 h2_vent_turnover_interval_s=172800.0,
                                 h2_vent_min_separation_cells=4)
        rng = np.random.Generator(np.random.PCG64(seed))
        w = World(cfg, rng)
        w.configure_flux_vents(core.LEGACY_FOUR_CENTERS)
        return cfg, w

    cfg, w = build(190001)
    gw, gh = cfg.grid_w, cfg.grid_h
    n_steps = int(round(20 * 86400.0 / cfg.dt_seconds))  # 20日 (Phase Bの最長run)
    count_ok = True
    for _ in range(n_steps):
        w.update()
        if len(set(w.vent_slot_positions)) != cfg.n_vents:
            count_ok = False
            break
    boundary_ok = all(
        1 <= ev["position"][0] <= gw - 2 and 1 <= ev["position"][1] <= gh - 2
        for ev in w._turnover_events[:20])

    _, w_same = build(190001)
    same_seed_ok = w_same._turnover_events[:10] == w._turnover_events[:10]
    _, w_diff = build(190002)
    diff_seed_ok = w_diff._turnover_events[:10] != w._turnover_events[:10]

    rng_probe = np.random.Generator(np.random.PCG64(190003))
    cfg2, w_a = build(190003)
    draw_a = rng_probe.random()  # 独立rng: worldのenv_rngとは無関係
    cfg3 = core.make_flux_cfg(f0, temporal=False, turnover=False, initial_population=0)
    rng_shared = np.random.Generator(np.random.PCG64(190004))
    from evosim.world import World as _World
    w_no_turnover = _World(cfg3, rng_shared)
    w_no_turnover.configure_flux_vents(core.LEGACY_FOUR_CENTERS)
    draw_no_turnover = rng_shared.random()
    rng_shared2 = np.random.Generator(np.random.PCG64(190004))
    cfg4 = core.make_flux_cfg(f0, temporal=False, turnover=True, initial_population=0,
                              h2_vent_turnover_interval_s=172800.0)
    w_turnover = _World(cfg4, rng_shared2)
    w_turnover.configure_flux_vents(core.LEGACY_FOUR_CENTERS)
    draw_with_turnover = rng_shared2.random()
    rng_isolated = bool(draw_no_turnover == draw_with_turnover)

    pass_ = bool(count_ok and boundary_ok and same_seed_ok and diff_seed_ok and rng_isolated)
    return {
        "pass": pass_, "vent_count_always_n_vents": count_ok,
        "boundary_constraint_ok": boundary_ok,
        "same_seed_same_schedule": same_seed_ok,
        "diff_seed_diff_schedule": diff_seed_ok,
        "organism_rng_isolated": rng_isolated,
        "turnover_events_over_20d": w._turnover_applied_idx,
    }


def p0_e(f0: float) -> dict:
    """dt convergence: 5s / 10s (docs Exp18 §2 P0-E)。"""
    from evosim.world import World

    def run(dt):
        cfg = core.make_flux_cfg(f0, temporal=False, turnover=False, initial_population=0,
                                 dt_seconds=dt)
        rng = np.random.Generator(np.random.PCG64(180005))
        w = World(cfg, rng)
        w.configure_flux_vents(core.LEGACY_FOUR_CENTERS)
        total_in = 0.0
        n_steps = int(round(6 * 3600.0 / dt))
        for _ in range(n_steps):
            inflow, _ = w.update()
            total_in += inflow
        return total_in, w.total_h2(), float(w.h2[10, 10])

    in5, stock5, radial5 = run(5.0)
    in10, stock10, radial10 = run(10.0)
    in_err = abs(in5 - in10) / max(in5, in10, 1e-30)
    stock_err = abs(stock5 - stock10) / max(stock5, stock10, 1e-30)
    radial_err = abs(radial5 - radial10) / max(radial5, radial10, 1e-30)
    pass_ = bool(in_err <= 0.01 and stock_err <= 0.01 and radial_err <= 0.05)
    return {"pass": pass_, "source_total_relative_error": in_err,
           "final_stock_relative_error": stock_err,
           "radial_concentration_relative_error": radial_err}


def main() -> None:
    a_result, h2_field = p0_a()
    f0 = a_result["f0_mol_s"]
    result = {
        "status": "Exp18 V1.10.1 Phase 0 preflight; NOT formal Exp18",
        "no_parameter_tuning": True,
        "P0_A": a_result,
        "P0_B": p0_b(f0, h2_field),
        "P0_C": p0_c(f0),
        "P0_D": p0_d(f0),
        "P0_E": p0_e(f0),
    }
    result["dispatch_gate_pass"] = bool(
        result["P0_A"]["pass"] and result["P0_B"]["pass"] and result["P0_C"]["pass"]
        and result["P0_D"]["pass"] and result["P0_E"]["pass"]
    )
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "phase0_v1101_results.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    # F0とcommon initial H2 fieldはPhase A/Bで再利用するため別途保存する
    np.save(out.with_name("common_initial_h2_field.npy"), h2_field)
    (out.with_name("f0_calibration.json")).write_text(
        json.dumps({"f0_mol_s": f0, **{k: v for k, v in a_result.items() if k != "pass"}},
                  indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
