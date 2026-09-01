"""Exp11 Phase B 結果集計と事前登録判定 (docs/Exp11_実験計画案.md §11)。

使い方:
    uv run python tools/summarize_exp11.py runs/exp11

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
  POP_HALT        population 10,000 到達で安全停止
  INCOMPLETE_RESOURCE  timeout / runner 中断 / output 欠落
  INTEGRITY_FAIL  Config 等の整合性違反
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BMR_CORE_CANDIDATES = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

B1_SEEDS = list(range(1, 9))   # 1-8
B2_SEEDS = list(range(1, 6))   # 1-5
B3_SEEDS = list(range(1, 5))   # 1-4

# body_size 分布のカットオフ (§10)
P_LOW_THRESHOLD = 0.21   # body_size <= P_LOW_THRESHOLD -> カウント
P_HIGH_THRESHOLD = 9.5   # body_size >= P_HIGH_THRESHOLD -> カウント

# 判定しきい値 (§11)
CTRL_P_LOW_MIN = 0.50       # 対照妥当性: p_low >= 0.50
CTRL_SEED_MIN = 5            # 対照妥当性: 8 seed 中 5 以上
B1_PER_SEED_P_LOW_MAX = 0.25
B1_PER_SEED_P_HIGH_MAX = 0.25
B1_PER_SEED_LATE_DRIFT_MAX = 0.10
B1_CANDIDATE_GREEN_MIN = 7   # 8 seed 中 7 以上
TRANSITION_CONSECUTIVE = 3   # 連続 n 候補 Green で TRANSITION_ELIGIBLE

B2_BASELINE_MIN = 3          # B2 baseline healthy COMPLETE >= 3/5
B3_BASELINE_MIN = 3          # B3 baseline healthy COMPLETE >= 3/4


def _round_core(v: float) -> float:
    """浮動小数点誤差を吸収して候補値へ丸める。"""
    for c in BMR_CORE_CANDIDATES:
        if abs(v - c) < 1e-9:
            return c
    return v


def load_run(run_dir: Path) -> dict | None:
    """run ディレクトリから meta + stats の必要情報を読み込む。

    Returns None if unreadable (INCOMPLETE_RESOURCE)。
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
        import csv
        rows = []
        with open(stats_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return None

    return {"meta": meta, "cfg": cfg, "stats": rows, "path": run_dir}


def classify_status(run: dict) -> str:
    """run の状態を分類する (§9)。"""
    meta = run["meta"]
    stats = run["stats"]

    stop_reason = meta.get("stop_reason", "")
    if stop_reason == "max_population":
        return "POP_HALT"

    if not stats:
        return "INCOMPLETE_RESOURCE"

    last = stats[-1]
    try:
        pop = int(last.get("population", -1))
    except (ValueError, TypeError):
        return "INCOMPLETE_RESOURCE"

    ticks_done = int(last.get("tick", 0))

    if pop == 0:
        return "EXTINCT"
    if ticks_done >= 10000:
        return "COMPLETE"
    return "INCOMPLETE_RESOURCE"


def get_body_size_dist(run: dict, status: str) -> dict | None:
    """最終 snapshot からbody_size 分布を取得する。

    COMPLETE / POP_HALT は最終 snapshot を使う。
    EXTINCT は空 (p_low/p_high = N/A)。
    """
    if status == "EXTINCT":
        return None

    snap_dir = run["path"] / "snapshots"
    if not snap_dir.exists():
        return None

    snaps = sorted(snap_dir.glob("tick_*.json"))
    if not snaps:
        return None

    final_snap = snaps[-1]
    try:
        data = json.loads(final_snap.read_text(encoding="utf-8"))
    except Exception:
        return None

    body_sizes = [o.get("body_size", o.get("genome", {}).get("body_size", None))
                  for o in data.get("organisms", [])]
    body_sizes = [b for b in body_sizes if b is not None]

    if not body_sizes:
        return None

    n = len(body_sizes)
    p_low = sum(1 for b in body_sizes if b <= P_LOW_THRESHOLD) / n
    p_high = sum(1 for b in body_sizes if b >= P_HIGH_THRESHOLD) / n

    return {
        "n": n,
        "mean": sum(body_sizes) / n,
        "p_low": p_low,
        "p_high": p_high,
    }


def get_late_drift(run: dict, status: str) -> float | None:
    """COMPLETE run の late_drift を計算する (§10)。

    m1 = mean body_size over tick 6000-8000
    m2 = mean body_size over tick 8000-10000
    late_drift = |m2-m1| / max(0.2, |m2|)
    """
    if status != "COMPLETE":
        return None

    snap_dir = run["path"] / "snapshots"
    if not snap_dir.exists():
        return None

    snaps = sorted(snap_dir.glob("tick_*.json"))

    def mean_body_size_in_range(lo: int, hi: int) -> float | None:
        vals = []
        for s in snaps:
            try:
                tick = int(s.stem.split("_")[1])
            except Exception:
                continue
            if lo <= tick <= hi:
                try:
                    data = json.loads(s.read_text(encoding="utf-8"))
                    for o in data.get("organisms", []):
                        b = o.get("body_size", o.get("genome", {}).get("body_size", None))
                        if b is not None:
                            vals.append(b)
                except Exception:
                    pass
        return sum(vals) / len(vals) if vals else None

    m1 = mean_body_size_in_range(6000, 8000)
    m2 = mean_body_size_in_range(8000, 10000)
    if m1 is None or m2 is None:
        return None

    return abs(m2 - m1) / max(0.2, abs(m2))


def get_max_generation(run: dict) -> int | None:
    """stats.csv から max_generation を取得する。"""
    stats = run["stats"]
    if not stats:
        return None
    last = stats[-1]
    v = last.get("max_generation")
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 判定関数
# ---------------------------------------------------------------------------

def b1_per_seed_green(
    status: str,
    dist: dict | None,
    late_drift: float | None,
    max_gen: int | None,
    g0: int | None,
    integrity_ok: bool,
) -> bool:
    """B1 per-seed Green 判定 (§11.2)。"""
    if not integrity_ok:
        return False
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


def summarize(base_dir: Path) -> int:
    """全 run を収集して事前登録判定を行う。"""
    # run ディレクトリ収集 (base_dir の子 or 孫)
    run_dirs: list[Path] = []
    for child in sorted(base_dir.iterdir()):
        if child.is_dir():
            # 子が run ディレクトリ (config.json を持つ) か、その親か
            if (child / "config.json").exists():
                run_dirs.append(child)
            else:
                for grandchild in sorted(child.iterdir()):
                    if grandchild.is_dir() and (grandchild / "config.json").exists():
                        run_dirs.append(grandchild)

    print(f"=== Exp11 Phase B 結果集計 ({len(run_dirs)} run ディレクトリ) ===")
    print()

    # run データを読み込む
    runs_by_key: dict[tuple[str, float, int], dict | None] = {}
    for rd in run_dirs:
        run = load_run(rd)
        if run is None:
            # INCOMPLETE_RESOURCE
            # ディレクトリ名から key を推定するのは難しいのでスキップ
            print(f"  INCOMPLETE_RESOURCE (読み込み失敗): {rd.name}")
            continue
        cfg = run["cfg"]
        core = _round_core(cfg.get("bmr_core", 0.0))
        seed = run["meta"].get("seed", -1)

        # 環境を推定
        placement = cfg.get("diagnostic_placement", "random")
        light_max = cfg.get("light_max", 1.2)
        chem_flux = cfg.get("chem_vent_flux", 0.0)
        if light_max <= 0:
            env = "B2"
        elif chem_flux <= 0:
            env = "B1"
        else:
            env = "B3"

        status = classify_status(run)
        dist = get_body_size_dist(run, status)
        late_drift = get_late_drift(run, status)
        max_gen = get_max_generation(run)

        run["status"] = status
        run["dist"] = dist
        run["late_drift"] = late_drift
        run["max_gen"] = max_gen
        run["env"] = env
        run["core"] = core
        run["seed"] = seed
        runs_by_key[(env, core, seed)] = run

    # B1 bmr_core=0 の g0 を取得 (per-seed)
    g0_by_seed: dict[int, int | None] = {}
    for seed in B1_SEEDS:
        key = ("B1", 0.0, seed)
        run = runs_by_key.get(key)
        if run:
            g0_by_seed[seed] = run["max_gen"]
        else:
            g0_by_seed[seed] = None

    # ---------------------------------------------------------------------------
    # 11.1 B1 bmr_core=0 対照妥当性
    # ---------------------------------------------------------------------------
    print("--- §11.1 B1 bmr_core=0 対照妥当性 ---")
    ctrl_signal_count = 0
    for seed in B1_SEEDS:
        run = runs_by_key.get(("B1", 0.0, seed))
        if run is None:
            print(f"  seed{seed}: INCOMPLETE_RESOURCE")
            continue
        status = run["status"]
        dist = run["dist"]
        if dist is None:
            if status in ("EXTINCT",):
                print(f"  seed{seed}: {status} (p_low N/A)")
            else:
                print(f"  seed{seed}: {status} (snapshot なし)")
            continue
        p_low = dist["p_low"]
        signal = p_low >= CTRL_P_LOW_MIN
        if signal:
            ctrl_signal_count += 1
        print(f"  seed{seed}: {status} p_low={p_low:.3f} {'✓' if signal else '✗'}")

    ctrl_ok = ctrl_signal_count >= CTRL_SEED_MIN
    print(f"  small-size signal: {ctrl_signal_count}/8 (必要: {CTRL_SEED_MIN}) "
          f"-> {'CONTROL_REPRODUCED' if ctrl_ok else 'CONTROL_NOT_REPRODUCED'}")
    print()

    # ---------------------------------------------------------------------------
    # 11.2 B1 candidate per-seed Green
    # ---------------------------------------------------------------------------
    print("--- §11.2 B1 candidate per-seed Green ---")
    candidate_green: dict[float, bool] = {}
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
                status=run["status"],
                dist=run["dist"],
                late_drift=run["late_drift"],
                max_gen=run["max_gen"],
                g0=g0_by_seed.get(seed),
                integrity_ok=True,  # 整合性は check_exp11.py が確認済み前提
            )
            per_seed_green.append(g)
        green_count = sum(per_seed_green)
        candidate_ok = green_count >= B1_CANDIDATE_GREEN_MIN
        candidate_green[core] = candidate_ok
        print(f"  bmr_core={core:.3f}: {green_count}/8 {'B1_GREEN' if candidate_ok else 'B1_FAIL'}")
    print()

    # ---------------------------------------------------------------------------
    # §11.3 持続的転換 (連続 3 候補 B1 Green)
    # ---------------------------------------------------------------------------
    print("--- §11.3 TRANSITION_ELIGIBLE (連続 3 候補 B1 Green) ---")
    non_zero = [c for c in BMR_CORE_CANDIDATES if c > 0.0]
    transition_eligible: list[float] = []
    for i, c in enumerate(non_zero):
        if i + TRANSITION_CONSECUTIVE - 1 >= len(non_zero):
            break
        trio = [non_zero[i + j] for j in range(TRANSITION_CONSECUTIVE)]
        if all(candidate_green.get(t, False) for t in trio):
            if c not in transition_eligible:
                transition_eligible.append(c)
    print(f"  TRANSITION_ELIGIBLE: {transition_eligible}")
    print()

    # ---------------------------------------------------------------------------
    # §11.4 B2/B3 baseline viability
    # ---------------------------------------------------------------------------
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
    print("--- §11.4 B2/B3 baseline viability ---")
    print(f"  B2 baseline healthy COMPLETE: {b2_baseline}/5 -> {'OK' if b2_viable else 'FAIL'}")
    print(f"  B3 baseline healthy COMPLETE: {b3_baseline}/4 -> {'OK' if b3_viable else 'FAIL'}")
    print()

    # ---------------------------------------------------------------------------
    # §11.5 B2/B3 environmental veto
    # ---------------------------------------------------------------------------
    print("--- §11.5 B2/B3 environmental veto ---")
    vetoed: set[float] = set()
    for core in transition_eligible:
        for env, seeds, h0 in [("B2", B2_SEEDS, b2_baseline), ("B3", B3_SEEDS, b3_baseline)]:
            hc = sum(
                1 for s in seeds
                if runs_by_key.get((env, core, s), {}) and
                runs_by_key[(env, core, s)]["status"] == "COMPLETE"
            )
            n = len(seeds)
            veto_a = hc <= n // 2 and (h0 - hc) >= 2
            # p_high の過半数条件
            healthy_runs = [
                runs_by_key.get((env, core, s))
                for s in seeds
                if runs_by_key.get((env, core, s), {}) and
                runs_by_key[(env, core, s)]["status"] == "COMPLETE"
            ]
            p_high_count = sum(
                1 for r in healthy_runs
                if r and r.get("dist") and r["dist"]["p_high"] >= 0.25
            )
            veto_b = len(healthy_runs) > 0 and p_high_count > len(healthy_runs) / 2

            if veto_a or veto_b:
                vetoed.add(core)
                print(f"  bmr_core={core:.3f} VETO by {env}: "
                      f"hc={hc}/{n} h0={h0} veto_a={veto_a} veto_b={veto_b}")
    if not vetoed & set(transition_eligible):
        print("  veto なし")
    print()

    # ---------------------------------------------------------------------------
    # §11.6 恒久値選定
    # ---------------------------------------------------------------------------
    print("--- §11.6 恒久値選定 ---")
    verdict = "NO_SELECTION / REVIEW"
    selected = None

    if not ctrl_ok:
        print(f"  CONTROL_NOT_REPRODUCED -> {verdict}")
    elif not b2_viable or not b3_viable:
        print(f"  B2/B3 baseline viability 不足 -> {verdict}")
    else:
        survivors = [c for c in transition_eligible if c not in vetoed]
        if survivors:
            selected = min(survivors)
            verdict = f"SELECTED: bmr_core={selected:.3f}"
        print(f"  TRANSITION_ELIGIBLE: {transition_eligible}")
        print(f"  veto後: {survivors}")
        print(f"  SCIENTIFIC_VERDICT = {verdict}")

    print()
    print(f"{'='*60}")
    print(f"SCIENTIFIC_VERDICT = {verdict}")
    print(f"{'='*60}")

    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp11 Phase B 結果集計と事前登録判定")
    ap.add_argument("base_dir", type=Path, help="run ディレクトリの親 (例: runs/exp11)")
    args = ap.parse_args()

    if not args.base_dir.exists():
        print(f"ERROR: {args.base_dir} が存在しない", file=sys.stderr)
        return 1

    return summarize(args.base_dir)


if __name__ == "__main__":
    sys.exit(main())
