"""Exp13 集計・選定・事前登録判定 (docs/Exp13_実験計画確定.md §5,6,8,10,16)。

Phase A (A1 light map / A2 chemical grid / A2b validation / A3 density) の
選定規則と、Phase B (B1-B4) のHARD GATE集計を実装する。

技術的集計エラー (run欠落・重複・想定外key・snapshot欠落等) は
AggregationErrorとして分離し、確定したscientific verdictを出さない
(Exp11/12と同じ設計。docs/V1.8_実装チェックリスト.md §15)。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.physiology import density_response
from tools.exp13_common import (
    A1_LATE_BIRTH_WINDOW, A1_LATE_POP_FLOOR, A1_LIGHT_MAX, A1_MAX_EXTINCT,
    A1_MIN_COMPLETE_FRAC, A1_MIN_LATE_BIRTH_SEEDS, A1_MIN_LATE_POP_SEEDS,
    A1_SEEDS, A1_TICKS, A2_CHEM_UPTAKE, A2_CHEMICAL_UPTAKE_HALF,
    A2_DEPLETION_FRAC, A2_DEPLETION_MIN_SEEDS, A2_H_MEDIAN_HIGH,
    A2_H_MEDIAN_LOW, A2_LATE_BIRTH_WINDOW, A2_MIN_COMPLETE_SEEDS,
    A2_MIN_LATE_BIRTH_SEEDS, A2_SEEDS, A2_TICKS, A2B_PLACEMENTS, A2B_SEEDS,
    A2B_TICKS, A2B_VENT_LATE_BIRTH_WINDOW, A2B_VENT_MIN_COMPLETE_SEEDS,
    A2B_VENT_MIN_LATE_BIRTH_SEEDS, A3_POPULATIONS, A3_SEEDS, A3_TICKS,
    B1_SEEDS, B1_TICKS, B2_SEEDS, B2_TICKS, B3_SEEDS, B3_TICKS,
    B4A_SEEDS, B4A_TICKS, B4B_SEEDS, B4B_TICKS, PHASE_A_TOTAL, PHASE_B_TOTAL,
)

VENT_CELL_COUNT_STANDARD = 13  # config.py chemical_stimulus_half=12.3 と同じ前提


class AggregationError(Exception):
    """技術的な集計失敗 (run欠落・重複・想定外key・snapshot欠落等)。"""


# ---------------------------------------------------------------------------
# run単位のデータ読み込み
# ---------------------------------------------------------------------------

def load_run(run_dir: Path) -> dict | None:
    meta_path = run_dir / "meta.json"
    stats_path = run_dir / "stats.csv"
    cfg_path = run_dir / "config.json"
    if not (meta_path.exists() and stats_path.exists() and cfg_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        rows = []
        with open(stats_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception:
        return None
    return {"meta": meta, "cfg": cfg, "stats": rows, "path": run_dir}


def classify_status(run: dict, ticks: int) -> str:
    stats = run["stats"]
    cfg = run["cfg"]
    if not stats:
        return "INCOMPLETE_RESOURCE"
    last = stats[-1]
    try:
        pop = int(last.get("population", -1))
        ticks_done = int(last.get("tick", 0))
    except (ValueError, TypeError):
        return "INCOMPLETE_RESOURCE"
    if pop == 0:
        return "EXTINCT"
    halt = cfg.get("max_population_halt", 0) or 0
    if halt and pop >= halt and ticks_done < ticks:
        return "POP_HALT"
    if ticks_done >= ticks:
        return "COMPLETE"
    return "INCOMPLETE_RESOURCE"


def late_births(run: dict, window: int) -> int:
    """final `window` tickでの出生数 (births_cumの差分から推定)。"""
    stats = run["stats"]
    if len(stats) < 2:
        return int(stats[0]["births_cum"]) if stats else 0
    last_tick = int(stats[-1]["tick"])
    cutoff = last_tick - window
    idx = 0
    for i, row in enumerate(stats):
        if int(row["tick"]) >= cutoff:
            idx = i
            break
    births_before = int(stats[idx]["births_cum"]) if idx < len(stats) else 0
    births_after = int(stats[-1]["births_cum"])
    return births_after - births_before


def late_population_values(run: dict, window: int) -> list[float]:
    stats = run["stats"]
    if not stats:
        return []
    last_tick = int(stats[-1]["tick"])
    cutoff = last_tick - window
    return [float(row["population"]) for row in stats if int(row["tick"]) >= cutoff]


def night_light_gain_is_zero(run: dict) -> bool:
    """light_cycle_factor==0の行でlight_supply_rate/flow_light_cum増分が0であることを
    確認する (厳密な差分計算まではせず、cycle_factor=0行の存在と
    light_supply_rateがそのタイミングで0であることを確認する軽量チェック)。"""
    stats = run["stats"]
    for row in stats:
        try:
            factor = float(row.get("light_cycle_factor", 1.0))
        except (ValueError, TypeError):
            continue
        if factor == 0.0:
            try:
                rate = float(row.get("light_supply_rate", 0.0))
            except (ValueError, TypeError):
                continue
            if rate != 0.0:
                return False
    return True


# ---------------------------------------------------------------------------
# run収集: 期待key集合との完全一致
# ---------------------------------------------------------------------------

def _require_unique(found: dict[tuple, list[Path]], expected: set[tuple],
                    label: str, errors: list[str]) -> dict[tuple, Path]:
    found_keys = set(found.keys())
    missing = expected - found_keys
    for key in sorted(missing, key=str):
        errors.append(f"{label}: 欠落run key={key}")
    unexpected = found_keys - expected
    for key in sorted(unexpected, key=str):
        errors.append(f"{label}: 想定外run key={key} (期待gridに含まれない)")
    result = {}
    for key, dirs in found.items():
        if len(dirs) > 1:
            errors.append(f"{label}: 重複run key={key} ({len(dirs)}件): {[str(d) for d in dirs]}")
        if key in expected and dirs:
            result[key] = dirs[0]
    return result


def collect_phase_a1(base_dir: Path, tech_errors: list[str]) -> dict[tuple, dict]:
    found: dict[tuple, list[Path]] = {}
    for run_dir in {p.parent for p in base_dir.rglob("config.json")}:
        run = load_run(run_dir)
        if run is None:
            continue
        cfg = run["cfg"]
        meta = run["meta"]
        if cfg.get("chem_vent_flux", None) not in (0, 0.0):
            continue
        if cfg.get("light_max") not in A1_LIGHT_MAX:
            continue
        seed = meta.get("seed")
        key = (round(float(cfg["light_max"]), 3), seed)
        found.setdefault(key, []).append(run_dir)
    expected = {(lm, s) for lm in A1_LIGHT_MAX for s in A1_SEEDS}
    kept = _require_unique(found, expected, "A1", tech_errors)
    return {k: load_run(v) for k, v in kept.items()}


def collect_phase_a2(base_dir: Path, tech_errors: list[str]) -> dict[tuple, dict]:
    found: dict[tuple, list[Path]] = {}
    for run_dir in {p.parent for p in base_dir.rglob("config.json")}:
        run = load_run(run_dir)
        if run is None:
            continue
        cfg = run["cfg"]
        meta = run["meta"]
        if cfg.get("light_max") not in (0, 0.0):
            continue
        if cfg.get("chemical_uptake_half") not in A2_CHEMICAL_UPTAKE_HALF:
            continue
        if cfg.get("chem_uptake") not in A2_CHEM_UPTAKE:
            continue
        seed = meta.get("seed")
        key = (round(float(cfg["chemical_uptake_half"]), 3),
              round(float(cfg["chem_uptake"]), 3), seed)
        found.setdefault(key, []).append(run_dir)
    expected = {(k, u, s) for k in A2_CHEMICAL_UPTAKE_HALF
               for u in A2_CHEM_UPTAKE for s in A2_SEEDS}
    kept = _require_unique(found, expected, "A2", tech_errors)
    return {k: load_run(v) for k, v in kept.items()}


# ---------------------------------------------------------------------------
# A1: robust light viability (§5.2, 5.3)
# ---------------------------------------------------------------------------

def a1_level_summary(level_runs: dict[int, dict]) -> dict:
    """1つのlight_max水準の5 seed分をまとめる。"""
    n = len(level_runs)
    statuses = {}
    late_birth_ok = 0
    late_pop_ok = 0
    night_zero_ok = 0
    for seed, run in level_runs.items():
        status = classify_status(run, A1_TICKS)
        statuses[seed] = status
        lb = late_births(run, A1_LATE_BIRTH_WINDOW)
        if lb > 0:
            late_birth_ok += 1
        pop_vals = late_population_values(run, A1_LATE_BIRTH_WINDOW)
        if pop_vals:
            med = float(np.median(pop_vals))
            if med >= A1_LATE_POP_FLOOR:
                late_pop_ok += 1
        if night_light_gain_is_zero(run):
            night_zero_ok += 1

    n_complete = sum(1 for s in statuses.values() if s == "COMPLETE")
    n_extinct = sum(1 for s in statuses.values() if s == "EXTINCT")
    n_pophalt = sum(1 for s in statuses.values() if s == "POP_HALT")

    robust = (
        n_complete >= A1_MIN_COMPLETE_FRAC
        and n_extinct <= A1_MAX_EXTINCT
        and n_pophalt == 0
        and late_birth_ok >= A1_MIN_LATE_BIRTH_SEEDS
        and late_pop_ok >= A1_MIN_LATE_POP_SEEDS
        and night_zero_ok == n
    )
    return {
        "n": n, "n_complete": n_complete, "n_extinct": n_extinct,
        "n_pophalt": n_pophalt, "late_birth_ok": late_birth_ok,
        "late_pop_ok": late_pop_ok, "night_zero_ok": night_zero_ok,
        "robust_light_viable": robust,
    }


def select_light_max(a1_runs: dict[tuple, dict]) -> tuple[float | None, dict]:
    per_level = {}
    for lm in A1_LIGHT_MAX:
        level_runs = {seed: a1_runs[(lm, seed)] for seed in A1_SEEDS if (lm, seed) in a1_runs}
        per_level[lm] = a1_level_summary(level_runs)
    viable = [lm for lm in A1_LIGHT_MAX if per_level[lm]["robust_light_viable"]]
    selected = min(viable) if viable else None
    return selected, per_level


# ---------------------------------------------------------------------------
# A2: chemical grid admissibility / selection (§6.2, 6.3)
# ---------------------------------------------------------------------------

def _combo_median_h_and_stock(runs: list[dict], k: float) -> tuple[float | None, float | None]:
    """occupied-vent snapshot群からrealized H(C,K)のgroup medianと
    そのcombinationのmin median vent stockを求める。

    environment/env_*.npz (chemical field) + snapshot CSV (organism座標) を
    使い、個体が実際にいたセルのchemical stockを集める。
    """
    all_h: list[float] = []
    per_run_stock_medians: list[float] = []
    for run in runs:
        run_dir = run["path"]
        env_dir = run_dir / "environment"
        static_path = env_dir / "static.npz"
        if not static_path.exists():
            continue
        with np.load(static_path) as d:
            chem_mask = d["chem_mask"]
        cell_size = float(run["cfg"].get("cell_size", 20.0))
        env_files = sorted(env_dir.glob("env_*.npz"))
        run_stocks: list[float] = []
        for env_path in env_files:
            tick_str = env_path.stem.split("_")[-1]
            snap_path = run_dir / "snapshots" / f"snap_{tick_str}.csv"
            with np.load(env_path) as d:
                chemical = d["chemical"]
            vent_stock_vals = chemical[chem_mask]
            if vent_stock_vals.size:
                run_stocks.append(float(np.median(vent_stock_vals)))
            if not snap_path.exists():
                continue
            with open(snap_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    x, y = float(row["x"]), float(row["y"])
                    ix = min(chemical.shape[0] - 1, max(0, int(x / cell_size)))
                    iy = min(chemical.shape[1] - 1, max(0, int(y / cell_size)))
                    if chem_mask[ix, iy]:
                        c = float(chemical[ix, iy])
                        all_h.append(density_response(c, k))
        if run_stocks:
            per_run_stock_medians.append(float(np.median(run_stocks)))
    group_median_h = float(np.median(all_h)) if all_h else None
    min_median_stock = min(per_run_stock_medians) if per_run_stock_medians else None
    return group_median_h, min_median_stock


def a2_combo_summary(k: float, uptake: float, runs: dict[int, dict], cfg_sample: dict) -> dict:
    n = len(runs)
    statuses = {seed: classify_status(run, A2_TICKS) for seed, run in runs.items()}
    n_complete = sum(1 for s in statuses.values() if s == "COMPLETE")
    n_pophalt = sum(1 for s in statuses.values() if s == "POP_HALT")
    late_birth_ok = sum(1 for run in runs.values()
                        if late_births(run, A2_LATE_BIRTH_WINDOW) > 0)

    group_median_h, _ = _combo_median_h_and_stock(list(runs.values()), k)

    chem_vent_flux = float(cfg_sample.get("chem_vent_flux", 16.0))
    chem_loss_frac = float(cfg_sample.get("chem_loss_frac", 0.10))
    biological_free_c_eq = chem_vent_flux / VENT_CELL_COUNT_STANDARD / chem_loss_frac

    depletion_seeds_ok = 0
    for run in runs.values():
        run_dir = run["path"]
        env_dir = run_dir / "environment"
        static_path = env_dir / "static.npz"
        if not static_path.exists():
            continue
        with np.load(static_path) as d:
            chem_mask = d["chem_mask"]
        stocks = []
        for env_path in sorted(env_dir.glob("env_*.npz")):
            with np.load(env_path) as d:
                chemical = d["chemical"]
            vals = chemical[chem_mask]
            if vals.size:
                stocks.append(float(np.median(vals)))
        if stocks and min(stocks) <= A2_DEPLETION_FRAC * biological_free_c_eq:
            depletion_seeds_ok += 1

    h_in_band = (group_median_h is not None
                and A2_H_MEDIAN_LOW <= group_median_h <= A2_H_MEDIAN_HIGH)

    admissible = (
        n_complete >= A2_MIN_COMPLETE_SEEDS
        and late_birth_ok >= A2_MIN_LATE_BIRTH_SEEDS
        and n_pophalt == 0
        and h_in_band
        and depletion_seeds_ok >= A2_DEPLETION_MIN_SEEDS
    )
    return {
        "n": n, "n_complete": n_complete, "n_pophalt": n_pophalt,
        "late_birth_ok": late_birth_ok, "group_median_h": group_median_h,
        "depletion_seeds_ok": depletion_seeds_ok,
        "biological_free_c_eq": biological_free_c_eq,
        "admissible": admissible,
    }


def select_chemical_pair(a2_runs: dict[tuple, dict]) -> tuple[dict | None, dict]:
    per_combo = {}
    cfg_sample = None
    for k in A2_CHEMICAL_UPTAKE_HALF:
        for u in A2_CHEM_UPTAKE:
            runs = {seed: a2_runs[(k, u, seed)] for seed in A2_SEEDS if (k, u, seed) in a2_runs}
            if runs and cfg_sample is None:
                cfg_sample = next(iter(runs.values()))["cfg"]
            per_combo[(k, u)] = a2_combo_summary(k, u, runs, cfg_sample or {})

    admissible = [(k, u) for (k, u) in per_combo if per_combo[(k, u)]["admissible"]]
    if not admissible:
        return None, per_combo

    min_uptake = min(u for (_, u) in admissible)
    same_uptake = [(k, u) for (k, u) in admissible if u == min_uptake]
    # median Hが0.5に最も近いK。tieは小さいK
    def _dist(item):
        k, u = item
        h = per_combo[(k, u)]["group_median_h"]
        return (abs((h if h is not None else 1e9) - 0.5), k)

    best = min(same_uptake, key=_dist)
    selected = {"chemical_uptake_half": best[0], "chem_uptake": best[1]}
    return selected, per_combo


# ---------------------------------------------------------------------------
# 集計表出力 (docs/V1.8_実装チェックリスト.md §15: A1 full sweep table /
# A2 2D grid table)
# ---------------------------------------------------------------------------

def _write_a1_table(out_dir: Path, a1_summary: dict[float, dict]) -> None:
    path = out_dir / "exp13_a1_light_sweep.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["light_max", "n", "n_complete", "n_extinct", "n_pophalt",
                   "late_birth_ok", "late_pop_ok", "night_zero_ok", "robust_light_viable"])
        for lm in A1_LIGHT_MAX:
            s = a1_summary[lm]
            w.writerow([lm, s["n"], s["n_complete"], s["n_extinct"], s["n_pophalt"],
                       s["late_birth_ok"], s["late_pop_ok"], s["night_zero_ok"],
                       s["robust_light_viable"]])


def _write_a2_table(out_dir: Path, a2_summary: dict[tuple, dict]) -> None:
    path = out_dir / "exp13_a2_chemical_grid.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["chemical_uptake_half", "chem_uptake", "n", "n_complete", "n_pophalt",
                   "late_birth_ok", "group_median_h", "depletion_seeds_ok",
                   "biological_free_c_eq", "admissible"])
        for k in A2_CHEMICAL_UPTAKE_HALF:
            for u in A2_CHEM_UPTAKE:
                s = a2_summary[(k, u)]
                w.writerow([k, u, s["n"], s["n_complete"], s["n_pophalt"],
                           s["late_birth_ok"], s["group_median_h"], s["depletion_seeds_ok"],
                           s["biological_free_c_eq"], s["admissible"]])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def summarize_phase_a(base_dir: Path, out_dir: Path | None) -> int:
    tech_errors: list[str] = []
    a1_runs = collect_phase_a1(base_dir, tech_errors)
    a2_runs = collect_phase_a2(base_dir, tech_errors)

    if tech_errors:
        for e in tech_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("AggregationError: Phase A技術的集計エラーのためselected値を確定しない", file=sys.stderr)
        return 1

    selected_light, a1_summary = select_light_max(a1_runs)
    selected_chem, a2_summary = select_chemical_pair(a2_runs)

    print("=== Exp13 Phase A 集計 ===")
    print("\n--- A1 light map ---")
    for lm in A1_LIGHT_MAX:
        s = a1_summary[lm]
        mark = "ROBUST_LIGHT_VIABLE" if s["robust_light_viable"] else "-"
        print(f"  light_max={lm:.2f}: COMPLETE={s['n_complete']}/{s['n']} "
              f"EXTINCT={s['n_extinct']}/{s['n']} POP_HALT={s['n_pophalt']}/{s['n']} "
              f"late_birth={s['late_birth_ok']}/{s['n']} late_pop>=25={s['late_pop_ok']}/{s['n']} "
              f"night0={s['night_zero_ok']}/{s['n']}  {mark}")
    if selected_light is None:
        print("\nLIGHT_CALIBRATION_FAIL / REVIEW — ROBUST_LIGHT_VIABLEを満たす水準なし")
    else:
        print(f"\nselected_light_max = {selected_light}")

    print("\n--- A2 chemical grid ---")
    for k in A2_CHEMICAL_UPTAKE_HALF:
        for u in A2_CHEM_UPTAKE:
            s = a2_summary[(k, u)]
            mark = "ADMISSIBLE" if s["admissible"] else "-"
            h = s["group_median_h"]
            h_str = f"{h:.3f}" if h is not None else "N/A"
            print(f"  K={k:.3f} uptake={u:.3f}: COMPLETE={s['n_complete']}/{s['n']} "
                  f"late_birth={s['late_birth_ok']}/{s['n']} median_H={h_str} "
                  f"depletion={s['depletion_seeds_ok']}/{s['n']}  {mark}")
    if selected_chem is None:
        print("\nCHEMICAL_CALIBRATION_FAIL / REVIEW — admissible combinationなし")
    else:
        print(f"\nselected_chemical_uptake_half = {selected_chem['chemical_uptake_half']}")
        print(f"selected_chem_uptake = {selected_chem['chem_uptake']}")

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_a1_table(out_dir, a1_summary)
        _write_a2_table(out_dir, a2_summary)

    if selected_light is None or selected_chem is None:
        return 1

    if out_dir is not None:
        selected = {
            "light_max": selected_light,
            "chemical_uptake_half": selected_chem["chemical_uptake_half"],
            "chem_uptake": selected_chem["chem_uptake"],
        }
        (out_dir / "exp13_selected.json").write_text(
            json.dumps(selected, indent=2), encoding="utf-8")
        print(f"\nA_PASS -> {out_dir / 'exp13_selected.json'} を書き出した")
    return 0


# ---------------------------------------------------------------------------
# A2b: selected pairの検証 (§7) — vent placementのみHARD gate
# ---------------------------------------------------------------------------

def collect_phase_a2b(base_dir: Path, tech_errors: list[str]) -> dict[tuple, dict]:
    found: dict[tuple, list[Path]] = {}
    for run_dir in {p.parent for p in base_dir.rglob("config.json")}:
        run = load_run(run_dir)
        if run is None:
            continue
        cfg, meta = run["cfg"], run["meta"]
        placement = cfg.get("diagnostic_placement")
        if placement not in A2B_PLACEMENTS:
            continue
        if cfg.get("light_max") not in (0, 0.0):
            continue
        seed = meta.get("seed")
        key = (placement, seed)
        found.setdefault(key, []).append(run_dir)
    expected = {(p, s) for p in A2B_PLACEMENTS for s in A2B_SEEDS}
    kept = _require_unique(found, expected, "A2b", tech_errors)
    return {k: load_run(v) for k, v in kept.items()}


def a2b_vent_gate(a2b_runs: dict[tuple, dict]) -> dict:
    vent_runs = {s: a2b_runs[("vent", s)] for s in A2B_SEEDS if ("vent", s) in a2b_runs}
    n = len(vent_runs)
    n_complete = sum(1 for r in vent_runs.values()
                     if classify_status(r, A2B_TICKS) == "COMPLETE")
    late_birth_ok = sum(1 for r in vent_runs.values()
                        if late_births(r, A2B_VENT_LATE_BIRTH_WINDOW) > 0)
    # 明確なdepletion: occupied vent stockが生物不在平衡より低い状態を保っているか
    depletion_ok = 0
    for r in vent_runs.values():
        env_dir = r["path"] / "environment"
        static_path = env_dir / "static.npz"
        if not static_path.exists():
            continue
        with np.load(static_path) as d:
            chem_mask = d["chem_mask"]
        chem_vent_flux = float(r["cfg"].get("chem_vent_flux", 16.0))
        chem_loss_frac = float(r["cfg"].get("chem_loss_frac", 0.10))
        c_eq = chem_vent_flux / VENT_CELL_COUNT_STANDARD / chem_loss_frac
        envs = sorted(env_dir.glob("env_*.npz"))
        if not envs:
            continue
        with np.load(envs[-1]) as d:
            chemical = d["chemical"]
        vals = chemical[chem_mask]
        if vals.size and float(np.median(vals)) < c_eq:
            depletion_ok += 1
    pass_ = (n_complete >= A2B_VENT_MIN_COMPLETE_SEEDS
            and late_birth_ok >= A2B_VENT_MIN_LATE_BIRTH_SEEDS
            and depletion_ok >= A2B_VENT_MIN_COMPLETE_SEEDS)
    return {"n": n, "n_complete": n_complete, "late_birth_ok": late_birth_ok,
           "depletion_ok": depletion_ok, "pass": pass_}


# ---------------------------------------------------------------------------
# A3: density competition mechanism check (§8)
# ---------------------------------------------------------------------------

def collect_phase_a3(base_dir: Path, tech_errors: list[str]) -> dict[tuple, dict]:
    found: dict[tuple, list[Path]] = {}
    for run_dir in {p.parent for p in base_dir.rglob("config.json")}:
        run = load_run(run_dir)
        if run is None:
            continue
        cfg, meta = run["cfg"], run["meta"]
        pop = cfg.get("initial_population")
        if pop not in A3_POPULATIONS:
            continue
        if cfg.get("light_max") not in (0, 0.0):
            continue
        # A2b random/vent との混同を避けるため diagnostic_placement=vent かつ
        # ticks が A3_TICKS 相当のrunだけを対象にする (statsの最終tickで判定)
        if cfg.get("diagnostic_placement") != "vent":
            continue
        if not run["stats"]:
            continue
        last_tick = int(run["stats"][-1]["tick"])
        if last_tick > A3_TICKS:
            continue
        seed = meta.get("seed")
        key = (pop, seed)
        found.setdefault(key, []).append(run_dir)
    expected = {(p, s) for p in A3_POPULATIONS for s in A3_SEEDS}
    kept = _require_unique(found, expected, "A3", tech_errors)
    return {k: load_run(v) for k, v in kept.items()}


def a3_direction_check(a3_runs: dict[tuple, dict]) -> dict:
    """密度増加でper-capita chemical gainが低下し、高密度ほどvent stockが
    低下する方向性を確認する (§8 PASS方向)。"""
    per_capita_gain: dict[int, list[float]] = {p: [] for p in A3_POPULATIONS}
    final_stock: dict[int, list[float]] = {p: [] for p in A3_POPULATIONS}
    for (pop, seed), run in a3_runs.items():
        stats = run["stats"]
        if not stats:
            continue
        last = stats[-1]
        try:
            flow = float(last.get("flow_chemical_cum", 0.0))
        except (ValueError, TypeError):
            flow = 0.0
        per_capita_gain[pop].append(flow / max(pop, 1))
        try:
            chem_total = float(last.get("chemical_total", 0.0))
        except (ValueError, TypeError):
            chem_total = 0.0
        final_stock[pop].append(chem_total)

    means_gain = {p: (float(np.mean(v)) if v else None) for p, v in per_capita_gain.items()}
    means_stock = {p: (float(np.mean(v)) if v else None) for p, v in final_stock.items()}

    pops_sorted = sorted(A3_POPULATIONS)
    gain_seq = [means_gain[p] for p in pops_sorted]
    stock_seq = [means_stock[p] for p in pops_sorted]

    gain_monotone_down = all(
        gain_seq[i] is not None and gain_seq[i + 1] is not None and gain_seq[i] >= gain_seq[i + 1]
        for i in range(len(gain_seq) - 1)
    )
    stock_monotone_down = all(
        stock_seq[i] is not None and stock_seq[i + 1] is not None and stock_seq[i] >= stock_seq[i + 1]
        for i in range(len(stock_seq) - 1)
    )
    direction_pass = gain_monotone_down and stock_monotone_down
    return {
        "means_gain": means_gain, "means_stock": means_stock,
        "direction_pass": direction_pass,
    }


# ---------------------------------------------------------------------------
# Phase B: B1/B2 HARD GATE, B3/B4 diagnostic
# ---------------------------------------------------------------------------

def collect_phase_bx(base_dir: Path, seeds: list[int], ticks: int,
                     match_fn, label: str, tech_errors: list[str]) -> dict[int, dict]:
    found: dict[int, list[Path]] = {}
    for run_dir in {p.parent for p in base_dir.rglob("config.json")}:
        run = load_run(run_dir)
        if run is None:
            continue
        if not match_fn(run["cfg"], run["stats"]):
            continue
        seed = run["meta"].get("seed")
        found.setdefault(seed, []).append(run_dir)
    expected = {(s,) for s in seeds}
    kept = _require_unique(
        {(k,): v for k, v in found.items()}, expected, label, tech_errors)
    return {k[0]: load_run(v) for k, v in kept.items()}


def b_gate_summary(runs: dict[int, dict], ticks: int, late_window: int) -> dict:
    n = len(runs)
    n_complete = sum(1 for r in runs.values() if classify_status(r, ticks) == "COMPLETE")
    late_birth_ok = sum(1 for r in runs.values() if late_births(r, late_window) > 0)
    return {"n": n, "n_complete": n_complete, "late_birth_ok": late_birth_ok}


# ---------------------------------------------------------------------------
# 最終集計: Phase A再検証 + Phase B + 全体verdict (§16)
# ---------------------------------------------------------------------------

def summarize_final(base_dir: Path, selected_path: Path, out_dir: Path | None) -> int:
    tech_errors: list[str] = []

    if not selected_path.exists():
        print(f"ERROR: selected file が見つからない: {selected_path}", file=sys.stderr)
        return 1
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    lm, k, up = selected["light_max"], selected["chemical_uptake_half"], selected["chem_uptake"]

    a1_runs = collect_phase_a1(base_dir, tech_errors)
    a2_runs = collect_phase_a2(base_dir, tech_errors)
    a2b_runs = collect_phase_a2b(base_dir, tech_errors)
    a3_runs = collect_phase_a3(base_dir, tech_errors)

    def _is_b1(cfg, stats):
        return (cfg.get("light_max") == lm and cfg.get("chem_vent_flux") in (0, 0.0)
                and cfg.get("fixed_genes") and len(cfg["fixed_genes"]) == 14)

    def _is_b2(cfg, stats):
        return (cfg.get("light_max") in (0, 0.0)
                and cfg.get("chemical_uptake_half") == k and cfg.get("chem_uptake") == up
                and cfg.get("diagnostic_placement") == "random"
                and cfg.get("fixed_genes") and len(cfg["fixed_genes"]) == 14)

    def _is_b3(cfg, stats):
        return (cfg.get("light_max") == lm and cfg.get("chem_vent_flux")
                and cfg.get("fixed_genes") and len(cfg["fixed_genes"]) == 12)

    def _is_b4a(cfg, stats):
        return (cfg.get("light_max") == lm
                and cfg.get("diagnostic_gene_overrides", {}).get("body_size") is not None)

    def _is_b4b(cfg, stats):
        return (cfg.get("light_max") == lm
                and cfg.get("fixed_genes") and len(cfg["fixed_genes"]) == 13)

    b1_runs = collect_phase_bx(base_dir, B1_SEEDS, B1_TICKS, _is_b1, "B1", tech_errors)
    b2_runs = collect_phase_bx(base_dir, B2_SEEDS, B2_TICKS, _is_b2, "B2", tech_errors)
    b3_runs = collect_phase_bx(base_dir, B3_SEEDS, B3_TICKS, _is_b3, "B3", tech_errors)
    b4a_runs = collect_phase_bx(base_dir, B4A_SEEDS, B4A_TICKS, _is_b4a, "B4a", tech_errors)
    b4b_runs = collect_phase_bx(base_dir, B4B_SEEDS, B4B_TICKS, _is_b4b, "B4b", tech_errors)

    if tech_errors:
        for e in tech_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("AggregationError: 技術的集計エラーのためExp13 verdictを確定しない", file=sys.stderr)
        return 1

    selected_light, a1_summary = select_light_max(a1_runs)
    selected_chem, a2_summary = select_chemical_pair(a2_runs)
    a2b_vent = a2b_vent_gate(a2b_runs)
    a3 = a3_direction_check(a3_runs)

    a_pass = (
        selected_light == lm and selected_chem is not None
        and selected_chem["chemical_uptake_half"] == k and selected_chem["chem_uptake"] == up
        and a2b_vent["pass"] and a3["direction_pass"]
    )

    b1 = b_gate_summary(b1_runs, B1_TICKS, 4_000)
    b2 = b_gate_summary(b2_runs, B2_TICKS, 4_000)

    print("=== Exp13 最終集計 ===")
    print(f"\nselected (Phase A artifact): light_max={lm} chemical_uptake_half={k} "
          f"chem_uptake={up}")
    print(f"Phase A再検証: selected一致={selected_light == lm and selected_chem == {'chemical_uptake_half': k, 'chem_uptake': up}}")
    print(f"A2b vent gate: {a2b_vent}")
    print(f"A3 direction check: gain={a3['means_gain']} stock={a3['means_stock']} "
          f"pass={a3['direction_pass']}")
    print(f"\nB1: COMPLETE={b1['n_complete']}/{b1['n']} late_birth={b1['late_birth_ok']}/{b1['n']}")
    print(f"B2: COMPLETE={b2['n_complete']}/{b2['n']} late_birth={b2['late_birth_ok']}/{b2['n']}")
    print(f"B3 (診断のみ): {len(b3_runs)} run収集")
    print(f"B4a (診断のみ): {len(b4a_runs)} run収集")
    print(f"B4b (診断のみ): {len(b4b_runs)} run収集")

    b1_pass = b1["n_complete"] >= 6 and b1["late_birth_ok"] >= 6
    b2_pass = b2["n_complete"] >= 6 and b2["late_birth_ok"] >= 6
    b1_recal = b1["n_complete"] <= 5 or b1["late_birth_ok"] <= 5
    b2_recal = b2["n_complete"] <= 5 or b2["late_birth_ok"] <= 5

    if not a_pass:
        verdict = "INVALID_OR_METHOD_REVIEW"
        reason = "Phase A selected値が現在runと一致しないか、A2b/A3 gateが不成立"
    elif b1_recal or b2_recal or not a3["direction_pass"]:
        verdict = "V1_8_RECALIBRATE_REVIEW"
        reason = "B1/B2いずれかが5/8以下、またはdensity competitionが想定方向でない"
    elif b1_pass and b2_pass and a_pass:
        verdict = "V1_8_ACCEPT_CANDIDATE"
        reason = "Phase 0/A/A3/B1/B2すべてPASS"
    else:
        verdict = "V1_8_RECALIBRATE_REVIEW"
        reason = "HARD GATE条件を完全には満たさない"

    print("\n============================================================")
    print(f"EXP13_VERDICT = {verdict}")
    print(f"理由: {reason}")
    print("============================================================")

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "exp13_verdict.txt").write_text(
            f"EXP13_VERDICT = {verdict}\n理由: {reason}\n", encoding="utf-8")
    return 0


def check_full_phase_a(base_dir: Path, selected_path: Path) -> int:
    """A1+A2+A2b+A3が全て揃った時点でPhase B開始可否を再検証する
    (workflow: phaseA_collect -> phase Bのgate)。"""
    tech_errors: list[str] = []
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    lm, k, up = selected["light_max"], selected["chemical_uptake_half"], selected["chem_uptake"]

    a1_runs = collect_phase_a1(base_dir, tech_errors)
    a2_runs = collect_phase_a2(base_dir, tech_errors)
    a2b_runs = collect_phase_a2b(base_dir, tech_errors)
    a3_runs = collect_phase_a3(base_dir, tech_errors)

    if tech_errors:
        for e in tech_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("AggregationError: Phase A技術的集計エラーのためPhase Bへ進まない", file=sys.stderr)
        return 1

    selected_light, _ = select_light_max(a1_runs)
    selected_chem, _ = select_chemical_pair(a2_runs)
    a2b_vent = a2b_vent_gate(a2b_runs)
    a3 = a3_direction_check(a3_runs)

    a_pass = (
        selected_light == lm and selected_chem is not None
        and selected_chem["chemical_uptake_half"] == k and selected_chem["chem_uptake"] == up
        and a2b_vent["pass"] and a3["direction_pass"]
    )
    print(f"selected_light_max再検証: {selected_light} (期待 {lm})")
    print(f"selected_chemical再検証: {selected_chem} (期待 K={k} uptake={up})")
    print(f"A2b vent gate: {a2b_vent}")
    print(f"A3 direction: {a3['direction_pass']}")
    print(f"A_PASS = {a_pass}")
    return 0 if a_pass else 1


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp13 集計・選定・判定")
    ap.add_argument("base_dir", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--selected", type=Path, default=None,
                    help="指定するとPhase B込みの最終判定を行う")
    ap.add_argument("--full-phase-a", action="store_true",
                    help="A1+A2+A2b+A3全体でA_PASSを再検証する (--selectedと併用)")
    args = ap.parse_args()
    if args.full_phase_a:
        if args.selected is None:
            print("ERROR: --full-phase-a には --selected が必要", file=sys.stderr)
            return 1
        return check_full_phase_a(args.base_dir, args.selected)
    if args.selected is not None:
        return summarize_final(args.base_dir, args.selected, args.out_dir)
    return summarize_phase_a(args.base_dir, args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
