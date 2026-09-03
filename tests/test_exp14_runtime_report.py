"""tools/exp14_runtime_report.py のテスト (実装チェックリスト.md §2/11)。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import exp14_runtime_report as rr


def test_choose_full_when_fast():
    result = rr.choose_profile(a_sec_2k=1.0, b_sec_5k=1.0, c_sec_2k=1.0, max_parallel=20)
    assert result["chosen_profile"] == "FULL"
    assert result["formal_auto_start_blocked"] is False


def test_choose_compact_when_full_too_slow():
    # FULLだけ9h超になるよう、Cの実測を極端に大きくする
    result = rr.choose_profile(a_sec_2k=1.0, b_sec_5k=1.0, c_sec_2k=10000.0,
                                max_parallel=1)
    assert result["FULL"]["predicted_total_wall_clock_hours"] > 9.0
    assert result["chosen_profile"] == "COMPACT"


def test_blocks_formal_when_compact_also_too_slow():
    result = rr.choose_profile(a_sec_2k=100000.0, b_sec_5k=100000.0,
                                c_sec_2k=100000.0, max_parallel=1)
    assert result["chosen_profile"] == "COMPACT"
    assert result["formal_auto_start_blocked"] is True


def test_predict_profile_job_counts_match_116():
    full = rr.predict_profile("FULL", 1.0, 1.0, 1.0, max_parallel=20)
    assert full["jobs"]["total"] == 116
    assert full["jobs"]["A"] + full["jobs"]["B"] + full["jobs"]["C"] == 116
