"""Exp11 collect/集計処理のテスト (2026-09-01 バグ修正)。

本番run #2 (33506955494) で発覚した2つのバグの回帰テスト:
  1. summarize_exp11.py が snapshot を `tick_*.json` として探していたが、
     実際は `snapshots/snap_{tick:08d}.csv` (CSV)。
  2. check_exp11.py が実行済みrunを1階層でしか探索しておらず、
     実際の2階層構造 (`runs/exp11/<条件key>/<seed dir>/config.json`) を
     全て「config.jsonが存在しない」と誤判定していた。

fixture は架空のJSON snapshotではなく、本番と同じCSV形式・
同じディレクトリ階層 (`<条件key>/<seed dir>/...`) を使う。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES
from tools import check_exp11, summarize_exp11
from tools.exp11_common import (
    BMR_CORE_CANDIDATES, SEEDS, TOTAL_RUNS, round_core, snapshot_files,
)
from tools.make_exp11_configs import build as build_config
from tools.summarize_exp11 import AggregationError, get_body_size_dist, get_late_drift

ENV_KEYS = {
    "B1": "B1_lightonly_lightspec",
    "B2": "B2_chemonly_chemspec",
    "B3": "B3_mixed_generalist",
}

SNAP_HEADER = ["id", "parent_id", "lineage_id", "generation", "age",
               "x", "y", "energy", "matter", "damage", *GENE_NAMES]


# ---------------------------------------------------------------------------
# fixture ヘルパー: 本番と同じ CSV 形式・同じディレクトリ階層を作る
# ---------------------------------------------------------------------------

def _write_snapshot(run_dir: Path, tick: int, body_sizes: list[float]) -> None:
    """本番と同じ形式 (snapshots/snap_{tick:08d}.csv) で snapshot を書く。"""
    snap_dir = run_dir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = snap_dir / f"snap_{tick:08d}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(SNAP_HEADER)
        for i, bs in enumerate(body_sizes):
            row = ["0"] * len(SNAP_HEADER)
            row[0] = str(i)  # id
            gene_start = 10
            row[gene_start] = f"{bs:.6f}"  # body_size は GENE_NAMES の先頭
            w.writerow(row)


def _write_stats(run_dir: Path, final_tick: int, population: int,
                 max_generation: int = 5, total_biomass: float = 100.0,
                 corpse_matter: float = 5.0, nutrient_total: float = 50.0) -> None:
    """最小限の stats.csv (最終行だけ意味を持たせる)。"""
    path = run_dir / "stats.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tick", "population", "max_generation",
                   "total_biomass", "corpse_matter", "nutrient_total"])
        w.writerow([final_tick, population, max_generation,
                   total_biomass, corpse_matter, nutrient_total])


def _write_meta(run_dir: Path, seed: int) -> None:
    (run_dir / "meta.json").write_text(
        json.dumps({"seed": seed, "git_sha": "deadbeef"}), encoding="utf-8"
    )


def make_run(base: Path, env_key: str, core: float, seed: int,
             final_tick: int = 10000, population: int = 100,
             snapshots: dict[int, list[float]] | None = None,
             max_generation: int = 5) -> Path:
    """本番と同じ2階層 (`<条件key>/<seed dir>/...`) で1 run を作る。"""
    cond_dir = base / f"{env_key}-bmr{core:.3f}"
    run_dir = cond_dir / f"20260901_000000_seed{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg = build_config(env_key, core)
    cfg.to_json(run_dir / "config.json")
    _write_meta(run_dir, seed)
    _write_stats(run_dir, final_tick, population, max_generation=max_generation)

    if snapshots:
        for tick, sizes in snapshots.items():
            _write_snapshot(run_dir, tick, sizes)

    return run_dir


# ---------------------------------------------------------------------------
# 1. snap_XXXXXXXX.csv から最終snapshotを選べる
# ---------------------------------------------------------------------------

def test_final_snapshot_is_max_tick(tmp_path):
    run_dir = make_run(
        tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
        snapshots={
            1000: [1.0, 1.0, 1.0],
            5000: [2.0, 2.0, 2.0],
            10000: [3.0, 3.0, 3.0],  # これが最終 (最大tick)
        },
    )
    dist = get_body_size_dist(run_dir, "COMPLETE")
    assert dist is not None
    assert dist["tick"] == 10000
    assert dist["mean"] == pytest.approx(3.0)


def test_snapshot_files_sorted_by_tick(tmp_path):
    run_dir = make_run(
        tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
        snapshots={5000: [1.0], 1000: [1.0], 10000: [1.0]},
    )
    ticks = [t for t, _ in snapshot_files(run_dir)]
    assert ticks == [1000, 5000, 10000]


# ---------------------------------------------------------------------------
# 2. CSV の body_size から p_low/p_high を正しく計算できる
# ---------------------------------------------------------------------------

def test_p_low_p_high_from_csv(tmp_path):
    # 10個体: 4個が p_low 閾値以下 (<=0.21)、3個が p_high 閾値以上 (>=9.5)
    sizes = [0.2, 0.2, 0.21, 0.15, 1.0, 2.0, 3.0, 9.5, 10.0, 9.8]
    run_dir = make_run(
        tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
        snapshots={10000: sizes},
    )
    dist = get_body_size_dist(run_dir, "COMPLETE")
    assert dist["n"] == 10
    assert dist["p_low"] == pytest.approx(4 / 10)
    assert dist["p_high"] == pytest.approx(3 / 10)
    assert dist["mean"] == pytest.approx(sum(sizes) / 10)


# ---------------------------------------------------------------------------
# 3. 複数tickのCSVからlate_driftを正しく計算できる
# ---------------------------------------------------------------------------

def test_late_drift_computed_from_multiple_snapshots(tmp_path):
    # window1 (6000-8000): 6000,7000,8000 の body_size を pool
    # window2 (8000-10000): 8000,9000,10000 の body_size を pool
    run_dir = make_run(
        tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
        snapshots={
            6000: [1.0, 1.0],
            7000: [1.0, 1.0],
            8000: [1.0, 1.0],       # 両ウィンドウに含まれる
            9000: [2.0, 2.0],
            10000: [2.0, 2.0],
        },
    )
    late_drift = get_late_drift(run_dir, "COMPLETE")
    # m1 = mean([1,1,1,1,1,1]) = 1.0  (6000,7000,8000)
    # m2 = mean([1,1,2,2,2,2]) = 1.6667  (8000,9000,10000)
    m1 = 1.0
    m2 = (1.0 + 1.0 + 2.0 + 2.0 + 2.0 + 2.0) / 6
    expected = abs(m2 - m1) / max(0.2, abs(m2))
    assert late_drift == pytest.approx(expected)


def test_late_drift_none_for_non_complete(tmp_path):
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
                       snapshots={10000: [1.0]})
    assert get_late_drift(run_dir, "EXTINCT") is None
    assert get_late_drift(run_dir, "POP_HALT") is None


# ---------------------------------------------------------------------------
# 4. 条件ディレクトリ→runディレクトリの2階層構造を checker が正しく探索できる
# ---------------------------------------------------------------------------

def test_checker_finds_run_dirs_in_two_level_structure(tmp_path):
    d1 = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1)
    d2 = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=2)
    d3 = make_run(tmp_path, ENV_KEYS["B2"], 0.005, seed=1)

    found = check_exp11.collect_run_dirs(tmp_path)
    assert set(found) == {d1, d2, d3}


# ---------------------------------------------------------------------------
# 5. condition ディレクトリを run と誤認しない
# ---------------------------------------------------------------------------

def test_condition_dir_not_treated_as_run(tmp_path):
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1)
    cond_dir = run_dir.parent

    found = check_exp11.collect_run_dirs(tmp_path)
    assert cond_dir not in found
    assert run_dir in found
    # 条件ディレクトリ直下に config.json は存在しない
    assert not (cond_dir / "config.json").exists()


# ---------------------------------------------------------------------------
# 6. COMPLETE なのに snapshot がない場合は科学的FAILではなく技術的エラーになる
# ---------------------------------------------------------------------------

def test_missing_snapshot_on_complete_run_raises_aggregation_error(tmp_path):
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
                       final_tick=10000, population=50, snapshots=None)
    with pytest.raises(AggregationError):
        get_body_size_dist(run_dir, "COMPLETE")


def test_summarize_reports_undetermined_on_missing_snapshot(tmp_path, monkeypatch):
    """collect_runs レベルでも AggregationError が tech_errors に積まれ、
    summarize() が非0終了し SCIENTIFIC_VERDICT を確定させないことを確認する。
    """
    # 小さい候補集合で高速化
    monkeypatch.setattr(summarize_exp11, "BMR_CORE_CANDIDATES", [0.000])
    monkeypatch.setattr(summarize_exp11, "SEEDS", {"B1": [1], "B2": [], "B3": []})
    monkeypatch.setattr(summarize_exp11, "B1_SEEDS", [1])
    monkeypatch.setattr(summarize_exp11, "B2_SEEDS", [])
    monkeypatch.setattr(summarize_exp11, "B3_SEEDS", [])

    base = tmp_path / "runs"
    base.mkdir()
    make_run(base, ENV_KEYS["B1"], 0.000, seed=1, final_tick=10000,
             population=50, snapshots=None)  # COMPLETE だが snapshot なし

    rc = summarize_exp11.summarize(base, None)
    assert rc == 1


# ---------------------------------------------------------------------------
# 7. 正常データでは事前登録判定が期待どおりになる
# ---------------------------------------------------------------------------

def _make_dist(p_low=0.0, p_high=0.0, mean=1.0, median=1.0, n=100):
    return {"tick": 10000, "n": n, "mean": mean, "median": median,
            "q10": mean, "q25": mean, "q75": mean, "q90": mean,
            "p_low": p_low, "p_high": p_high}


def test_preregistered_verdict_selects_min_transition_eligible(monkeypatch):
    """3候補連続 Green の最小値が TRANSITION_ELIGIBLE として選定される。"""
    small_candidates = [0.000, 0.010, 0.020, 0.030, 0.040]
    seeds_small = {"B1": [1, 2, 3, 4, 5, 6, 7, 8], "B2": [1, 2, 3], "B3": [1, 2]}
    monkeypatch.setattr(summarize_exp11, "BMR_CORE_CANDIDATES", small_candidates)
    monkeypatch.setattr(summarize_exp11, "B1_SEEDS", seeds_small["B1"])
    monkeypatch.setattr(summarize_exp11, "B2_SEEDS", seeds_small["B2"])
    monkeypatch.setattr(summarize_exp11, "B3_SEEDS", seeds_small["B3"])
    monkeypatch.setattr(summarize_exp11, "B2_BASELINE_MIN", 2)
    monkeypatch.setattr(summarize_exp11, "B3_BASELINE_MIN", 2)

    runs_by_key = {}
    # B1 bmr_core=0: 対照妥当性を満たす (p_low>=0.50 が 8/8)
    for seed in seeds_small["B1"]:
        runs_by_key[("B1", 0.000, seed)] = {
            "status": "COMPLETE", "dist": _make_dist(p_low=0.6),
            "late_drift": 0.01, "max_gen": 10,
        }
    # bmr_core=0.010,0.020,0.030 は全 seed Green (p_low/p_high 小さい、late_drift小、max_gen十分)
    for core in (0.010, 0.020, 0.030):
        for seed in seeds_small["B1"]:
            runs_by_key[("B1", core, seed)] = {
                "status": "COMPLETE", "dist": _make_dist(p_low=0.05, p_high=0.0),
                "late_drift": 0.01, "max_gen": 10,
            }
    # bmr_core=0.040 は Green にしない (p_high 大)
    for seed in seeds_small["B1"]:
        runs_by_key[("B1", 0.040, seed)] = {
            "status": "COMPLETE", "dist": _make_dist(p_low=0.05, p_high=0.9),
            "late_drift": 0.01, "max_gen": 10,
        }
    # B2/B3 baseline: healthy COMPLETE (bmr_core=0)
    for seed in seeds_small["B2"]:
        runs_by_key[("B2", 0.000, seed)] = {"status": "COMPLETE", "dist": _make_dist()}
    for seed in seeds_small["B3"]:
        runs_by_key[("B3", 0.000, seed)] = {"status": "COMPLETE", "dist": _make_dist()}
    # B2/B3 の他候補は veto されないよう健全に埋める
    for core in (0.010, 0.020, 0.030, 0.040):
        for seed in seeds_small["B2"]:
            runs_by_key[("B2", core, seed)] = {"status": "COMPLETE", "dist": _make_dist()}
        for seed in seeds_small["B3"]:
            runs_by_key[("B3", core, seed)] = {"status": "COMPLETE", "dist": _make_dist()}

    verdict, detail = summarize_exp11.preregistered_verdict(runs_by_key, [])
    assert detail["ctrl_ok"] is True
    assert detail["candidate_green"][0.010] is True
    assert detail["candidate_green"][0.020] is True
    assert detail["candidate_green"][0.030] is True
    assert detail["candidate_green"][0.040] is False
    assert detail["transition_eligible"] == [0.010]
    assert verdict == "SELECTED: bmr_core=0.010"


def test_preregistered_verdict_control_not_reproduced(monkeypatch):
    monkeypatch.setattr(summarize_exp11, "BMR_CORE_CANDIDATES", [0.000])
    monkeypatch.setattr(summarize_exp11, "B1_SEEDS", [1, 2, 3, 4, 5, 6, 7, 8])
    monkeypatch.setattr(summarize_exp11, "B2_SEEDS", [])
    monkeypatch.setattr(summarize_exp11, "B3_SEEDS", [])

    runs_by_key = {}
    for seed in range(1, 9):
        runs_by_key[("B1", 0.000, seed)] = {
            "status": "COMPLETE", "dist": _make_dist(p_low=0.05),  # 対照が再現しない
            "late_drift": 0.01, "max_gen": 10,
        }
    verdict, detail = summarize_exp11.preregistered_verdict(runs_by_key, [])
    assert detail["ctrl_ok"] is False
    assert verdict == "NO_SELECTION / REVIEW"
    assert detail["verdict_reason"] == "CONTROL_NOT_REPRODUCED"


# ---------------------------------------------------------------------------
# 8. 255 run の欠落・重複を検出できる
# ---------------------------------------------------------------------------

def test_check_run_completeness_detects_missing(tmp_path):
    # B1 bmr_core=0.000 は8 seed必要だが seed8 を欠落させる
    for seed in range(1, 8):  # 1..7 のみ
        make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=seed)
    for core in BMR_CORE_CANDIDATES[1:]:
        for seed in SEEDS["B1"]:
            make_run(tmp_path, ENV_KEYS["B1"], core, seed=seed)
    for core in BMR_CORE_CANDIDATES:
        for seed in SEEDS["B2"]:
            make_run(tmp_path, ENV_KEYS["B2"], core, seed=seed)
        for seed in SEEDS["B3"]:
            make_run(tmp_path, ENV_KEYS["B3"], core, seed=seed)

    run_dirs = check_exp11.collect_run_dirs(tmp_path)
    assert len(run_dirs) == TOTAL_RUNS - 1

    errors = check_exp11.check_run_completeness(run_dirs)
    assert any("欠落run: env=B1 bmr_core=0.000 seed=8" in e for e in errors)


def test_check_run_completeness_detects_duplicate(tmp_path):
    for core in BMR_CORE_CANDIDATES:
        for seed in SEEDS["B1"]:
            make_run(tmp_path, ENV_KEYS["B1"], core, seed=seed)
        for seed in SEEDS["B2"]:
            make_run(tmp_path, ENV_KEYS["B2"], core, seed=seed)
        for seed in SEEDS["B3"]:
            make_run(tmp_path, ENV_KEYS["B3"], core, seed=seed)

    # B1 bmr_core=0.000 seed=1 を重複させる (別の run ディレクトリ名で同じ条件)
    cond_dir = tmp_path / f"{ENV_KEYS['B1']}-bmr0.000"
    dup_dir = cond_dir / "20260901_999999_seed1_dup"
    dup_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_config(ENV_KEYS["B1"], 0.000)
    cfg.to_json(dup_dir / "config.json")
    _write_meta(dup_dir, seed=1)

    run_dirs = check_exp11.collect_run_dirs(tmp_path)
    assert len(run_dirs) == TOTAL_RUNS + 1

    errors = check_exp11.check_run_completeness(run_dirs)
    assert any("重複run: env=B1 bmr_core=0.000 seed=1" in e for e in errors)


def test_check_run_completeness_passes_when_complete(tmp_path):
    for env, key in ENV_KEYS.items():
        for core in BMR_CORE_CANDIDATES:
            for seed in SEEDS[env]:
                make_run(tmp_path, key, core, seed=seed)

    run_dirs = check_exp11.collect_run_dirs(tmp_path)
    assert len(run_dirs) == TOTAL_RUNS

    errors = check_exp11.check_run_completeness(run_dirs)
    assert errors == []


def test_collect_runs_detects_missing_via_summarize(tmp_path, monkeypatch):
    """summarize_exp11.collect_runs() 自体も欠落を tech_errors として検出する
    (check_exp11.py を経由しない防御的チェック)。
    """
    monkeypatch.setattr(summarize_exp11, "BMR_CORE_CANDIDATES", [0.000])
    monkeypatch.setattr(summarize_exp11, "SEEDS", {"B1": [1, 2], "B2": [], "B3": []})

    base = tmp_path / "runs"
    base.mkdir()
    make_run(base, ENV_KEYS["B1"], 0.000, seed=1, snapshots={10000: [1.0]})
    # seed=2 を作らない -> 欠落として検出されるはず

    tech_errors: list[str] = []
    summarize_exp11.collect_runs(base, tech_errors)
    assert any("欠落run: env=B1 bmr_core=0.000 seed=2" in e for e in tech_errors)
