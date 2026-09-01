"""Exp11 Phase B 結果集計と事前登録判定 (docs/Exp11_実験計画案.md §11)。

使い方:
    uv run python tools/summarize_exp11.py runs/exp11
    uv run python tools/summarize_exp11.py runs/exp11 --diagnostics-csv out.csv

事前登録判定順序 (§11.6):
  1. Phase 0 integrity Green (呼び出し元 check_exp11.py が担当)
  2. B1 bmr_core=0 対照妥当性 (p_low>=0.50 が 5/8 以上)
  3. B2/B3 baseline viability (healthy COMPLETE >= 3/5 and 3/4)
  4. TRANSITION_ELIGIBLE (連続 3 候補 B1 Green)
  5. B2/B3 environmental veto
  6. 最小 TRANSITION_ELIGIBLE を恒久値候補として選定

run 状態 (§9):
  COMPLETE        10,000 tick 到達
  EXTINCT         population=0
  POP_HALT        population max_population_halt 到達で安全停止
  INCOMPLETE_RESOURCE  timeout / runner 中断 / output 欠落
  INTEGRITY_FAIL  Config 等の整合性違反 (check_exp11.py が担当)

技術的集計失敗と科学的判定の分離 (2026-09-01 事故を受けた設計):
  snapshot欠落・CSV読み込み失敗・body_size列欠如・late_drift対象不足・
  run欠落・run重複は「集計エラー」(AggregationError) として扱い、
  科学的な B1_FAIL や CONTROL_NOT_REPRODUCED と混同しない。
  集計エラーが1件でもあれば SCIENTIFIC_VERDICT を確定値として出力せず、
  非0終了する (workflow はこれを技術的失敗として扱う)。
  データが揃った上での CONTROL_NOT_REPRODUCED / NO_SELECTION / REVIEW /
  environmental veto は正常な科学的結果であり、非0終了にはしない。
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

from tools.exp11_common import (
    BMR_CORE_CANDIDATES, LATE_DRIFT_WINDOW_1, LATE_DRIFT_WINDOW_2,
    P_HIGH_THRESHOLD, P_LOW_THRESHOLD, SEEDS, infer_env, read_body_sizes,
    round_core, snapshot_files,
)

B1_SEEDS = SEEDS["B1"]
B2_SEEDS = SEEDS["B2"]
B3_SEEDS = SEEDS["B3"]

# 判定しきい値 (§11)。事前登録値。ここでは変更しない。
CTRL_P_LOW_MIN = 0.50        # 対照妥当性: p_low >= 0.50
CTRL_SEED_MIN = 5            # 対照妥当性: 8 seed 中 5 以上
B1_PER_SEED_P_LOW_MAX = 0.25
B1_PER_SEED_P_HIGH_MAX = 0.25
B1_PER_SEED_LATE_DRIFT_MAX = 0.10
B1_CANDIDATE_GREEN_MIN = 7   # 8 seed 中 7 以上
TRANSITION_CONSECUTIVE = 3   # 連続 n 候補 Green で TRANSITION_ELIGIBLE

B2_BASELINE_MIN = 3          # B2 baseline healthy COMPLETE >= 3/5
B3_BASELINE_MIN = 3          # B3 baseline healthy COMPLETE >= 3/4


class AggregationError(Exception):
    """技術的な集計失敗 (snapshot欠落・読み込み失敗・run欠落/重複等)。

    科学的な B1_FAIL / CONTROL_NOT_REPRODUCED とは区別する。
    """


# ---------------------------------------------------------------------------
# run単位のデータ読み込み
# ---------------------------------------------------------------------------

def load_run(run_dir: Path) -> dict | None:
    """run ディレクトリから meta + config + stats を読み込む。

    Returns None if unreadable (技術的不完了として上位で扱う)。
    """
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


def classify_status(run: dict) -> str:
    """run の状態を分類する (§9)。

    stats.csv の最終行 (population / tick) と Config の
    max_population_halt から判定する。meta.json は起動時に1回だけ
    書かれ stop_reason 等の実行結果フィールドを持たないため、
    stats.csv 側の実測値だけで判定する。
    """
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
    if halt and pop >= halt and ticks_done < 10000:
        return "POP_HALT"

    if ticks_done >= 10000:
        return "COMPLETE"

    return "INCOMPLETE_RESOURCE"


def _quantile(sorted_vals: list[float], q: float) -> float:
    """線形補間の分位点 (numpy 依存を避けた単純実装)。"""
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


def get_body_size_dist(run_dir: Path, status: str) -> dict | None:
    """最終 snapshot (最大tick) から body_size 分布を取得する。

    EXTINCT はデータなし (正常。N/A) -> None を返す。
    COMPLETE / POP_HALT で snapshot が読めない場合は AggregationError。
    """
    if status == "EXTINCT":
        return None
    if status == "INCOMPLETE_RESOURCE":
        return None

    snaps = snapshot_files(run_dir)
    if not snaps:
        raise AggregationError(
            f"{run_dir}: status={status} なのに snapshot が1つも見つからない"
        )

    tick, path = snaps[-1]  # tick 昇順にソート済みなので最後が最大tick
    try:
        sizes = read_body_sizes(path)
    except Exception as e:
        raise AggregationError(f"{run_dir}: snapshot 読み込み失敗 ({path.name}): {e}")

    if not sizes:
        raise AggregationError(
            f"{run_dir}: 最終snapshot ({path.name}) に個体データがない "
            f"(status={status} なのに空は不整合)"
        )

    n = len(sizes)
    sizes_sorted = sorted(sizes)
    return {
        "tick": tick,
        "n": n,
        "mean": statistics.fmean(sizes),
        "median": statistics.median(sizes),
        "q10": _quantile(sizes_sorted, 0.10),
        "q25": _quantile(sizes_sorted, 0.25),
        "q75": _quantile(sizes_sorted, 0.75),
        "q90": _quantile(sizes_sorted, 0.90),
        "p_low": sum(1 for s in sizes if s <= P_LOW_THRESHOLD) / n,
        "p_high": sum(1 for s in sizes if s >= P_HIGH_THRESHOLD) / n,
    }


def get_late_drift(run_dir: Path, status: str) -> float | None:
    """COMPLETE run の late_drift を計算する (§10)。

    m1 = mean body_size over tick 6000-8000 (全snapshot・全個体をpool)
    m2 = mean body_size over tick 8000-10000
    late_drift = |m2-m1| / max(0.2, |m2|)

    対象snapshotが片方のウィンドウに1つもなければ AggregationError。
    """
    if status != "COMPLETE":
        return None

    snaps = snapshot_files(run_dir)

    def mean_in_window(lo: int, hi: int) -> float:
        vals: list[float] = []
        for tick, path in snaps:
            if lo <= tick <= hi:
                try:
                    vals.extend(read_body_sizes(path))
                except Exception as e:
                    raise AggregationError(
                        f"{run_dir}: late_drift 用 snapshot 読み込み失敗 "
                        f"(tick={tick}): {e}"
                    )
        if not vals:
            raise AggregationError(
                f"{run_dir}: late_drift 対象 snapshot が tick {lo}-{hi} に存在しない"
            )
        return statistics.fmean(vals)

    m1 = mean_in_window(*LATE_DRIFT_WINDOW_1)
    m2 = mean_in_window(*LATE_DRIFT_WINDOW_2)
    return abs(m2 - m1) / max(0.2, abs(m2))


def get_max_generation(run: dict) -> int | None:
    stats = run["stats"]
    if not stats:
        return None
    v = stats[-1].get("max_generation")
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def get_population_stats(run: dict) -> dict:
    """final / peak population, biomass_fraction, free nutrient fraction (診断用)。"""
    stats = run["stats"]
    if not stats:
        return {}
    last = stats[-1]

    def f(key, default=None):
        v = last.get(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    peak_pop = 0
    for row in stats:
        try:
            peak_pop = max(peak_pop, int(row.get("population", 0)))
        except (TypeError, ValueError):
            pass

    biomass = f("total_biomass")
    corpse = f("corpse_matter")
    nutrient = f("nutrient_total")
    total_matter = None
    biomass_fraction = None
    nutrient_fraction = None
    if biomass is not None and corpse is not None and nutrient is not None:
        total_matter = biomass + corpse + nutrient
        if total_matter > 0:
            biomass_fraction = biomass / total_matter
            nutrient_fraction = nutrient / total_matter

    return {
        "final_population": f("population"),
        "peak_population": peak_pop,
        "total_biomass": biomass,
        "corpse_matter": corpse,
        "nutrient_total": nutrient,
        "biomass_fraction": biomass_fraction,
        "free_nutrient_fraction": nutrient_fraction,
    }


# ---------------------------------------------------------------------------
# 判定関数 (事前登録 §11 の閾値・順序は変更しない)
# ---------------------------------------------------------------------------

def b1_per_seed_green(
    status: str,
    dist: dict | None,
    late_drift: float | None,
    max_gen: int | None,
    g0: int | None,
) -> bool:
    """B1 per-seed Green 判定 (§11.2)。"""
    if status != "COMPLETE":
        return False
    if dist is None:
        return False
    if dist["p_low"] >= B1_PER_SEED_P_LOW_MAX:
        return False
    if dist["p_high"] >= B1_PER_SEED_P_HIGH_MAX:
        return False
    if late_drift is None or late_drift > B1_PER_SEED_LATE_DRIFT_MAX:
        return False
    if max_gen is None:
        return False
    threshold = max(5, math.ceil(0.5 * (g0 or 0)))
    if max_gen < threshold:
        return False
    return True


# ---------------------------------------------------------------------------
# 収集
# ---------------------------------------------------------------------------

def collect_runs(base_dir: Path, tech_errors: list[str]) -> dict:
    """base_dir 以下から config.json を直接持つ全runを収集し、
    (env, core, seed) をキーとする辞書を返す。

    欠落・重複は tech_errors へ追記する (AggregationError と同格に扱う)。
    """
    run_dirs = sorted({p.parent for p in base_dir.rglob("config.json")})

    runs_by_key: dict[tuple[str, float, int], dict] = {}
    duplicate_keys: dict[tuple[str, float, int], list[Path]] = {}

    for rd in run_dirs:
        run = load_run(rd)
        if run is None:
            tech_errors.append(f"{rd}: config.json/meta.json/stats.csv が読み込めない"
                               " (INCOMPLETE_RESOURCE)")
            continue

        cfg = run["cfg"]
        core = round_core(cfg.get("bmr_core", 0.0))
        env = infer_env(cfg)
        seed = run["meta"].get("seed")
        if seed is None:
            tech_errors.append(f"{rd}: meta.json に seed がない")
            continue

        status = classify_status(run)

        try:
            dist = get_body_size_dist(rd, status)
        except AggregationError as e:
            tech_errors.append(str(e))
            dist = None
        try:
            late_drift = get_late_drift(rd, status)
        except AggregationError as e:
            tech_errors.append(str(e))
            late_drift = None

        max_gen = get_max_generation(run)
        pop_stats = get_population_stats(run)

        run.update({
            "status": status, "dist": dist, "late_drift": late_drift,
            "max_gen": max_gen, "env": env, "core": core, "seed": seed,
            "pop_stats": pop_stats,
        })

        key = (env, core, seed)
        if key in runs_by_key:
            duplicate_keys.setdefault(key, [runs_by_key[key]["path"]]).append(rd)
        else:
            runs_by_key[key] = run

    for key, paths in duplicate_keys.items():
        env, core, seed = key
        tech_errors.append(
            f"重複run: env={env} bmr_core={core:.3f} seed={seed} が "
            f"{len(paths)} 件存在: {[str(p) for p in paths]}"
        )

    # 欠落検出
    expected_keys = {
        (env, core, seed)
        for env in SEEDS
        for core in BMR_CORE_CANDIDATES
        for seed in SEEDS[env]
    }
    missing = expected_keys - set(runs_by_key.keys())
    for env, core, seed in sorted(missing):
        tech_errors.append(f"欠落run: env={env} bmr_core={core:.3f} seed={seed}")

    return runs_by_key


# ---------------------------------------------------------------------------
# 事前登録判定 (§11)
# ---------------------------------------------------------------------------

def preregistered_verdict(runs_by_key: dict, tech_errors: list[str]) -> tuple[str, dict]:
    """§11 の事前登録判定順序どおりに判定する。

    Returns:
        (verdict文字列, 詳細dict)
    """
    out: dict = {}

    # B1 bmr_core=0 の g0 (per-seed)
    g0_by_seed: dict[int, int | None] = {}
    for seed in B1_SEEDS:
        run = runs_by_key.get(("B1", 0.0, seed))
        g0_by_seed[seed] = run["max_gen"] if run else None

    # --- §11.1 B1 bmr_core=0 対照妥当性 ---
    ctrl_lines = []
    ctrl_signal_count = 0
    for seed in B1_SEEDS:
        run = runs_by_key.get(("B1", 0.0, seed))
        if run is None:
            ctrl_lines.append(f"  seed{seed}: 欠落 (集計エラー対象)")
            continue
        status = run["status"]
        dist = run["dist"]
        if dist is None:
            ctrl_lines.append(f"  seed{seed}: {status} (p_low N/A)")
            continue
        p_low = dist["p_low"]
        signal = p_low >= CTRL_P_LOW_MIN
        if signal:
            ctrl_signal_count += 1
        ctrl_lines.append(f"  seed{seed}: {status} p_low={p_low:.3f} "
                          f"{'✓' if signal else '✗'}")
    ctrl_ok = ctrl_signal_count >= CTRL_SEED_MIN
    out["ctrl_lines"] = ctrl_lines
    out["ctrl_signal_count"] = ctrl_signal_count
    out["ctrl_ok"] = ctrl_ok

    # --- §11.2 B1 candidate per-seed Green ---
    candidate_lines = []
    candidate_green: dict[float, bool] = {}
    candidate_green_count: dict[float, int] = {}
    for core in BMR_CORE_CANDIDATES:
        if core == 0.0:
            continue
        per_seed_green = []
        for seed in B1_SEEDS:
            run = runs_by_key.get(("B1", core, seed))
            if run is None:
                per_seed_green.append(False)
                continue
            g = b1_per_seed_green(
                status=run["status"], dist=run["dist"],
                late_drift=run["late_drift"], max_gen=run["max_gen"],
                g0=g0_by_seed.get(seed),
            )
            per_seed_green.append(g)
        green_count = sum(per_seed_green)
        candidate_ok = green_count >= B1_CANDIDATE_GREEN_MIN
        candidate_green[core] = candidate_ok
        candidate_green_count[core] = green_count
        candidate_lines.append(
            f"  bmr_core={core:.3f}: {green_count}/8 "
            f"{'B1_GREEN' if candidate_ok else 'B1_FAIL'}"
        )
    out["candidate_lines"] = candidate_lines
    out["candidate_green"] = candidate_green
    out["candidate_green_count"] = candidate_green_count

    # --- §11.3 TRANSITION_ELIGIBLE ---
    non_zero = [c for c in BMR_CORE_CANDIDATES if c > 0.0]
    transition_eligible: list[float] = []
    for i, c in enumerate(non_zero):
        if i + TRANSITION_CONSECUTIVE - 1 >= len(non_zero):
            break
        trio = [non_zero[i + j] for j in range(TRANSITION_CONSECUTIVE)]
        if all(candidate_green.get(t, False) for t in trio):
            if c not in transition_eligible:
                transition_eligible.append(c)
    out["transition_eligible"] = transition_eligible

    # --- §11.4 B2/B3 baseline viability ---
    def healthy_complete_count(env: str, seeds: list[int]) -> int:
        cnt = 0
        for seed in seeds:
            run = runs_by_key.get((env, 0.0, seed))
            if run and run["status"] == "COMPLETE":
                cnt += 1
        return cnt

    b2_baseline = healthy_complete_count("B2", B2_SEEDS)
    b3_baseline = healthy_complete_count("B3", B3_SEEDS)
    b2_viable = b2_baseline >= B2_BASELINE_MIN
    b3_viable = b3_baseline >= B3_BASELINE_MIN
    out.update(b2_baseline=b2_baseline, b3_baseline=b3_baseline,
               b2_viable=b2_viable, b3_viable=b3_viable)

    # --- §11.5 B2/B3 environmental veto ---
    veto_lines = []
    vetoed: set[float] = set()
    for core in transition_eligible:
        for env, seeds, h0 in [("B2", B2_SEEDS, b2_baseline),
                               ("B3", B3_SEEDS, b3_baseline)]:
            healthy_runs = [
                runs_by_key.get((env, core, s)) for s in seeds
                if runs_by_key.get((env, core, s))
                and runs_by_key[(env, core, s)]["status"] == "COMPLETE"
            ]
            hc = len(healthy_runs)
            n = len(seeds)
            veto_a = hc <= n // 2 and (h0 - hc) >= 2
            p_high_count = sum(
                1 for r in healthy_runs
                if r.get("dist") and r["dist"]["p_high"] >= 0.25
            )
            veto_b = hc > 0 and p_high_count > hc / 2
            if veto_a or veto_b:
                vetoed.add(core)
                veto_lines.append(
                    f"  bmr_core={core:.3f} VETO by {env}: "
                    f"hc={hc}/{n} h0={h0} veto_a={veto_a} veto_b={veto_b}"
                )
    if not (vetoed & set(transition_eligible)):
        veto_lines.append("  veto なし")
    out["veto_lines"] = veto_lines
    out["vetoed"] = vetoed

    # --- §11.6 恒久値選定 ---
    verdict = "NO_SELECTION / REVIEW"
    selected = None
    if not ctrl_ok:
        verdict_reason = "CONTROL_NOT_REPRODUCED"
    elif not b2_viable or not b3_viable:
        verdict_reason = "B2/B3 baseline viability 不足"
    else:
        survivors = [c for c in transition_eligible if c not in vetoed]
        if survivors:
            selected = min(survivors)
            verdict = f"SELECTED: bmr_core={selected:.3f}"
            verdict_reason = "TRANSITION_ELIGIBLE かつ veto されない最小候補"
        else:
            verdict_reason = "TRANSITION_ELIGIBLE な候補が veto 後に残らない"
    out["verdict"] = verdict
    out["verdict_reason"] = verdict_reason
    out["selected"] = selected

    return verdict, out


# ---------------------------------------------------------------------------
# 事後診断 (事前登録判定とは明確に分離。恒久値選定には使わない)
# ---------------------------------------------------------------------------

def print_diagnostics(runs_by_key: dict, out_csv: Path | None) -> None:
    print("=" * 60)
    print("事後診断 (事前登録判定とは別。恒久値選定には使用しない)")
    print("=" * 60)
    print()

    csv_rows = []

    for env in ("B1", "B2", "B3"):
        print(f"--- {env}: bmr_core 別 診断 ---")
        for core in BMR_CORE_CANDIDATES:
            seeds = SEEDS[env]
            rows = [runs_by_key.get((env, core, s)) for s in seeds]
            rows = [r for r in rows if r is not None]
            if not rows:
                print(f"  bmr_core={core:.3f}: データなし")
                continue

            means = [r["dist"]["mean"] for r in rows if r.get("dist")]
            p_lows = [r["dist"]["p_low"] for r in rows if r.get("dist")]
            p_highs = [r["dist"]["p_high"] for r in rows if r.get("dist")]
            late_drifts = [r["late_drift"] for r in rows if r.get("late_drift") is not None]
            final_pops = [r["pop_stats"].get("final_population") for r in rows
                         if r.get("pop_stats", {}).get("final_population") is not None]
            peak_pops = [r["pop_stats"].get("peak_population") for r in rows
                        if r.get("pop_stats")]
            biomass_fracs = [r["pop_stats"].get("biomass_fraction") for r in rows
                             if r.get("pop_stats", {}).get("biomass_fraction") is not None]
            statuses = [r["status"] for r in rows]

            def fmt_stat(vals):
                if not vals:
                    return "N/A"
                return (f"median={statistics.median(vals):.4f} "
                       f"range=[{min(vals):.4f},{max(vals):.4f}]")

            n_complete = sum(1 for s in statuses if s == "COMPLETE")
            print(f"  bmr_core={core:.3f}  (n={len(rows)}, COMPLETE={n_complete})")
            print(f"    body_size mean : {fmt_stat(means)}")
            print(f"    p_low          : {fmt_stat(p_lows)}")
            print(f"    p_high         : {fmt_stat(p_highs)}")
            print(f"    late_drift     : {fmt_stat(late_drifts)}")
            print(f"    final population: {fmt_stat(final_pops)}")
            print(f"    peak population : {fmt_stat(peak_pops)}")
            print(f"    biomass_fraction: {fmt_stat(biomass_fracs)}")

            for r in rows:
                dist = r.get("dist") or {}
                pop_stats = r.get("pop_stats") or {}
                csv_rows.append({
                    "env": env, "bmr_core": f"{core:.3f}", "seed": r["seed"],
                    "status": r["status"],
                    "body_size_mean": dist.get("mean"),
                    "body_size_median": dist.get("median"),
                    "body_size_q10": dist.get("q10"),
                    "body_size_q25": dist.get("q25"),
                    "body_size_q75": dist.get("q75"),
                    "body_size_q90": dist.get("q90"),
                    "p_low": dist.get("p_low"),
                    "p_high": dist.get("p_high"),
                    "late_drift": r.get("late_drift"),
                    "max_generation": r.get("max_gen"),
                    "final_population": pop_stats.get("final_population"),
                    "peak_population": pop_stats.get("peak_population"),
                    "biomass_fraction": pop_stats.get("biomass_fraction"),
                    "free_nutrient_fraction": pop_stats.get("free_nutrient_fraction"),
                })
        print()

    # B1: bmr_core - body_size 関係
    print("--- B1: bmr_core と body_size (中央値) の関係 ---")
    for core in BMR_CORE_CANDIDATES:
        rows = [runs_by_key.get(("B1", core, s)) for s in B1_SEEDS]
        rows = [r for r in rows if r and r.get("dist")]
        if not rows:
            continue
        medians = [r["dist"]["median"] for r in rows]
        print(f"  bmr_core={core:.3f}: body_size median = "
              f"{statistics.median(medians):.4f} (n={len(medians)})")
    print()

    # B2/B3: bmr_core=0 baseline に対する生態影響 (population)
    for env, seeds in (("B2", B2_SEEDS), ("B3", B3_SEEDS)):
        print(f"--- {env}: bmr_core=0 baseline に対する population 変化 ---")
        base_rows = [runs_by_key.get((env, 0.0, s)) for s in seeds]
        base_pops = [r["pop_stats"].get("final_population") for r in base_rows
                    if r and r.get("pop_stats", {}).get("final_population") is not None]
        base_median = statistics.median(base_pops) if base_pops else None
        for core in BMR_CORE_CANDIDATES:
            rows = [runs_by_key.get((env, core, s)) for s in seeds]
            pops = [r["pop_stats"].get("final_population") for r in rows
                   if r and r.get("pop_stats", {}).get("final_population") is not None]
            if not pops:
                continue
            med = statistics.median(pops)
            rel = f" (baseline比 {med / base_median:.2f}x)" if base_median else ""
            print(f"  bmr_core={core:.3f}: final population median={med:.1f}{rel}")
        print()

    if out_csv is not None and csv_rows:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"診断CSVを書き出した: {out_csv} ({len(csv_rows)} 行)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def summarize(base_dir: Path, out_csv: Path | None) -> int:
    tech_errors: list[str] = []
    runs_by_key = collect_runs(base_dir, tech_errors)

    print(f"=== Exp11 Phase B 結果集計 ({len(runs_by_key)} run 収集) ===")
    print()

    if tech_errors:
        print("=" * 60)
        print(f"★ 集計エラー ({len(tech_errors)} 件) — 技術的不完了・非INTEGRITY_FAIL")
        print("=" * 60)
        for e in tech_errors:
            print(f"  ERROR: {e}")
        print()
        print("必要な指標を計算できないため、事前登録判定 (SCIENTIFIC_VERDICT) を")
        print("確定値として出力しない。原因を解消したうえで再集計すること。")
        print()
        print("=" * 60)
        print("SCIENTIFIC_VERDICT = UNDETERMINED (集計エラーのため未確定)")
        print("=" * 60)
        return 1

    verdict, detail = preregistered_verdict(runs_by_key, tech_errors)

    print("--- §11.1 B1 bmr_core=0 対照妥当性 ---")
    for line in detail["ctrl_lines"]:
        print(line)
    print(f"  small-size signal: {detail['ctrl_signal_count']}/8 (必要: {CTRL_SEED_MIN}) "
          f"-> {'CONTROL_REPRODUCED' if detail['ctrl_ok'] else 'CONTROL_NOT_REPRODUCED'}")
    print()

    print("--- §11.2 B1 candidate per-seed Green ---")
    for line in detail["candidate_lines"]:
        print(line)
    print()

    print("--- §11.3 TRANSITION_ELIGIBLE (連続 3 候補 B1 Green) ---")
    print(f"  TRANSITION_ELIGIBLE: {detail['transition_eligible']}")
    print()

    print("--- §11.4 B2/B3 baseline viability ---")
    print(f"  B2 baseline healthy COMPLETE: {detail['b2_baseline']}/5 -> "
          f"{'OK' if detail['b2_viable'] else 'FAIL'}")
    print(f"  B3 baseline healthy COMPLETE: {detail['b3_baseline']}/4 -> "
          f"{'OK' if detail['b3_viable'] else 'FAIL'}")
    print()

    print("--- §11.5 B2/B3 environmental veto ---")
    for line in detail["veto_lines"]:
        print(line)
    print()

    print("--- §11.6 恒久値選定 ---")
    print(f"  理由: {detail['verdict_reason']}")
    print()

    print("=" * 60)
    print(f"SCIENTIFIC_VERDICT = {verdict}")
    print("=" * 60)
    print()

    print_diagnostics(runs_by_key, out_csv)

    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp11 Phase B 結果集計と事前登録判定")
    ap.add_argument("base_dir", type=Path, help="run ディレクトリの親 (例: runs/exp11)")
    ap.add_argument("--diagnostics-csv", type=Path, default=None,
                    help="事後診断の per-run 指標を CSV に書き出す (任意)")
    args = ap.parse_args()

    if not args.base_dir.exists():
        print(f"ERROR: {args.base_dir} が存在しない", file=sys.stderr)
        return 1

    return summarize(args.base_dir, args.diagnostics_csv)


if __name__ == "__main__":
    sys.exit(main())
