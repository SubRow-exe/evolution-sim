"""Exp14 結果集計 (docs/Exp14_実験計画確定.md §6/7/8, 実装チェックリスト.md)。

run status vocabulary (AGENTS.md §10):
  COMPLETE / EXTINCT / POP_HALT / SCIENTIFIC_STOP_REVIEW /
  INCOMPLETE_RESOURCE / INTEGRITY_FAIL

科学的結果 (COMPLETE/EXTINCT/POP_HALT/SCIENTIFIC_STOP_REVIEW) と
技術的失敗 (INCOMPLETE_RESOURCE/INTEGRITY_FAIL) は必ず分離したフィールドで
報告する。late window未到達は明示的にNoneとして扱い、PASS/FAIL集計へ
混入させない (Exp13のlate_pop_ok誤PASSバグの修正)。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from tools.exp14_common import (
    classify_phase_a_arm, cycle_observation_from_rows,
    daylight_births_and_night_starvation, late_window_metric, r_ref_for_arm,
)

TECHNICAL_STATUSES = {"INCOMPLETE_RESOURCE", "INTEGRITY_FAIL"}
SCIENTIFIC_STATUSES = {"COMPLETE", "EXTINCT", "POP_HALT", "SCIENTIFIC_STOP_REVIEW"}


def _load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_status(run_dir: Path, expected_ticks: int) -> tuple[str, str]:
    """(scientific_or_technical, status) を返す。

    - stats.csv/config.json/meta.jsonが揃わない -> ("technical", "INTEGRITY_FAIL")
    - meta.jsonのincomplete markerがあれば -> ("technical", "INCOMPLETE_RESOURCE")
    - population==0で終了 -> ("scientific", "EXTINCT")
    - max_population_halt到達 -> ("scientific", "POP_HALT")
    - それ以外で最終tick==expected_ticks -> ("scientific", "COMPLETE")
    - 途中で終わっているが技術的原因が特定できない -> ("technical", "INCOMPLETE_RESOURCE")
    """
    cfg_path = run_dir / "config.json"
    meta_path = run_dir / "meta.json"
    stats_path = run_dir / "stats.csv"
    if not (cfg_path.exists() and meta_path.exists() and stats_path.exists()):
        return "technical", "INTEGRITY_FAIL"

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return "technical", "INTEGRITY_FAIL"
    if meta.get("incomplete_resource"):
        return "technical", "INCOMPLETE_RESOURCE"

    rows = _load_csv_rows(stats_path)
    if not rows:
        return "technical", "INTEGRITY_FAIL"

    final_tick = int(rows[-1]["tick"])
    final_pop = int(rows[-1]["population"])
    try:
        cfg = Config.from_json(cfg_path)
    except Exception:
        return "technical", "INTEGRITY_FAIL"

    if final_pop == 0:
        return "scientific", "EXTINCT"
    if cfg.max_population_halt and final_pop >= cfg.max_population_halt:
        return "scientific", "POP_HALT"
    if final_tick >= expected_ticks:
        return "scientific", "COMPLETE"
    # 期待tickへ届かず、EXTINCT/POP_HALTでもない: 原因不明の途中終了
    return "technical", "INCOMPLETE_RESOURCE"


def summarize_phase_a_run(run_dir: Path, expected_ticks: int, late_window: int) -> dict:
    kind, status = run_status(run_dir, expected_ticks)
    result = {"run_dir": str(run_dir), "kind": kind, "status": status}
    if kind != "scientific":
        return result

    rows = _load_csv_rows(run_dir / "stats.csv")
    final_tick = int(rows[-1]["tick"])
    final_pop = int(rows[-1]["population"])
    result["final_tick"] = final_tick
    result["final_population"] = final_pop
    result["reached_full_ticks"] = final_tick >= expected_ticks

    # late window: N/A semantics (Exp13バグ修正)
    late_pop = late_window_metric(rows, final_tick, late_window, "population", agg="mean")
    result["late_population_mean"] = late_pop  # None なら N/A

    cyc = cycle_observation_from_rows(rows, Config.from_json(run_dir / "config.json"))
    result.update(cyc)
    events = _load_csv_rows(run_dir / "events.csv")
    result.update(daylight_births_and_night_starvation(
        events, Config.from_json(run_dir / "config.json")))
    return result


def summarize_phase_a(base_dir: Path, arm_overrides: dict, expected_ticks: int,
                       late_window: int) -> dict:
    from tools.exp14_common import A_ARM_NAMES, PHASE_A_SEEDS
    from tools.make_exp14_configs import phase_a_config_name

    out = {}
    for arm in A_ARM_NAMES:
        seed_results = []
        for seed in PHASE_A_SEEDS:
            name = phase_a_config_name(arm, seed).replace(".json", "")
            run_dir = base_dir / name
            seed_results.append(summarize_phase_a_run(run_dir, expected_ticks, late_window))
        scientific = [r for r in seed_results if r["kind"] == "scientific"]
        classification = None
        if len(scientific) == len(seed_results):
            classification = classify_phase_a_arm(scientific)
        out[arm] = {
            "seed_results": seed_results,
            "classification": classification,  # Noneなら技術fail混在で判定不能
            "predicted_r_ref": r_ref_for_arm(arm_overrides.get(arm, {})),
            "n_technical_fail": sum(1 for r in seed_results if r["kind"] == "technical"),
        }
    return out


def main() -> int:
    import argparse
    from tools.exp14_common import PHASE_A_ARMS

    ap = argparse.ArgumentParser(description="Exp14 Phase A 結果集計")
    ap.add_argument("run_dir", type=Path, help="Phase A run群の親ディレクトリ")
    ap.add_argument("--ticks", type=int, default=2000)
    ap.add_argument("--late-window", type=int, default=500)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    result = summarize_phase_a(args.run_dir, PHASE_A_ARMS, args.ticks, args.late_window)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
