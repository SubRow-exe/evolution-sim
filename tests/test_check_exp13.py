"""tools/check_exp13.py のテスト (docs/数値再現性・Actions実行環境方針.md,
V1.8_実装チェックリスト.md)。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import check_exp13
from tools.make_exp13_configs import build_a1

STATS_FIELDS = ["tick", "population", "total_biomass"]


def _write_stats_rows(run_dir: Path, rows: list[dict]) -> None:
    with open(run_dir / "stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATS_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _write_meta(run_dir: Path, seed: int, git_sha="sha-A", env_key="env-A") -> None:
    meta = {"seed": seed, "git_sha": git_sha, "numeric_environment": {"env_key": env_key}}
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _default_rows():
    return [{"tick": t, "population": 50, "total_biomass": 10.0} for t in range(0, 2001, 500)]


def _stock_run(run_dir: Path, seed=1, **meta_kwargs) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    build_a1(1.8).to_json(run_dir / "config.json")
    _write_meta(run_dir, seed, **meta_kwargs)
    _write_stats_rows(run_dir, _default_rows())
    return run_dir


def test_check_phase_a_configs_ok():
    errors = check_exp13.check_phase_a_configs()
    assert errors == []


def test_compare_first_2k_identical_match(tmp_path):
    a = _stock_run(tmp_path / "a")
    b = _stock_run(tmp_path / "b")
    errors = check_exp13.compare_first_2k(a, b, max_tick=2000)
    assert errors == []


def test_compare_first_2k_mismatch_detected(tmp_path):
    a = _stock_run(tmp_path / "a")
    b_dir = tmp_path / "b"
    b_dir.mkdir(parents=True)
    build_a1(1.8).to_json(b_dir / "config.json")
    _write_meta(b_dir, 1)
    rows = _default_rows()
    rows[1]["total_biomass"] = 999.0
    _write_stats_rows(b_dir, rows)
    errors = check_exp13.compare_first_2k(a, b_dir, max_tick=2000)
    assert errors
    assert any("total_biomass" in e for e in errors)


def test_environment_integrity_all_same_passes(tmp_path):
    dirs = [_stock_run(tmp_path / f"r{i}", seed=i) for i in range(1, 4)]
    errors = check_exp13.check_run_environment_integrity(dirs)
    assert errors == []


def test_environment_integrity_detects_sha_mismatch(tmp_path):
    dirs = [
        _stock_run(tmp_path / "r1", seed=1, git_sha="sha-A"),
        _stock_run(tmp_path / "r2", seed=2, git_sha="sha-B"),
    ]
    errors = check_exp13.check_run_environment_integrity(dirs)
    assert any("git_sha" in e for e in errors)


def test_environment_integrity_detects_env_key_mismatch(tmp_path):
    dirs = [
        _stock_run(tmp_path / "r1", seed=1, env_key="env-A"),
        _stock_run(tmp_path / "r2", seed=2, env_key="env-B"),
    ]
    errors = check_exp13.check_run_environment_integrity(dirs)
    assert any("numeric_environment" in e for e in errors)
