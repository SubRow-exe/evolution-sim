"""Exp12 長期平衡解析・事前登録判定 (docs/Exp12_実験計画確定.md)。

使い方:
    uv run python tools/summarize_exp12.py runs/exp12 --out-dir exp12_out

技術的集計エラー (AggregationError) と科学的判定の分離:
  snapshot欠落・CSV読み込み失敗・run欠落/重複・first-10k参照不足は
  技術的集計エラーとして扱う。1件でもあれば非0終了し、
  SCIENTIFIC_VERDICTを確定値として出力しない
  (Exp12_実装チェックリスト.md §1.5)。

first-10k Exp11比較によるINTEGRITY_FAILは、そのrunを解析対象から除外する
(技術的集計エラーとは別カテゴリ。複数runで系統的に出た場合は
 呼び出し側 [workflow] がExp12全体停止を判断する)。
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from tools.exp12_common import (
    B1_BASELINE_SEED_MIN, B1_BMR_CORE, B1_DELAY_MAX_FOR_INTERIOR,
    B1_DELAY_SEED_MIN, B1_INTERIOR_SEED_MIN, B1_SEEDS, B2_BMR_CORE, B2_SEEDS,
    B2_STATIONARY_SEED_MIN, DECEL_RATIO, FIRST_10K, FIT_B_INF_MAX,
    FIT_B_INF_MIN, FIT_NRMSE_MAX, FIT_TAU_MAX, GENERATION_LATE_FRACTION,
    GENERATION_WINDOW_MIN, LOWER_BOUND_SENTINEL, MATTER_COUPLING_P_MAX,
    MATTER_COUPLING_RHO_MIN, MATTER_COUPLING_SEED_MIN_FRAC,
    MATTER_COUPLING_WINDOW, P_HIGH_THRESHOLD, P_LOW_THRESHOLDS,
    STATIONARITY_SENTINEL, SUSTAINED_RATIO, SUSTAINED_S_THRESHOLD,
    TICK_WINDOWS, infer_env, read_snapshot_columns, round_bmr_any,
    snapshot_files,
)


class AggregationError(Exception):
    """技術的な集計失敗 (snapshot欠落・読み込み失敗・run欠落/重複等)。"""


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
            reader = csv.DictReader(f)
            for row in reader:
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


# ---------------------------------------------------------------------------
# snapshot集計 (body_size分布 + generation分布)
# ---------------------------------------------------------------------------

def _quantile(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def load_snapshot_series(run_dir: Path) -> list[dict]:
    """全snapshotについて body_size分布 + generation分布を計算する。

    各要素: {tick, n, body_mean, body_median, q10,q25,q75,q90,
             p_021,p_023,p_025,p_high, g50, g90, gmax}

    snapshotが1つも無い場合は AggregationError。
    列欠落・読み込み失敗も AggregationError。
    """
    snaps = snapshot_files(run_dir)
    if not snaps:
        raise AggregationError(f"{run_dir}: snapshotが1つも見つからない")

    out = []
    for tick, path in snaps:
        try:
            cols = read_snapshot_columns(path, ["body_size", "generation"])
        except Exception as e:
            raise AggregationError(f"{run_dir}: snapshot読み込み失敗 (tick={tick}): {e}")

        sizes = cols["body_size"]
        gens = cols["generation"]
        if not sizes:
            raise AggregationError(f"{run_dir}: snapshot (tick={tick}) に個体データがない")

        n = len(sizes)
        sizes_sorted = sorted(sizes)
        gens_sorted = sorted(gens)

        rec = {
            "tick": tick,
            "n": n,
            "body_mean": statistics.fmean(sizes),
            "body_median": statistics.median(sizes),
            "q10": _quantile(sizes_sorted, 0.10),
            "q25": _quantile(sizes_sorted, 0.25),
            "q75": _quantile(sizes_sorted, 0.75),
            "q90": _quantile(sizes_sorted, 0.90),
            "p_high": sum(1 for s in sizes if s >= P_HIGH_THRESHOLD) / n,
            "g50": statistics.median(gens),
            "g90": _quantile(gens_sorted, 0.90),
            "gmax": max(gens),
        }
        for key, thr in P_LOW_THRESHOLDS.items():
            rec[key] = sum(1 for s in sizes if s <= thr) / n
        out.append(rec)

    return out


# ---------------------------------------------------------------------------
# tick-space trajectory 解析 (§8, §9)
# ---------------------------------------------------------------------------

def ols_slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(set(xs)) < 2:
        return None
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    A = np.vstack([x, np.ones_like(x)]).T
    slope, _intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(slope)


def tick_space_slopes(series: list[dict]) -> dict:
    """W1/W2/W3の正規化傾き S1,S2,S3 を計算する。"""
    result = {}
    for name, (lo, hi) in TICK_WINDOWS.items():
        pts = [(r["tick"], r["body_median"]) for r in series if lo <= r["tick"] <= hi]
        if len(pts) < 2:
            result[name] = None
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        slope = ols_slope(xs, ys)
        if slope is None:
            result[name] = None
            continue
        median_level = statistics.median(ys)
        s_norm = slope * 10000.0 / max(0.2, median_level)
        result[name] = s_norm
    return result


def deceleration_classification(s1: float | None, s2: float | None, s3: float | None) -> dict:
    """CLEAR_DECELERATION / SUSTAINED_NEGATIVE_DRIFT の判定 (§9)。"""
    out = {"clear_deceleration": False, "sustained_negative_drift": False}
    if s1 is None or s2 is None or s3 is None:
        return out

    if s1 < 0 and s2 < 0 and s3 < 0:
        if abs(s2) <= DECEL_RATIO * abs(s1) and abs(s3) <= DECEL_RATIO * abs(s2):
            out["clear_deceleration"] = True

    if (s1 < -SUSTAINED_S_THRESHOLD and s2 < -SUSTAINED_S_THRESHOLD
            and s3 < -SUSTAINED_S_THRESHOLD and abs(s3) >= SUSTAINED_RATIO * abs(s1)):
        out["sustained_negative_drift"] = True

    return out


# ---------------------------------------------------------------------------
# generation-space 解析 (§11)
# ---------------------------------------------------------------------------

def generation_space_slope(series: list[dict]) -> dict:
    """generation-late slope S_gen を計算する。

    Returns: {"s_gen": float|None, "window_insufficient": bool,
              "g50_range": (min,max)|None}
    """
    # 同じg50が連続する場合は最後のsnapshotを代表にし、増加区間だけを使う
    pts: list[tuple[float, float]] = []
    for r in series:
        g, b = r["g50"], r["body_median"]
        if pts and g <= pts[-1][0]:
            if g == pts[-1][0]:
                pts[-1] = (g, b)  # 同一g50なら最後の値で上書き
            continue  # 減少・停滞は増加区間として使わない
        pts.append((g, b))

    if len(pts) < 2:
        return {"s_gen": None, "window_insufficient": True, "g50_range": None}

    g_min, g_max = pts[0][0], pts[-1][0]
    late_start = g_min + (1 - GENERATION_LATE_FRACTION) * (g_max - g_min)
    late_pts = [(g, b) for g, b in pts if g >= late_start]

    window_width = g_max - late_start
    if window_width < GENERATION_WINDOW_MIN or len(late_pts) < 2:
        return {"s_gen": None, "window_insufficient": True, "g50_range": (g_min, g_max)}

    xs = [p[0] for p in late_pts]
    ys = [p[1] for p in late_pts]
    slope = ols_slope(xs, ys)
    if slope is None:
        return {"s_gen": None, "window_insufficient": True, "g50_range": (g_min, g_max)}

    median_level = statistics.median(ys)
    s_gen = slope * 10.0 / max(0.2, median_level)
    return {"s_gen": s_gen, "window_insufficient": False, "g50_range": (g_min, g_max)}


# ---------------------------------------------------------------------------
# 漸近平衡fit (§10)
# ---------------------------------------------------------------------------

def asymptotic_fit(series: list[dict]) -> dict:
    """b(t) = b_inf + A*exp(-(t-10000)/tau) を10k-50kのデータへfitする (variable projection)。"""
    pts = [(r["tick"], r["body_median"]) for r in series if r["tick"] >= FIRST_10K]
    if len(pts) < 4:
        return {"success": False, "reason": "insufficient_points"}

    t = np.asarray([p[0] for p in pts], dtype=float)
    y = np.asarray([p[1] for p in pts], dtype=float)
    t0 = t - FIRST_10K

    tau_grid = np.geomspace(200.0, 60000.0, 80)
    best = None
    for tau in tau_grid:
        X = np.exp(-t0 / tau)
        design = np.vstack([np.ones_like(X), X]).T
        try:
            coef, *_ = np.linalg.lstsq(design, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        b_inf, A = float(coef[0]), float(coef[1])
        if A < 0:
            # A>=0 制約: b_inf=mean(y) で近似 (減衰項なし)
            b_inf = float(np.mean(y))
            A = 0.0
        pred = b_inf + A * X
        rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
        if best is None or rmse < best["rmse"]:
            best = {"tau": float(tau), "b_inf": b_inf, "A": A, "rmse": rmse}

    if best is None:
        return {"success": False, "reason": "fit_failed"}

    level = max(0.2, float(np.median(y)))
    nrmse = best["rmse"] / level
    boundary_stuck = (
        best["b_inf"] <= FIT_B_INF_MIN + 1e-6 or best["b_inf"] >= FIT_B_INF_MAX - 1e-6
        or best["tau"] <= tau_grid[0] * 1.05 or best["tau"] >= tau_grid[-1] * 0.95
    )
    tau_unstable = best["tau"] > FIT_TAU_MAX
    success = (
        FIT_B_INF_MIN <= best["b_inf"] <= FIT_B_INF_MAX
        and best["A"] >= 0
        and not tau_unstable
        and nrmse <= FIT_NRMSE_MAX
        and not boundary_stuck
    )

    return {
        "success": success,
        "b_inf": best["b_inf"],
        "A": best["A"],
        "tau": best["tau"],
        "rmse": best["rmse"],
        "nrmse": nrmse,
        "tau_unstable": tau_unstable,
        "boundary_stuck": boundary_stuck,
    }


# ---------------------------------------------------------------------------
# Matter coupling (§12)
# ---------------------------------------------------------------------------

def _rankdata_average(a: list[float]) -> np.ndarray:
    """同順位を平均順位にする rankdata (scipy.stats.rankdata(method='average') 相当)。"""
    arr = np.asarray(a, dtype=float)
    sorter = np.argsort(arr, kind="stable")
    inv = np.empty(len(arr), dtype=int)
    inv[sorter] = np.arange(len(arr))
    sorted_arr = arr[sorter]
    is_new = np.r_[True, sorted_arr[1:] != sorted_arr[:-1]]
    dense = is_new.cumsum()[inv]
    group_start = np.r_[np.nonzero(is_new)[0], len(arr)]
    avg_rank = 0.5 * (group_start[dense - 1] + group_start[dense] - 1) + 1
    return avg_rank


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    """Spearman順位相関 rho と両側p値 (正規近似) を返す。n<4なら None。"""
    n = len(xs)
    if n < 4 or len(ys) != n:
        return None
    rx = _rankdata_average(xs)
    ry = _rankdata_average(ys)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    rho = float(np.corrcoef(rx, ry)[0, 1])
    rho = max(-1.0, min(1.0, rho))
    z = rho * math.sqrt(n - 1)
    p = 2.0 * (1.0 - _norm_cdf(abs(z)))
    return rho, p


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def matter_coupling_for_run(series: list[dict], run: dict) -> dict:
    """30k-50kのsnapshot差分から body_size と Matter/population 指標の相関を計算する。"""
    lo, hi = MATTER_COUPLING_WINDOW
    stats_by_tick = {}
    for row in run["stats"]:
        try:
            tick = int(row["tick"])
        except (KeyError, ValueError):
            continue
        stats_by_tick[tick] = row

    pts = [r for r in series if lo <= r["tick"] <= hi]
    if len(pts) < 5:
        return {"n": len(pts)}

    d_body, d_nutrient, d_biomass, d_pop = [], [], [], []
    for a, b in zip(pts, pts[1:]):
        row_a = stats_by_tick.get(a["tick"])
        row_b = stats_by_tick.get(b["tick"])
        if row_a is None or row_b is None:
            continue
        try:
            biomass_a, corpse_a, nutrient_a, pop_a = (
                float(row_a["total_biomass"]), float(row_a["corpse_matter"]),
                float(row_a["nutrient_total"]), float(row_a["population"]),
            )
            biomass_b, corpse_b, nutrient_b, pop_b = (
                float(row_b["total_biomass"]), float(row_b["corpse_matter"]),
                float(row_b["nutrient_total"]), float(row_b["population"]),
            )
        except (KeyError, ValueError):
            continue
        total_a = biomass_a + corpse_a + nutrient_a
        total_b = biomass_b + corpse_b + nutrient_b
        if total_a <= 0 or total_b <= 0:
            continue
        d_body.append(b["body_median"] - a["body_median"])
        d_nutrient.append(nutrient_b / total_b - nutrient_a / total_a)
        d_biomass.append(biomass_b / total_b - biomass_a / total_a)
        d_pop.append(pop_b - pop_a)

    out: dict = {"n": len(d_body)}
    for name, series_d in (("nutrient_fraction", d_nutrient),
                           ("biomass_fraction", d_biomass),
                           ("population", d_pop)):
        r = spearman(d_body, series_d)
        if r is None:
            out[name] = None
        else:
            rho, p = r
            out[name] = {
                "rho": rho, "p": p,
                "strong": abs(rho) >= MATTER_COUPLING_RHO_MIN and p < MATTER_COUPLING_P_MAX,
                "sign": (1 if rho > 0 else (-1 if rho < 0 else 0)),
            }
    return out


def matter_coupled_for_bmr_level(per_run_coupling: list[dict]) -> bool:
    """同一bmr水準の全runについて、同一指標・同一符号のstrong couplingが
    MATTER_COUPLING_SEED_MIN_FRAC以上のseedで揃うか。"""
    if not per_run_coupling:
        return False
    metrics = ("nutrient_fraction", "biomass_fraction", "population")
    for metric in metrics:
        by_sign: dict[int, int] = {}
        for c in per_run_coupling:
            m = c.get(metric)
            if m and m.get("strong"):
                by_sign[m["sign"]] = by_sign.get(m["sign"], 0) + 1
        if by_sign and max(by_sign.values()) >= MATTER_COUPLING_SEED_MIN_FRAC:
            return True
    return False


# ---------------------------------------------------------------------------
# per-run 科学分類 (§13)
# ---------------------------------------------------------------------------

def classify_run(status: str, s1, s2, s3, decel: dict, s_gen_info: dict,
                 late_median: float | None, late_p023: float | None) -> str:
    if status != "COMPLETE":
        return "WINDOW_INSUFFICIENT"
    if s1 is None or s2 is None or s3 is None:
        return "WINDOW_INSUFFICIENT"

    s_gen = s_gen_info["s_gen"]
    gen_insufficient = s_gen_info["window_insufficient"]

    tick_stationary = abs(s3) <= STATIONARITY_SENTINEL
    gen_stationary = (not gen_insufficient) and s_gen is not None and abs(s_gen) <= STATIONARITY_SENTINEL

    if tick_stationary and gen_stationary:
        if late_median is not None and late_p023 is not None:
            if late_median > LOWER_BOUND_SENTINEL and late_p023 < 0.50:
                return "INTERIOR_EQUILIBRIUM"
            return "LOWER_BOUND_EQUILIBRIUM"
        return "WINDOW_INSUFFICIENT"

    if decel["sustained_negative_drift"] and not gen_insufficient and s_gen is not None and s_gen < -STATIONARITY_SENTINEL:
        return "DELAY_CONTINUES"

    if decel["clear_deceleration"] and abs(s3) > STATIONARITY_SENTINEL:
        return "CONVERGING_NOT_PROVEN"
    if tick_stationary and not gen_stationary:
        return "CONVERGING_NOT_PROVEN"
    if gen_stationary and not tick_stationary:
        return "CONVERGING_NOT_PROVEN"

    if gen_insufficient:
        return "WINDOW_INSUFFICIENT"

    return "WINDOW_INSUFFICIENT"


# ---------------------------------------------------------------------------
# 収集
# ---------------------------------------------------------------------------

def collect_runs(base_dir: Path, ticks: int, tech_errors: list[str]) -> dict:
    run_dirs = sorted({p.parent for p in base_dir.rglob("config.json")})
    runs_by_key: dict[tuple[str, float, int], dict] = {}
    duplicate_keys: dict[tuple[str, float, int], list[Path]] = {}

    for rd in run_dirs:
        run = load_run(rd)
        if run is None:
            tech_errors.append(f"{rd}: config.json/meta.json/stats.csv が読み込めない")
            continue

        cfg = run["cfg"]
        try:
            env = infer_env(cfg)
        except ValueError as e:
            tech_errors.append(f"{rd}: {e}")
            continue
        core = round_bmr_any(cfg.get("bmr_core", 0.0))
        seed = run["meta"].get("seed")
        if seed is None:
            tech_errors.append(f"{rd}: meta.json に seed がない")
            continue

        status = classify_status(run, ticks)

        try:
            series = load_snapshot_series(rd)
        except AggregationError as e:
            tech_errors.append(str(e))
            series = None

        run.update({"status": status, "series": series, "env": env, "core": core, "seed": seed})

        key = (env, core, seed)
        if key in runs_by_key:
            duplicate_keys.setdefault(key, [runs_by_key[key]["path"]]).append(rd)
        else:
            runs_by_key[key] = run

    for key, paths in duplicate_keys.items():
        env, core, seed = key
        tech_errors.append(
            f"重複run: env={env} bmr_core={core:.3f} seed={seed} が {len(paths)} 件存在: "
            f"{[str(p) for p in paths]}"
        )

    expected_keys = {
        (env, core, seed)
        for env, bmrs, seeds in (("B1", B1_BMR_CORE, B1_SEEDS), ("B2", B2_BMR_CORE, B2_SEEDS))
        for core in bmrs
        for seed in seeds
    }
    found_keys = set(runs_by_key.keys())
    missing = expected_keys - found_keys
    for env, core, seed in sorted(missing):
        tech_errors.append(f"欠落run: env={env} bmr_core={core:.3f} seed={seed}")

    unexpected = found_keys - expected_keys
    for env, core, seed in sorted(unexpected):
        tech_errors.append(
            f"想定外run: env={env} bmr_core={core:.3f} seed={seed} (期待gridに含まれない)"
        )

    return runs_by_key


# ---------------------------------------------------------------------------
# per-bmr-level 集約と verdict (§14, §15, §16)
# ---------------------------------------------------------------------------

def summarize(base_dir: Path, out_dir: Path | None, ticks: int = 50000) -> int:
    tech_errors: list[str] = []
    runs_by_key = collect_runs(base_dir, ticks, tech_errors)

    print(f"=== Exp12 長期平衡解析 ({len(runs_by_key)} run 収集) ===")
    print()

    if tech_errors:
        print("=" * 60)
        print(f"★ 集計エラー ({len(tech_errors)} 件) — 技術的不完了")
        print("=" * 60)
        for e in tech_errors:
            print(f"  ERROR: {e}")
        print()
        print("SCIENTIFIC_VERDICT = UNDETERMINED (集計エラーのため未確定)")
        return 1

    per_run_records: dict[tuple[str, float, int], dict] = {}
    per_run_coupling: dict[tuple[str, float, int], dict] = {}

    for key, run in runs_by_key.items():
        series = run["series"]
        status = run["status"]
        if series is None or status != "COMPLETE":
            per_run_records[key] = {"status": status, "classification": "WINDOW_INSUFFICIENT"}
            continue

        slopes = tick_space_slopes(series)
        s1, s2, s3 = slopes["W1"], slopes["W2"], slopes["W3"]
        decel = deceleration_classification(s1, s2, s3)
        gen_info = generation_space_slope(series)
        fit = asymptotic_fit(series)

        late_pts = [r for r in series if r["tick"] >= TICK_WINDOWS["W3"][0]]
        late_median = statistics.median([r["body_median"] for r in late_pts]) if late_pts else None
        late_p023 = statistics.median([r["p_023"] for r in late_pts]) if late_pts else None

        classification = classify_run(status, s1, s2, s3, decel, gen_info, late_median, late_p023)

        coupling = matter_coupling_for_run(series, run)
        per_run_coupling[key] = coupling

        per_run_records[key] = {
            "status": status, "s1": s1, "s2": s2, "s3": s3,
            "decel": decel, "gen_info": gen_info, "fit": fit,
            "late_median": late_median, "late_p023": late_p023,
            "classification": classification,
        }

    # --- B1 baseline lower-bound signal (§14.1) ---
    baseline_pass_count = 0
    for seed in B1_SEEDS:
        rec = per_run_records.get(("B1", 0.0, seed))
        if rec is None:
            continue
        cls = rec.get("classification")
        cond = (cls == "LOWER_BOUND_EQUILIBRIUM"
               or (rec.get("late_median") is not None and rec["late_median"] <= LOWER_BOUND_SENTINEL)
               or (rec.get("late_p023") is not None and rec["late_p023"] >= 0.50))
        if cond:
            baseline_pass_count += 1
    baseline_signal_pass = baseline_pass_count >= B1_BASELINE_SEED_MIN

    # --- B1 per-bmr level: INTERIOR_EQ / DELAY / INCONCLUSIVE (§14.2-14.4) ---
    bmr_level_verdict: dict[float, str] = {}
    bmr_level_matter_coupled: dict[float, bool] = {}
    for core in B1_BMR_CORE:
        if core == 0.0:
            continue
        recs = [per_run_records.get(("B1", core, s)) for s in B1_SEEDS]
        recs = [r for r in recs if r is not None]
        interior_count = sum(1 for r in recs if r.get("classification") == "INTERIOR_EQUILIBRIUM")
        delay_count = sum(1 for r in recs if r.get("classification") == "DELAY_CONTINUES")

        if interior_count >= B1_INTERIOR_SEED_MIN and delay_count <= B1_DELAY_MAX_FOR_INTERIOR:
            bmr_level_verdict[core] = "BMR_LEVEL_INTERIOR_EQ"
        elif delay_count >= B1_DELAY_SEED_MIN:
            bmr_level_verdict[core] = "BMR_LEVEL_DELAY"
        else:
            bmr_level_verdict[core] = "BMR_LEVEL_INCONCLUSIVE"

        couplings = [per_run_coupling.get(("B1", core, s)) for s in B1_SEEDS]
        couplings = [c for c in couplings if c is not None]
        bmr_level_matter_coupled[core] = matter_coupled_for_bmr_level(couplings)

    # --- B2 method control (§15) ---
    b2_stationary_count = 0
    b2_total = 0
    for seed in B2_SEEDS:
        rec = per_run_records.get(("B2", 0.0, seed))
        if rec is None:
            continue
        b2_total += 1
        s3 = rec.get("s3")
        if s3 is not None and abs(s3) <= STATIONARITY_SENTINEL:
            b2_stationary_count += 1
    b2_control_pass = b2_stationary_count >= B2_STATIONARY_SEED_MIN

    # --- global verdict (§16) ---
    interior_levels = [c for c, v in bmr_level_verdict.items() if v == "BMR_LEVEL_INTERIOR_EQ"]
    delay_levels = [c for c, v in bmr_level_verdict.items() if v == "BMR_LEVEL_DELAY"]
    representative_delay_levels = [c for c in (0.100, 0.200, 0.300) if bmr_level_verdict.get(c) == "BMR_LEVEL_DELAY"]

    if not b2_control_pass:
        verdict = "INVALID_OR_METHOD_REVIEW"
        verdict_reason = "METHOD_CONTROL_FAIL"
    elif baseline_signal_pass and interior_levels:
        matter_coupled_any = any(bmr_level_matter_coupled.get(c) for c in interior_levels)
        verdict = ("EQUILIBRIUM_SHIFT_SUPPORTED_WITH_ECOLOGICAL_COUPLING" if matter_coupled_any
                  else "EQUILIBRIUM_SHIFT_SUPPORTED")
        verdict_reason = f"INTERIOR_EQ levels: {sorted(interior_levels)}"
    elif len(representative_delay_levels) >= 2 and not interior_levels:
        verdict = "DELAY_SUPPORTED"
        verdict_reason = f"DELAY levels (representative): {sorted(representative_delay_levels)}"
    else:
        verdict = "WINDOW_INSUFFICIENT / REVIEW"
        verdict_reason = (
            f"baseline_signal_pass={baseline_signal_pass} interior_levels={sorted(interior_levels)} "
            f"delay_levels={sorted(delay_levels)}"
        )

    # --- 出力 ---
    print("--- B1 baseline (bmr_core=0) lower-bound signal ---")
    print(f"  {baseline_pass_count}/8 -> {'PASS' if baseline_signal_pass else 'BASELINE_WINDOW_INSUFFICIENT'}")
    print()

    print("--- B1 per-bmr level verdict ---")
    for core in B1_BMR_CORE:
        if core == 0.0:
            continue
        recs = [per_run_records.get(("B1", core, s)) for s in B1_SEEDS]
        recs = [r for r in recs if r is not None]
        counts = {}
        for r in recs:
            c = r.get("classification")
            counts[c] = counts.get(c, 0) + 1
        mc = " MATTER_COUPLED" if bmr_level_matter_coupled.get(core) else ""
        print(f"  bmr_core={core:.3f}: {bmr_level_verdict[core]}{mc} ({counts})")
    print()

    print("--- B2 method control ---")
    print(f"  bmr_core=0.000 |S3|<=0.05: {b2_stationary_count}/{b2_total} -> "
          f"{'PASS' if b2_control_pass else 'METHOD_CONTROL_FAIL'}")
    print()

    print("=" * 60)
    print(f"SCIENTIFIC_VERDICT = {verdict}")
    print(f"理由: {verdict_reason}")
    print("=" * 60)

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_csvs(out_dir, per_run_records, per_run_coupling, bmr_level_verdict,
                   bmr_level_matter_coupled, verdict, verdict_reason)

    return 0


def _write_csvs(out_dir: Path, per_run_records, per_run_coupling, bmr_level_verdict,
                bmr_level_matter_coupled, verdict, verdict_reason) -> None:
    with open(out_dir / "exp12_runs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["env", "bmr_core", "seed", "status", "classification",
                   "s1", "s2", "s3", "s_gen", "late_median", "late_p023",
                   "fit_success", "fit_b_inf", "fit_tau", "fit_nrmse"])
        for (env, core, seed), rec in sorted(per_run_records.items()):
            fit = rec.get("fit", {}) or {}
            gen_info = rec.get("gen_info", {}) or {}
            w.writerow([env, f"{core:.3f}", seed, rec.get("status"), rec.get("classification"),
                       rec.get("s1"), rec.get("s2"), rec.get("s3"), gen_info.get("s_gen"),
                       rec.get("late_median"), rec.get("late_p023"),
                       fit.get("success"), fit.get("b_inf"), fit.get("tau"), fit.get("nrmse")])

    with open(out_dir / "exp12_verdict.txt", "w", encoding="utf-8") as f:
        f.write(f"SCIENTIFIC_VERDICT = {verdict}\n理由: {verdict_reason}\n")
        for core, v in sorted(bmr_level_verdict.items()):
            f.write(f"bmr_core={core:.3f}: {v} matter_coupled={bmr_level_matter_coupled.get(core)}\n")

    with open(out_dir / "exp12_matter_coupling.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["env", "bmr_core", "seed", "metric", "rho", "p", "strong"])
        for (env, core, seed), coupling in sorted(per_run_coupling.items()):
            for metric in ("nutrient_fraction", "biomass_fraction", "population"):
                m = coupling.get(metric)
                if m:
                    w.writerow([env, f"{core:.3f}", seed, metric, m["rho"], m["p"], m["strong"]])


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp12 長期平衡解析")
    ap.add_argument("base_dir", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--ticks", type=int, default=50000)
    args = ap.parse_args()

    if not args.base_dir.exists():
        print(f"ERROR: {args.base_dir} が存在しない", file=sys.stderr)
        return 1

    return summarize(args.base_dir, args.out_dir, args.ticks)


if __name__ == "__main__":
    sys.exit(main())
