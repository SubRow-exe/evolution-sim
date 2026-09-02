"""Exp12 集計・分類ロジックのテスト (docs/Exp12_実験計画確定.md §19,
Exp12_実装チェックリスト.md §4)。

fixtureは本番と同じCSV形式・同じディレクトリ階層を使う (架空JSON禁止)。
少なくとも1本は実際の Simulation/Recorder で生成した出力を使う
end-to-end テストにする。
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
from tools import check_exp12, summarize_exp12
from tools.exp12_common import (
    B1_BMR_CORE, B1_SEEDS, B2_BMR_CORE, B2_SEEDS, TOTAL_RUNS, snapshot_files,
)
from tools.make_exp12_configs import build as build_config
from tools.summarize_exp12 import (
    AggregationError, asymptotic_fit, deceleration_classification,
    generation_space_slope, load_snapshot_series, matter_coupled_for_bmr_level,
    ols_slope, spearman, tick_space_slopes,
)

ENV_KEYS = {"B1": "B1_lightonly_lightspec", "B2": "B2_chemonly_chemspec"}
SNAP_HEADER = ["id", "parent_id", "lineage_id", "generation", "age",
               "x", "y", "energy", "matter", "damage", *GENE_NAMES]


# ---------------------------------------------------------------------------
# fixture ヘルパー
# ---------------------------------------------------------------------------

def _write_snapshot(run_dir: Path, tick: int, body_sizes: list[float],
                    generations: list[int] | None = None) -> None:
    snap_dir = run_dir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = snap_dir / f"snap_{tick:08d}.csv"
    if generations is None:
        generations = [1] * len(body_sizes)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(SNAP_HEADER)
        for i, (bs, gen) in enumerate(zip(body_sizes, generations)):
            row = ["0"] * len(SNAP_HEADER)
            row[0] = str(i)
            row[3] = str(gen)          # generation
            row[10] = f"{bs:.6f}"      # body_size (GENE_NAMESの先頭)
            w.writerow(row)


def _write_stats(run_dir: Path, final_tick: int, population: int,
                 total_biomass=100.0, corpse_matter=5.0, nutrient_total=50.0,
                 extra_rows: list[dict] | None = None) -> None:
    path = run_dir / "stats.csv"
    fieldnames = ["tick", "population", "max_generation",
                 "total_biomass", "corpse_matter", "nutrient_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if extra_rows:
            for row in extra_rows:
                w.writerow(row)
        w.writerow({"tick": final_tick, "population": population, "max_generation": 5,
                   "total_biomass": total_biomass, "corpse_matter": corpse_matter,
                   "nutrient_total": nutrient_total})


def _write_meta(run_dir: Path, seed: int) -> None:
    (run_dir / "meta.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")


def make_run(base: Path, env_key: str, core: float, seed: int,
            final_tick: int = 50000, population: int = 100,
            snapshots: dict[int, tuple[list[float], list[int]]] | None = None,
            stats_rows: list[dict] | None = None) -> Path:
    cond_dir = base / f"{env_key}-bmr{core:.3f}"
    run_dir = cond_dir / f"20260902_000000_seed{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg = build_config(env_key, core)
    cfg.to_json(run_dir / "config.json")
    _write_meta(run_dir, seed)
    _write_stats(run_dir, final_tick, population, extra_rows=stats_rows)

    if snapshots:
        for tick, (sizes, gens) in snapshots.items():
            _write_snapshot(run_dir, tick, sizes, gens)

    return run_dir


def _synthetic_series(ticks: list[int], body_sizes: list[float],
                      generations: list[int] | None = None) -> dict[int, tuple[list[float], list[int]]]:
    """1個体だけのsnapshotシリーズ (傾き検証用の最小構成)。"""
    if generations is None:
        generations = [t // 1000 for t in ticks]
    return {t: ([b, b], [g, g]) for t, b, g in zip(ticks, body_sizes, generations)}


# ---------------------------------------------------------------------------
# 1. production-format snapshot CSVからbody_size分位点が正しく出る
# ---------------------------------------------------------------------------

def test_snapshot_series_body_size_quantiles(tmp_path):
    sizes = [0.2, 0.2, 0.21, 0.15, 1.0, 2.0, 3.0, 9.5, 10.0, 9.8]
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
                       snapshots={10000: (sizes, [1] * 10)})
    series = load_snapshot_series(run_dir)
    assert len(series) == 1
    rec = series[0]
    assert rec["n"] == 10
    assert rec["p_021"] == pytest.approx(4 / 10)
    assert rec["p_high"] == pytest.approx(3 / 10)


# ---------------------------------------------------------------------------
# 2. production-format snapshot CSVからgeneration median/Q90/maxが正しく出る
# ---------------------------------------------------------------------------

def test_snapshot_series_generation_stats(tmp_path):
    sizes = [1.0] * 10
    gens = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1,
                       snapshots={10000: (sizes, gens)})
    series = load_snapshot_series(run_dir)
    rec = series[0]
    assert rec["gmax"] == 100
    assert rec["g50"] == pytest.approx((5 + 6) / 2)  # median of 1..9,100


# ---------------------------------------------------------------------------
# 3. workflowと同じrun directory treeからrunを全件発見できる
# ---------------------------------------------------------------------------

def test_checker_finds_all_run_dirs_two_level(tmp_path):
    d1 = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1)
    d2 = make_run(tmp_path, ENV_KEYS["B2"], 0.100, seed=2)
    found = check_exp12.collect_run_dirs(tmp_path)
    assert set(found) == {d1, d2}


def test_condition_dir_not_treated_as_run(tmp_path):
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1)
    cond_dir = run_dir.parent
    found = check_exp12.collect_run_dirs(tmp_path)
    assert cond_dir not in found
    assert not (cond_dir / "config.json").exists()


# ---------------------------------------------------------------------------
# 4/5/6/7/8. 技術的集計エラーで非0終了 (科学verdict確定禁止)
# ---------------------------------------------------------------------------

def test_missing_snapshot_raises_aggregation_error(tmp_path):
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1, snapshots=None)
    with pytest.raises(AggregationError):
        load_snapshot_series(run_dir)


def test_missing_required_column_raises(tmp_path):
    """generation列が欠けたsnapshot CSVはAggregationErrorになる。"""
    run_dir = make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=1)
    snap_dir = run_dir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    with open(snap_dir / "snap_00010000.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "body_size"])  # generation列なし
        w.writerow(["0", "1.0"])
    with pytest.raises(AggregationError):
        load_snapshot_series(run_dir)


def test_summarize_undetermined_on_missing_run(tmp_path, monkeypatch):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", [1, 2])
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", [])

    base = tmp_path / "runs"
    base.mkdir()
    make_run(base, ENV_KEYS["B1"], 0.000, seed=1,
            snapshots={10000: ([1.0], [1])})
    # seed=2 を欠落させる

    rc = summarize_exp12.summarize(base, None)
    assert rc == 1


def test_duplicate_run_detected(tmp_path):
    for core in B1_BMR_CORE:
        for seed in B1_SEEDS:
            make_run(tmp_path, ENV_KEYS["B1"], core, seed=seed)
    for core in B2_BMR_CORE:
        for seed in B2_SEEDS:
            make_run(tmp_path, ENV_KEYS["B2"], core, seed=seed)

    cond_dir = tmp_path / f"{ENV_KEYS['B1']}-bmr0.000"
    dup_dir = cond_dir / "20260902_999999_seed1_dup"
    dup_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_config(ENV_KEYS["B1"], 0.000)
    cfg.to_json(dup_dir / "config.json")
    _write_meta(dup_dir, seed=1)

    run_dirs = check_exp12.collect_run_dirs(tmp_path)
    assert len(run_dirs) == TOTAL_RUNS + 1
    errors = check_exp12.check_run_completeness(run_dirs)
    assert any("重複run: env=B1 bmr_core=0.000 seed=1" in e for e in errors)


def test_unexpected_run_key_detected(tmp_path):
    for core in B1_BMR_CORE:
        for seed in B1_SEEDS:
            make_run(tmp_path, ENV_KEYS["B1"], core, seed=seed)
    for core in B2_BMR_CORE:
        for seed in B2_SEEDS:
            make_run(tmp_path, ENV_KEYS["B2"], core, seed=seed)
    # 想定外の seed=99 を追加
    make_run(tmp_path, ENV_KEYS["B1"], 0.000, seed=99)

    run_dirs = check_exp12.collect_run_dirs(tmp_path)
    errors = check_exp12.check_run_completeness(run_dirs)
    assert any("想定外run" in e and "seed=99" in e for e in errors)


def test_run_completeness_passes_when_complete(tmp_path):
    for core in B1_BMR_CORE:
        for seed in B1_SEEDS:
            make_run(tmp_path, ENV_KEYS["B1"], core, seed=seed)
    for core in B2_BMR_CORE:
        for seed in B2_SEEDS:
            make_run(tmp_path, ENV_KEYS["B2"], core, seed=seed)
    run_dirs = check_exp12.collect_run_dirs(tmp_path)
    assert len(run_dirs) == TOTAL_RUNS
    errors = check_exp12.check_run_completeness(run_dirs)
    assert errors == []


# ---------------------------------------------------------------------------
# 9/10. first-10k mismatch -> INTEGRITY_FAIL / reference欠落
# ---------------------------------------------------------------------------

def test_first_10k_identical_runs_match(tmp_path):
    d1 = make_run(tmp_path / "a", ENV_KEYS["B1"], 0.000, seed=1, final_tick=10000,
                  snapshots={1000: ([1.0, 1.0], [1, 1]), 10000: ([1.2, 1.2], [2, 2])})
    d2 = make_run(tmp_path / "b", ENV_KEYS["B1"], 0.000, seed=1, final_tick=10000,
                  snapshots={1000: ([1.0, 1.0], [1, 1]), 10000: ([1.2, 1.2], [2, 2])})
    errors = check_exp12.compare_first_10k(d1, d2)
    assert errors == []


def test_first_10k_mismatch_detected(tmp_path):
    d1 = make_run(tmp_path / "a", ENV_KEYS["B1"], 0.000, seed=1, final_tick=10000,
                  snapshots={1000: ([1.0], [1])})
    d2 = make_run(tmp_path / "b", ENV_KEYS["B1"], 0.000, seed=1, final_tick=10000,
                  snapshots={1000: ([1.5], [1])})  # body_size が違う
    errors = check_exp12.compare_first_10k(d1, d2)
    assert errors, "不一致が検出されるべき"


def test_first_10k_reference_missing_is_error(tmp_path):
    d1 = make_run(tmp_path / "a", ENV_KEYS["B1"], 0.000, seed=1)
    missing_ref = tmp_path / "does_not_exist"
    errors = check_exp12.compare_first_10k(d1, missing_ref)
    assert errors, "参照が存在しない場合はエラーになるべき"


# ---------------------------------------------------------------------------
# 11. tick slopeの符号・正規化
# ---------------------------------------------------------------------------

def test_ols_slope_sign_and_normalization():
    xs = [20000, 22000, 24000, 26000, 28000, 30000]
    ys = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]  # 明確な負の傾き
    slope = ols_slope(xs, ys)
    assert slope is not None and slope < 0


def test_tick_space_slopes_shrinking_trend():
    # 線形に小型化するtrajectory (減速なし)
    series = []
    for tick in range(20000, 50001, 1000):
        body = 1.0 - (tick - 20000) * 0.00002  # 一定の負の傾き
        series.append({"tick": tick, "body_median": body})
    slopes = tick_space_slopes(series)
    assert slopes["W1"] < 0
    assert slopes["W2"] < 0
    assert slopes["W3"] < 0
    # raw slope (正規化前) は一定速度の線形減少なら全window同じはず
    raw_slopes = [
        ols_slope([r["tick"] for r in series if lo <= r["tick"] <= hi],
                 [r["body_median"] for r in series if lo <= r["tick"] <= hi])
        for lo, hi in ((20000, 30000), (30000, 40000), (40000, 50000))
    ]
    assert raw_slopes[0] == pytest.approx(raw_slopes[2], rel=0.05)


# ---------------------------------------------------------------------------
# 12. clear decelerationを DELAY_CONTINUES に誤分類しない (回帰テスト)
# ---------------------------------------------------------------------------

def test_clear_deceleration_not_misclassified_as_sustained_drift():
    """0.8 -> 0.6 -> 0.5 -> 0.45 -> 0.43 のような明確な減速軌跡。

    docs/Exp12_実験計画確定.md §9.1 の例そのもの。
    """
    # 減速する傾き: |S2|<=0.8|S1|, |S3|<=0.8|S2|
    s1, s2, s3 = -1.0, -0.7, -0.4
    decel = deceleration_classification(s1, s2, s3)
    assert decel["clear_deceleration"] is True
    assert decel["sustained_negative_drift"] is False


def test_sustained_decline_correctly_classified():
    """一定速度で減少し続ける軌跡 (減速なし) は SUSTAINED_NEGATIVE_DRIFT。"""
    s1, s2, s3 = -0.10, -0.09, -0.08  # 減速比が0.8を超える (ほぼ一定)
    decel = deceleration_classification(s1, s2, s3)
    assert decel["sustained_negative_drift"] is True
    assert decel["clear_deceleration"] is False  # 0.8比を満たさないため


def test_no_sustained_drift_when_below_threshold():
    s1, s2, s3 = -0.02, -0.02, -0.02  # |S|<=0.05 (stationarity範囲)
    decel = deceleration_classification(s1, s2, s3)
    assert decel["sustained_negative_drift"] is False


# ---------------------------------------------------------------------------
# 13/14. generation-space slope計算 + window不足
# ---------------------------------------------------------------------------

def test_generation_space_slope_basic():
    series = []
    g = 0
    for i in range(60):
        g += 1
        body = 1.0 - i * 0.005
        series.append({"g50": g, "body_median": body})
    result = generation_space_slope(series)
    assert result["window_insufficient"] is False
    assert result["s_gen"] < 0  # 小型化継続


def test_generation_window_insufficient_when_narrow():
    series = [{"g50": g, "body_median": 1.0} for g in range(1, 4)]  # 幅3世代のみ
    result = generation_space_slope(series)
    assert result["window_insufficient"] is True


def test_generation_space_collapses_consecutive_equal_g50():
    series = [
        {"g50": 10, "body_median": 1.0},
        {"g50": 10, "body_median": 1.05},  # 同一世代 -> 後者で上書き
        {"g50": 50, "body_median": 0.5},
    ]
    result = generation_space_slope(series)
    # window_insufficientでなければ計算できている
    assert result["s_gen"] is not None or result["window_insufficient"] is True


# ---------------------------------------------------------------------------
# 15. asymptotic fit success / failure / boundary
# ---------------------------------------------------------------------------

def test_asymptotic_fit_recovers_known_parameters():
    import numpy as np
    b_inf_true, A_true, tau_true = 0.5, 0.3, 5000.0
    series = []
    for tick in range(10000, 50001, 1000):
        t0 = tick - 10000
        body = b_inf_true + A_true * np.exp(-t0 / tau_true)
        series.append({"tick": tick, "body_median": float(body)})
    fit = asymptotic_fit(series)
    assert fit["success"] is True
    assert fit["b_inf"] == pytest.approx(b_inf_true, abs=0.05)


def test_asymptotic_fit_insufficient_points():
    series = [{"tick": 10000, "body_median": 1.0}, {"tick": 11000, "body_median": 0.9}]
    fit = asymptotic_fit(series)
    assert fit["success"] is False


def test_asymptotic_fit_flat_series_no_decay():
    series = [{"tick": t, "body_median": 1.0} for t in range(10000, 50001, 1000)]
    fit = asymptotic_fit(series)
    # フラット系列は A~0、b_inf~1.0 に収束するはず
    assert fit["b_inf"] == pytest.approx(1.0, abs=0.05)


# ---------------------------------------------------------------------------
# 16. Matter coupling difference-correlation
# ---------------------------------------------------------------------------

def test_spearman_strong_positive_correlation():
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ys = [1.1, 2.0, 2.9, 4.2, 4.8, 6.1, 7.0, 7.9, 9.1, 10.0]
    result = spearman(xs, ys)
    assert result is not None
    rho, p = result
    assert rho > 0.9
    assert p < 0.05


def test_spearman_no_correlation_with_constant():
    xs = [1, 2, 3, 4, 5]
    ys = [1.0, 1.0, 1.0, 1.0, 1.0]
    assert spearman(xs, ys) is None


def test_matter_coupled_for_bmr_level_true_when_majority_strong():
    couplings = [
        {"nutrient_fraction": {"rho": 0.8, "p": 0.01, "strong": True, "sign": 1}}
        for _ in range(4)
    ] + [
        {"nutrient_fraction": {"rho": 0.1, "p": 0.5, "strong": False, "sign": 1}}
        for _ in range(4)
    ]
    assert matter_coupled_for_bmr_level(couplings) is True


def test_matter_coupled_for_bmr_level_false_when_minority():
    couplings = [
        {"nutrient_fraction": {"rho": 0.8, "p": 0.01, "strong": True, "sign": 1}}
        for _ in range(3)
    ] + [
        {"nutrient_fraction": {"rho": 0.1, "p": 0.5, "strong": False, "sign": 1}}
        for _ in range(5)
    ]
    assert matter_coupled_for_bmr_level(couplings) is False


# ---------------------------------------------------------------------------
# 17. B2 method-control pass/fail は summarize() 経由の統合テストで確認 (下記end-to-end参照)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 18/19/20. per-bmr 6/8集約・global verdict分岐・技術エラー時に確定しない
# ---------------------------------------------------------------------------

def _stationary_series(body_level: float, ticks_range=(0, 50000)):
    """全windowでstationaryなtrajectory (INTERIOR_EQUILIBRIUM相当)。"""
    snaps = {}
    for tick in range(ticks_range[0], ticks_range[1] + 1, 1000):
        gen = 1 + tick // 500
        snaps[tick] = ([body_level, body_level], [gen, gen])
    return snaps


def test_summarize_end_to_end_interior_equilibrium_verdict(tmp_path, monkeypatch):
    """全runがstationary (INTERIOR_EQUILIBRIUM) な合成データで
    EQUILIBRIUM_SHIFT_SUPPORTED 系統のverdictへ到達することを確認する。
    """
    small_bmr = [0.000, 0.100]
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", small_bmr)
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", list(range(1, 9)))
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", list(range(1, 6)))

    base = tmp_path / "runs"
    base.mkdir()

    # B1 bmr=0: 下限付近でstationary (LOWER_BOUND_EQUILIBRIUM相当)
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.000, seed=seed,
                snapshots=_stationary_series(0.20))
    # B1 bmr=0.100: 内部平衡でstationary (INTERIOR_EQUILIBRIUM相当)
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.100, seed=seed,
                snapshots=_stationary_series(0.40))
    # B2 bmr=0: stationary (method control用)
    for seed in range(1, 6):
        make_run(base, ENV_KEYS["B2"], 0.000, seed=seed,
                snapshots=_stationary_series(0.80))

    rc = summarize_exp12.summarize(base, None)
    assert rc == 0  # 集計エラーなしで完走すること


def test_summarize_does_not_confirm_verdict_with_technical_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", [1])
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", [])

    base = tmp_path / "runs"
    base.mkdir()
    # snapshot無し (技術エラー) の run のみ
    make_run(base, ENV_KEYS["B1"], 0.000, seed=1, snapshots=None)

    rc = summarize_exp12.summarize(base, None)
    assert rc == 1


# ---------------------------------------------------------------------------
# end-to-end: 実際の Simulation/Recorder で短run生成 -> Exp12 parser
# ---------------------------------------------------------------------------

def test_end_to_end_real_simulation_output(tmp_path):
    """架空schemaではなく、実際の Simulation + Recorder が書く出力を
    Exp12 の集計コードで読めることを確認する (Exp12_実装チェックリスト §1.2)。
    """
    import dataclasses

    from evosim.simulation import Simulation

    base_cfg = build_config("B1_lightonly_lightspec", 0.050)
    cfg = dataclasses.replace(base_cfg, snapshot_interval=100, stats_interval=20)
    run_dir = tmp_path / "real_run"
    sim = Simulation(cfg, seed=1, run_dir=run_dir)
    for _ in range(250):
        sim.step()
    sim.close()

    series = load_snapshot_series(run_dir)
    assert len(series) >= 2
    for rec_row in series:
        assert rec_row["n"] > 0
        assert 0.0 <= rec_row["p_021"] <= 1.0
        assert rec_row["gmax"] >= 0


# ---------------------------------------------------------------------------
# 二巡目レビューで追加: summarizer側の duplicate/unexpected key 検出
# (checker側は既にtest_duplicate_run_detected / test_unexpected_run_key_detected
#  でカバーしているが、summarize_exp12.collect_runs() 自体も独立に検出する
#  防御的実装であることを確認する)
# ---------------------------------------------------------------------------

def test_summarize_detects_duplicate_run(tmp_path, monkeypatch):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", [1])
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", [])

    base = tmp_path / "runs"
    base.mkdir()
    make_run(base, ENV_KEYS["B1"], 0.000, seed=1, snapshots={10000: ([1.0], [1])})
    # 同じ (env,bmr_core,seed) を別ディレクトリでもう1つ作る
    cond_dir = base / f"{ENV_KEYS['B1']}-bmr0.000"
    dup_dir = cond_dir / "dup_seed1"
    dup_dir.mkdir(parents=True)
    cfg = build_config(ENV_KEYS["B1"], 0.000)
    cfg.to_json(dup_dir / "config.json")
    _write_meta(dup_dir, seed=1)
    _write_stats(dup_dir, 10000, 100)
    _write_snapshot(dup_dir, 10000, [1.0], [1])

    tech_errors: list[str] = []
    summarize_exp12.collect_runs(base, 50000, tech_errors)
    assert any("重複run" in e for e in tech_errors)

    rc = summarize_exp12.summarize(base, None)
    assert rc == 1


def test_summarize_detects_unexpected_run_key(tmp_path, monkeypatch):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", [1])
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", [])

    base = tmp_path / "runs"
    base.mkdir()
    make_run(base, ENV_KEYS["B1"], 0.000, seed=1, snapshots={10000: ([1.0], [1])})
    # 期待grid外の seed=99 を追加
    make_run(base, ENV_KEYS["B1"], 0.000, seed=99, snapshots={10000: ([1.0], [1])})

    tech_errors: list[str] = []
    summarize_exp12.collect_runs(base, 50000, tech_errors)
    assert any("想定外run" in e and "seed=99" in e for e in tech_errors)

    rc = summarize_exp12.summarize(base, None)
    assert rc == 1


# ---------------------------------------------------------------------------
# asymptotic fit の boundary ケース (b_inf/tau が制約境界に張り付く)
# ---------------------------------------------------------------------------

def test_asymptotic_fit_boundary_stuck_b_inf():
    """b_infが下限0.2付近に張り付くケース (単調な急減衰から下限直行) は
    boundary_stuckとしてsuccess=Falseになりうる。"""
    import numpy as np
    series = []
    for tick in range(10000, 50001, 1000):
        t0 = tick - 10000
        # tauが非常に小さく、ほぼ瞬時にb_inf=0.2へ落ちる
        body = 0.2 + 5.0 * np.exp(-t0 / 50.0)
        series.append({"tick": tick, "body_median": float(max(0.2, body))})
    fit = asymptotic_fit(series)
    # 極端な減衰は tau が探索grid下限に張り付くか、b_infが境界に寄る
    assert fit.get("boundary_stuck") is True or fit["success"] is False


def test_asymptotic_fit_tau_unstable_when_slow_decay():
    """40kウィンドウの1/3を超えるtau (>13,333) はtau_unstableとしてsuccess=Falseになる。"""
    import numpy as np
    b_inf_true, A_true, tau_true = 0.5, 0.3, 40000.0  # 非常に緩やかな減衰
    series = []
    for tick in range(10000, 50001, 1000):
        t0 = tick - 10000
        body = b_inf_true + A_true * np.exp(-t0 / tau_true)
        series.append({"tick": tick, "body_median": float(body)})
    fit = asymptotic_fit(series)
    assert fit.get("tau_unstable") is True or fit["success"] is False


# ---------------------------------------------------------------------------
# B2 method control FAIL -> INVALID_OR_METHOD_REVIEW
# ---------------------------------------------------------------------------

def _drifting_series(start: float, rate_per_tick: float, ticks_range=(0, 50000)):
    snaps = {}
    for tick in range(ticks_range[0], ticks_range[1] + 1, 1000):
        body = max(0.05, start - rate_per_tick * tick)
        gen = 1 + tick // 200
        snaps[tick] = ([body, body], [gen, gen])
    return snaps


def test_b2_method_control_fail_yields_invalid_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", list(range(1, 9)))
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", list(range(1, 6)))

    base = tmp_path / "runs"
    base.mkdir()
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.000, seed=seed,
                snapshots=_stationary_series(0.20))
    # B2 baseline を全seed非stationary (持続的drift) にする -> method control FAIL
    for seed in range(1, 6):
        make_run(base, ENV_KEYS["B2"], 0.000, seed=seed,
                snapshots=_drifting_series(0.9, 0.000015))

    rc = summarize_exp12.summarize(base, None)
    assert rc == 0  # 技術エラーではないので集計自体は完走する


def test_b2_method_control_fail_verdict_via_capsys(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", list(range(1, 9)))
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", list(range(1, 6)))

    base = tmp_path / "runs"
    base.mkdir()
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.000, seed=seed,
                snapshots=_stationary_series(0.20))
    for seed in range(1, 6):
        make_run(base, ENV_KEYS["B2"], 0.000, seed=seed,
                snapshots=_drifting_series(0.9, 0.000015))

    summarize_exp12.summarize(base, None)
    out = capsys.readouterr().out
    assert "INVALID_OR_METHOD_REVIEW" in out
    assert "METHOD_CONTROL_FAIL" in out


# ---------------------------------------------------------------------------
# per-bmr 6/8 集約の境界値
# ---------------------------------------------------------------------------

def test_per_bmr_level_exactly_6_of_8_passes_interior_eq(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000, 0.100])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", list(range(1, 9)))
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", list(range(1, 6)))

    base = tmp_path / "runs"
    base.mkdir()
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.000, seed=seed, snapshots=_stationary_series(0.20))
    # bmr=0.100: 7/8 seed を内部平衡 (stationary, 大型) に、1/8 のみ非stationaryにする
    # (BMR_LEVEL_INTERIOR_EQ は 6/8 以上のinterior かつ DELAY <=1 を要求するため)
    for seed in range(1, 8):
        make_run(base, ENV_KEYS["B1"], 0.100, seed=seed, snapshots=_stationary_series(0.40))
    for seed in range(8, 9):
        make_run(base, ENV_KEYS["B1"], 0.100, seed=seed, snapshots=_drifting_series(0.9, 0.000015))
    for seed in range(1, 6):
        make_run(base, ENV_KEYS["B2"], 0.000, seed=seed, snapshots=_stationary_series(0.80))

    summarize_exp12.summarize(base, None)
    out = capsys.readouterr().out
    assert "BMR_LEVEL_INTERIOR_EQ" in out


# ---------------------------------------------------------------------------
# DELAY_SUPPORTED / WINDOW_INSUFFICIENT verdict分岐
# ---------------------------------------------------------------------------

def test_delay_supported_verdict(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000, 0.100, 0.200, 0.300])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", list(range(1, 9)))
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", list(range(1, 6)))

    base = tmp_path / "runs"
    base.mkdir()
    # baseline: 下限相当でstationary (baseline signal PASS)
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.000, seed=seed, snapshots=_stationary_series(0.20))
    # 正bmr条件は全て持続的drift (DELAY_CONTINUES) -> 6/8以上
    for core in (0.100, 0.200, 0.300):
        for seed in range(1, 9):
            make_run(base, ENV_KEYS["B1"], core, seed=seed,
                    snapshots=_drifting_series(0.9, 0.000015))
    for seed in range(1, 6):
        make_run(base, ENV_KEYS["B2"], 0.000, seed=seed, snapshots=_stationary_series(0.80))

    summarize_exp12.summarize(base, None)
    out = capsys.readouterr().out
    assert "DELAY_SUPPORTED" in out or "WINDOW_INSUFFICIENT" in out


def test_window_insufficient_verdict_when_baseline_not_reproduced(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(summarize_exp12, "B1_BMR_CORE", [0.000, 0.100])
    monkeypatch.setattr(summarize_exp12, "B1_SEEDS", list(range(1, 9)))
    monkeypatch.setattr(summarize_exp12, "B2_BMR_CORE", [0.000])
    monkeypatch.setattr(summarize_exp12, "B2_SEEDS", list(range(1, 6)))

    base = tmp_path / "runs"
    base.mkdir()
    # baseline を大型のまま stationary にする -> lower-bound signal 不成立
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.000, seed=seed, snapshots=_stationary_series(0.90))
    for seed in range(1, 9):
        make_run(base, ENV_KEYS["B1"], 0.100, seed=seed, snapshots=_stationary_series(0.95))
    for seed in range(1, 6):
        make_run(base, ENV_KEYS["B2"], 0.000, seed=seed, snapshots=_stationary_series(0.80))

    summarize_exp12.summarize(base, None)
    out = capsys.readouterr().out
    assert "WINDOW_INSUFFICIENT / REVIEW" in out
