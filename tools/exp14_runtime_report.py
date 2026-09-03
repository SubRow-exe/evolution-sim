"""Exp14 preflight runtime測定からformal全体wall-clockを予測する
(docs/Exp14_実験計画確定.md §9, 実装チェックリスト.md §2/11)。

FULL/COMPACT選定はここでのみ行う (科学結果では選ばない)。
formalは別dispatchで開始するため、ここでは報告のみ行い、
formalを一切起動しない。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.exp14_common import (
    COMPACT_MAX_HOURS, FULL_SELECT_MAX_HOURS, PHASE_A_JOBS, PHASE_B_JOBS,
    PHASE_C_JOBS, PROFILES, TOTAL_RUNS,
)

SAFETY_FACTOR = 1.5
SETUP_SEC_PER_JOB = 90   # checkout + uv sync + config生成
COLLECT_MIN = 20         # 全artifact download + check_exp14.py 実行


def _per_tick_rate(measured_sec: float, ticks: int) -> float:
    """tickあたり秒 (代表run実測から線形外挿する単純モデル)。"""
    return measured_sec / ticks


def predict_profile(profile: str, a_sec_2k: float, b_sec_5k: float, c_sec_2k: float,
                     max_parallel: int) -> dict:
    ticks = PROFILES[profile]
    rate_a = _per_tick_rate(a_sec_2k, 2000)
    rate_b = _per_tick_rate(b_sec_5k, 5000)
    rate_c = _per_tick_rate(c_sec_2k, 2000)

    time_a = rate_a * ticks["A"] + SETUP_SEC_PER_JOB
    time_b = rate_b * ticks["B"] + SETUP_SEC_PER_JOB
    time_c = rate_c * ticks["C"] + SETUP_SEC_PER_JOB

    def waves(n_jobs: int) -> int:
        return math.ceil(n_jobs / max_parallel)

    wave_a, wave_b, wave_c = waves(PHASE_A_JOBS), waves(PHASE_B_JOBS), waves(PHASE_C_JOBS)
    phase_wall_sec = (wave_a * time_a) + (wave_b * time_b) + (wave_c * time_c)
    collect_sec = COLLECT_MIN * 60
    total_sec = (phase_wall_sec + collect_sec) * SAFETY_FACTOR

    return {
        "profile": profile,
        "ticks": ticks,
        "per_tick_rate_sec": {"A": rate_a, "B": rate_b, "C": rate_c},
        "per_job_time_sec": {"A": time_a, "B": time_b, "C": time_c},
        "jobs": {"A": PHASE_A_JOBS, "B": PHASE_B_JOBS, "C": PHASE_C_JOBS,
                 "total": TOTAL_RUNS},
        "waves": {"A": wave_a, "B": wave_b, "C": wave_c},
        "max_parallel": max_parallel,
        "collect_estimate_sec": collect_sec,
        "safety_factor": SAFETY_FACTOR,
        "predicted_total_wall_clock_hours": round(total_sec / 3600.0, 3),
    }


def choose_profile(a_sec_2k: float, b_sec_5k: float, c_sec_2k: float,
                    max_parallel: int) -> dict:
    full = predict_profile("FULL", a_sec_2k, b_sec_5k, c_sec_2k, max_parallel)
    compact = predict_profile("COMPACT", a_sec_2k, b_sec_5k, c_sec_2k, max_parallel)

    if full["predicted_total_wall_clock_hours"] <= FULL_SELECT_MAX_HOURS:
        chosen = "FULL"
    else:
        chosen = "COMPACT"

    result = {
        "chosen_profile": chosen,
        "FULL": full,
        "COMPACT": compact,
        "full_select_max_hours": FULL_SELECT_MAX_HOURS,
        "compact_max_hours": COMPACT_MAX_HOURS,
    }
    if chosen == "COMPACT" and compact["predicted_total_wall_clock_hours"] > COMPACT_MAX_HOURS:
        result["formal_auto_start_blocked"] = True
        result["reason"] = (
            "COMPACT profileでも予測wall-clockが"
            f"{COMPACT_MAX_HOURS}時間を超過。formalを開始せず人間へ報告する。"
        )
    else:
        result["formal_auto_start_blocked"] = False
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a-2k-sec", type=float, required=True)
    ap.add_argument("--b-5k-sec", type=float, required=True)
    ap.add_argument("--c-2k-sec", type=float, required=True)
    ap.add_argument("--max-parallel", type=int, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    result = choose_profile(args.a_2k_sec, args.b_5k_sec, args.c_2k_sec, args.max_parallel)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
