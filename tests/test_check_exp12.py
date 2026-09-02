"""tools/check_exp12.py のテスト (docs/数値再現性・Actions実行環境方針.md,
Exp12_実装チェックリスト.md §4 9〜12)。

`compare_first_10k` はどのrun同士を比較するかを知らない汎用関数であり、
その用途 (現在環境内比較=HARD GATE / 過去artifact比較=DIAGNOSTIC) は
呼び出し側 (.github/workflows/exp12.yml) が決める。ここではその汎用関数と
`check_run_environment_integrity` (formal SHA / numeric environment整合性)
の動作を、本番と同じCSV形式のfixtureで検証する。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES
from tools import check_exp12
from tools.make_exp12_configs import build as build_config

SNAP_HEADER = ["id", "parent_id", "lineage_id", "generation", "age",
               "x", "y", "energy", "matter", "damage", *GENE_NAMES]

STATS_FIELDS = ["tick", "population", "total_biomass", "corpse_matter", "nutrient_total"]


def _write_stats_rows(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "stats.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATS_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _write_snapshot(run_dir: Path, tick: int, body_sizes: list[float]) -> None:
    snap_dir = run_dir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = snap_dir / f"snap_{tick:08d}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(SNAP_HEADER)
        for i, bs in enumerate(body_sizes):
            row = ["0"] * len(SNAP_HEADER)
            row[0] = str(i)
            row[3] = "1"
            row[10] = f"{bs:.6f}"
            w.writerow(row)


def _write_meta(run_dir: Path, seed: int, git_sha: str = "abc123",
                env_key: str = "linux-x86_64-glibc2.35-py3.12.0-np1.26.0") -> None:
    meta = {
        "seed": seed,
        "git_sha": git_sha,
        "numeric_environment": {"env_key": env_key},
    }
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _stock_run(run_dir: Path, tick_rows: list[dict], snapshot_ticks: list[int],
               body_sizes: list[float], seed: int = 1, **meta_kwargs) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_config("B1_lightonly_lightspec", 0.100)
    cfg.to_json(run_dir / "config.json")
    _write_meta(run_dir, seed, **meta_kwargs)
    _write_stats_rows(run_dir, tick_rows)
    for t in snapshot_ticks:
        _write_snapshot(run_dir, t, body_sizes)
    return run_dir


def _default_rows(n: int = 5, step: int = 2000) -> list[dict]:
    return [
        {"tick": t, "population": 100 + t, "total_biomass": 50.0,
         "corpse_matter": 1.0, "nutrient_total": 10.0}
        for t in range(step, step * (n + 1), step)
    ]


# ---------------------------------------------------------------------------
# 9. current-run referenceとのfirst-10k mismatch -> HARD STOP (compare_first_10kが空でないerrorsを返す)
# ---------------------------------------------------------------------------

def test_compare_first_10k_identical_runs_match(tmp_path):
    rows = _default_rows()
    a = _stock_run(tmp_path / "a", rows, [2000, 4000], [0.2, 0.3, 0.4])
    b = _stock_run(tmp_path / "b", rows, [2000, 4000], [0.2, 0.3, 0.4])
    errors = check_exp12.compare_first_10k(a, b, max_tick=10000)
    assert errors == []


def test_compare_first_10k_stats_mismatch_detected(tmp_path):
    rows_a = _default_rows()
    rows_b = _default_rows()
    rows_b[2]["total_biomass"] = 999.0  # 中間tickで数値が分岐 (実際の事象を模す)
    a = _stock_run(tmp_path / "a", rows_a, [], [])
    b = _stock_run(tmp_path / "b", rows_b, [], [])
    errors = check_exp12.compare_first_10k(a, b, max_tick=10000)
    assert errors, "分岐があればHARD STOP対象のerrorsが返るべき"
    assert any("total_biomass" in e for e in errors)


def test_compare_first_10k_snapshot_mismatch_detected(tmp_path):
    rows = _default_rows()
    a = _stock_run(tmp_path / "a", rows, [2000], [0.2, 0.3])
    b = _stock_run(tmp_path / "b", rows, [2000], [0.2, 0.35])  # body_size分岐
    errors = check_exp12.compare_first_10k(a, b, max_tick=10000)
    assert any("snapshot" in e for e in errors)


def test_compare_first_10k_missing_snapshot_tick_detected(tmp_path):
    rows = _default_rows()
    a = _stock_run(tmp_path / "a", rows, [2000, 4000], [0.2])
    b = _stock_run(tmp_path / "b", rows, [2000], [0.2])
    errors = check_exp12.compare_first_10k(a, b, max_tick=10000)
    assert any("snapshot tick集合不一致" in e for e in errors)


# ---------------------------------------------------------------------------
# 10. current-run reference欠落 -> 技術エラー
# ---------------------------------------------------------------------------

def test_compare_first_10k_missing_reference_dir(tmp_path):
    rows = _default_rows()
    a = _stock_run(tmp_path / "a", rows, [], [])
    missing = tmp_path / "does_not_exist"
    errors = check_exp12.compare_first_10k(a, missing, max_tick=10000)
    assert errors and "stats.csv" in errors[0]


# ---------------------------------------------------------------------------
# 11. historical Exp11 reference mismatchはdiagnosticでありformal verdictを
#     直接failureにしない (= compare_first_10kはただerrorsを返すだけで、
#     どう扱うか (HARD GATE か DIAGNOSTIC か) は呼び出し側の責務であることを確認)
# ---------------------------------------------------------------------------

def test_compare_first_10k_is_a_pure_reporting_function(tmp_path):
    """compare_first_10k自体はexit codeやHARD STOP判定を持たない
    (呼び出し側がcurrent-run比較かhistorical比較かで扱いを分けられることの保証)。"""
    rows_a = _default_rows()
    rows_b = _default_rows()
    rows_b[0]["population"] = -1  # 明確な不一致
    a = _stock_run(tmp_path / "a", rows_a, [], [])
    b = _stock_run(tmp_path / "b", rows_b, [], [])
    errors = check_exp12.compare_first_10k(a, b, max_tick=10000)
    # 例外を投げず、errorsのリストとして返す。呼び出し側はhistorical比較なら
    # このerrorsをDIAGNOSTICとして記録するだけでformal verdictを失敗させない、
    # current-run比較ならHARD STOPとして扱う、を選べる。
    assert isinstance(errors, list)
    assert errors


# ---------------------------------------------------------------------------
# 12. formal SHA / numeric environment混在をintegrity errorにする
# ---------------------------------------------------------------------------

def test_environment_integrity_all_same_passes(tmp_path):
    rows = _default_rows()
    dirs = [
        _stock_run(tmp_path / f"r{i}", rows, [], [], seed=i,
                  git_sha="sha-fixed", env_key="linux-x86_64-py3.12-np1.26")
        for i in range(1, 4)
    ]
    errors = check_exp12.check_run_environment_integrity(dirs)
    assert errors == []


def test_environment_integrity_detects_sha_mismatch(tmp_path):
    rows = _default_rows()
    dirs = [
        _stock_run(tmp_path / "r1", rows, [], [], seed=1, git_sha="sha-A"),
        _stock_run(tmp_path / "r2", rows, [], [], seed=2, git_sha="sha-B"),
    ]
    errors = check_exp12.check_run_environment_integrity(dirs)
    assert any("git_sha" in e for e in errors)


def test_environment_integrity_detects_numeric_env_mismatch(tmp_path):
    rows = _default_rows()
    dirs = [
        _stock_run(tmp_path / "r1", rows, [], [], seed=1, env_key="env-A"),
        _stock_run(tmp_path / "r2", rows, [], [], seed=2, env_key="env-B"),
    ]
    errors = check_exp12.check_run_environment_integrity(dirs)
    assert any("numeric_environment" in e for e in errors)


def test_environment_integrity_detects_missing_fields(tmp_path):
    run_dir = tmp_path / "r1"
    run_dir.mkdir()
    cfg = build_config("B1_lightonly_lightspec", 0.100)
    cfg.to_json(run_dir / "config.json")
    (run_dir / "meta.json").write_text(json.dumps({"seed": 1}), encoding="utf-8")
    _write_stats_rows(run_dir, _default_rows())
    errors = check_exp12.check_run_environment_integrity([run_dir])
    assert any("git_sha" in e for e in errors)
    assert any("numeric_environment" in e for e in errors)


# ---------------------------------------------------------------------------
# check_run_completeness / collect_run_dirs (既存機能の回帰確認)
# ---------------------------------------------------------------------------

def test_check_run_completeness_detects_duplicate(tmp_path):
    from tools.exp12_common import B1_BMR_CORE, B1_SEEDS, B2_BMR_CORE, B2_SEEDS

    base = tmp_path / "runs"
    rows = _default_rows()
    dirs = []
    for core in B1_BMR_CORE:
        for seed in B1_SEEDS:
            run_dir = base / f"B1_lightonly_lightspec-bmr{core:.3f}" / f"s{seed}"
            run_dir.mkdir(parents=True)
            cfg = build_config("B1_lightonly_lightspec", core)
            cfg.to_json(run_dir / "config.json")
            _write_meta(run_dir, seed)
            _write_stats_rows(run_dir, rows)
            dirs.append(run_dir)
    for core in B2_BMR_CORE:
        for seed in B2_SEEDS:
            run_dir = base / f"B2_chemonly_chemspec-bmr{core:.3f}" / f"s{seed}"
            run_dir.mkdir(parents=True)
            cfg = build_config("B2_chemonly_chemspec", core)
            cfg.to_json(run_dir / "config.json")
            _write_meta(run_dir, seed)
            _write_stats_rows(run_dir, rows)
            dirs.append(run_dir)

    # 完全な71件ではエラーなし
    errors = check_exp12.check_run_completeness(dirs)
    assert errors == []

    # 重複runを1件追加
    dup_dir = base / "B1_lightonly_lightspec-bmr0.000" / "s1_dup"
    dup_dir.mkdir(parents=True)
    cfg = build_config("B1_lightonly_lightspec", 0.000)
    cfg.to_json(dup_dir / "config.json")
    _write_meta(dup_dir, seed=1)
    _write_stats_rows(dup_dir, rows)
    errors2 = check_exp12.check_run_completeness(dirs + [dup_dir])
    assert any("重複run" in e for e in errors2)
