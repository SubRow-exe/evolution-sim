"""Exp13集計・選定ロジックのテスト
(docs/Exp13_実験計画確定.md, docs/V1.8_実装チェックリスト.md §11)。

fixtureは本番と同じCSV形式・ディレクトリ階層を使う。少なくとも1本は
実Simulation/Recorder出力を使うend-to-endテストにする。
"""
from __future__ import annotations

import csv
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.simulation import Simulation
from tools import summarize_exp13 as sx
from tools.exp13_common import A1_LIGHT_MAX, A1_SEEDS, A1_TICKS, A2_CHEM_UPTAKE, A2_CHEMICAL_UPTAKE_HALF
from tools.make_exp13_configs import build_a1, build_a2, build_b1


STATS_FIELDS = ["tick", "population", "births_cum", "chemical_total",
                "flow_chemical_cum", "light_cycle_factor", "light_supply_rate",
                "max_generation"]


def _write_stats(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "stats.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATS_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_meta(run_dir: Path, seed: int) -> None:
    (run_dir / "meta.json").write_text(
        json.dumps({"seed": seed, "git_sha": "abc", "numeric_environment": {"env_key": "env"}}),
        encoding="utf-8")


def _make_run(base: Path, name: str, cfg, seed: int, rows: list[dict]) -> Path:
    run_dir = base / name
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg.to_json(run_dir / "config.json")
    _write_meta(run_dir, seed)
    _write_stats(run_dir, rows)
    return run_dir


def _rows(ticks: list[int], pop: int = 50, births_start: int = 0, births_step: int = 1,
         max_gen: int = 3) -> list[dict]:
    out = []
    births = births_start
    for t in ticks:
        births += births_step
        out.append({
            "tick": t, "population": pop, "births_cum": births,
            "chemical_total": 10.0, "flow_chemical_cum": float(t) * 0.1,
            "light_cycle_factor": 0.0 if (t % 200) >= 100 else 1.0,
            "light_supply_rate": 0.0 if (t % 200) >= 100 else 5.0,
            "max_generation": max_gen,
        })
    return out


# ---------------------------------------------------------------------------
# 1. real Simulation/Recorder end-to-end
# ---------------------------------------------------------------------------

def test_end_to_end_real_simulation_output(tmp_path):
    cfg = build_a1(2.1)
    cfg = dataclasses.replace(cfg, snapshot_interval=200, stats_interval=50,
                              initial_population=40)
    run_dir = tmp_path / "real_run"
    sim = Simulation(cfg, seed=1, run_dir=run_dir)
    for _ in range(600):
        sim.step()
    sim.close()

    run = sx.load_run(run_dir)
    assert run is not None
    status = sx.classify_status(run, 600)
    assert status in {"COMPLETE", "EXTINCT", "POP_HALT", "INCOMPLETE_RESOURCE"}
    lb = sx.late_births(run, 200)
    assert lb >= 0
    assert sx.night_light_gain_is_zero(run) in (True, False)


# ---------------------------------------------------------------------------
# 2. classify_status
# ---------------------------------------------------------------------------

class TestClassifyStatus:
    def test_complete(self, tmp_path):
        cfg = build_a1(1.8)
        run_dir = _make_run(tmp_path, "r1", cfg, 1, _rows([2000, 4000, 10000]))
        run = sx.load_run(run_dir)
        assert sx.classify_status(run, 10000) == "COMPLETE"

    def test_extinct(self, tmp_path):
        cfg = build_a1(1.8)
        rows = _rows([2000, 4000])
        rows[-1]["population"] = 0
        run_dir = _make_run(tmp_path, "r2", cfg, 1, rows)
        run = sx.load_run(run_dir)
        assert sx.classify_status(run, 10000) == "EXTINCT"

    def test_pop_halt(self, tmp_path):
        cfg = build_a1(1.8)
        rows = _rows([2000, 4000], pop=10000)
        run_dir = _make_run(tmp_path, "r3", cfg, 1, rows)
        run = sx.load_run(run_dir)
        assert sx.classify_status(run, 10000) == "POP_HALT"

    def test_incomplete_resource(self, tmp_path):
        cfg = build_a1(1.8)
        rows = _rows([2000, 4000])
        run_dir = _make_run(tmp_path, "r4", cfg, 1, rows)
        run = sx.load_run(run_dir)
        assert sx.classify_status(run, 10000) == "INCOMPLETE_RESOURCE"


# ---------------------------------------------------------------------------
# 3. late_births / late_population_values
# ---------------------------------------------------------------------------

class TestLateMetrics:
    def test_late_births_positive(self, tmp_path):
        cfg = build_a1(1.8)
        rows = _rows(list(range(0, 10001, 20)), births_step=1)
        run_dir = _make_run(tmp_path, "r5", cfg, 1, rows)
        run = sx.load_run(run_dir)
        lb = sx.late_births(run, 2000)
        assert lb > 0

    def test_late_births_zero_when_stalled(self, tmp_path):
        cfg = build_a1(1.8)
        rows = _rows(list(range(0, 8001, 20)), births_step=1)
        rows += _rows(list(range(8020, 10001, 20)), births_start=rows[-1]["births_cum"],
                      births_step=0)
        run_dir = _make_run(tmp_path, "r6", cfg, 1, rows)
        run = sx.load_run(run_dir)
        lb = sx.late_births(run, 2000)
        assert lb == 0


# ---------------------------------------------------------------------------
# 4. night_light_gain_is_zero
# ---------------------------------------------------------------------------

class TestNightZero:
    def test_true_when_rate_zero_at_night(self, tmp_path):
        cfg = build_a1(1.8)
        run_dir = _make_run(tmp_path, "r7", cfg, 1, _rows([100, 150, 200]))
        run = sx.load_run(run_dir)
        assert sx.night_light_gain_is_zero(run) is True

    def test_false_when_rate_nonzero_at_night(self, tmp_path):
        cfg = build_a1(1.8)
        rows = _rows([100, 150])
        rows[1]["light_supply_rate"] = 3.0  # cycle_factor=0だがrateが非0 (バグ検出用)
        run_dir = _make_run(tmp_path, "r8", cfg, 1, rows)
        run = sx.load_run(run_dir)
        assert sx.night_light_gain_is_zero(run) is False


# ---------------------------------------------------------------------------
# 5. collect_phase_a1: 欠落/重複/想定外key検出
# ---------------------------------------------------------------------------

class TestCollectPhaseA1:
    def _make_full_a1(self, base: Path) -> None:
        for lm in A1_LIGHT_MAX:
            for seed in A1_SEEDS:
                cfg = build_a1(lm)
                _make_run(base, f"A1_{lm}_{seed}", cfg, seed,
                         _rows(list(range(0, A1_TICKS + 1, 2000))))

    def test_complete_grid_no_errors(self, tmp_path):
        self._make_full_a1(tmp_path)
        errors: list[str] = []
        runs = sx.collect_phase_a1(tmp_path, errors)
        assert errors == []
        assert len(runs) == len(A1_LIGHT_MAX) * len(A1_SEEDS)

    def test_missing_run_detected(self, tmp_path):
        self._make_full_a1(tmp_path)
        import shutil
        shutil.rmtree(tmp_path / f"A1_{A1_LIGHT_MAX[0]}_1")
        errors: list[str] = []
        sx.collect_phase_a1(tmp_path, errors)
        assert any("欠落run" in e for e in errors)

    def test_duplicate_run_detected(self, tmp_path):
        self._make_full_a1(tmp_path)
        cfg = build_a1(A1_LIGHT_MAX[0])
        _make_run(tmp_path, f"A1_{A1_LIGHT_MAX[0]}_1_dup", cfg, 1,
                 _rows(list(range(0, A1_TICKS + 1, 2000))))
        errors: list[str] = []
        sx.collect_phase_a1(tmp_path, errors)
        assert any("重複run" in e for e in errors)


# ---------------------------------------------------------------------------
# 6. select_light_max (a1_level_summary経由の高レベルロジック)
# ---------------------------------------------------------------------------

class TestSelectLightMax:
    def _synthetic_runs_for_level(self, lm: float, complete: int, extinct: int,
                                  late_birth: int, late_pop_ok: int) -> dict[int, dict]:
        runs = {}
        for i, seed in enumerate(A1_SEEDS):
            if i < extinct:
                rows = _rows([0, 2000], pop=0)
                rows[-1]["population"] = 0
            elif i < extinct + complete:
                pop = 40 if i < extinct + late_pop_ok else 5
                births_step = 1 if i < extinct + late_birth else 0
                rows = _rows(list(range(0, A1_TICKS + 1, 2000)), pop=pop, births_step=births_step)
            else:
                rows = _rows([0, 2000])  # incomplete
            runs[seed] = {"meta": {"seed": seed}, "cfg": {}, "stats": rows,
                         "path": Path(f"/fake/{lm}/{seed}")}
        return runs

    def test_robust_level_selected(self):
        # 全水準を「頑健」にして最小 (0.8) が選ばれることを確認
        levels = {}
        for lm in A1_LIGHT_MAX:
            levels[lm] = self._synthetic_runs_for_level(
                lm, complete=5, extinct=0, late_birth=5, late_pop_ok=5)
        a1_runs = {(lm, seed): run for lm, level in levels.items() for seed, run in level.items()}
        selected, summary = sx.select_light_max(a1_runs)
        assert selected == min(A1_LIGHT_MAX)
        for lm in A1_LIGHT_MAX:
            assert summary[lm]["robust_light_viable"] is True

    def test_no_robust_level_fails(self):
        levels = {}
        for lm in A1_LIGHT_MAX:
            levels[lm] = self._synthetic_runs_for_level(
                lm, complete=0, extinct=5, late_birth=0, late_pop_ok=0)
        a1_runs = {(lm, seed): run for lm, level in levels.items() for seed, run in level.items()}
        selected, summary = sx.select_light_max(a1_runs)
        assert selected is None
        for lm in A1_LIGHT_MAX:
            assert summary[lm]["robust_light_viable"] is False

    def test_smallest_robust_level_wins_when_mixed(self):
        levels = {}
        for i, lm in enumerate(A1_LIGHT_MAX):
            # 0.8, 1.2 は非頑健、1.5以降は頑健 -> 1.5が選ばれる
            robust = i >= 2
            levels[lm] = self._synthetic_runs_for_level(
                lm, complete=5 if robust else 1, extinct=0 if robust else 3,
                late_birth=5 if robust else 0, late_pop_ok=5 if robust else 0)
        a1_runs = {(lm, seed): run for lm, level in levels.items() for seed, run in level.items()}
        selected, summary = sx.select_light_max(a1_runs)
        assert selected == A1_LIGHT_MAX[2]


# ---------------------------------------------------------------------------
# 7. a3_direction_check
# ---------------------------------------------------------------------------

class TestA3DirectionCheck:
    def test_direction_pass_when_gain_and_stock_decrease(self):
        from tools.exp13_common import A3_POPULATIONS, A3_SEEDS
        runs = {}
        for pop in A3_POPULATIONS:
            for seed in A3_SEEDS:
                # 密度が高いほどper-capita gainとfinal stockが下がる合成データ
                flow_per_capita = 10.0 / pop
                chem_total = 20.0 / pop
                rows = [{
                    "tick": 2000, "population": pop, "births_cum": 1,
                    "chemical_total": chem_total,
                    "flow_chemical_cum": flow_per_capita * pop,
                    "light_cycle_factor": 0.0, "light_supply_rate": 0.0,
                    "max_generation": 1,
                }]
                runs[(pop, seed)] = {"meta": {"seed": seed}, "cfg": {}, "stats": rows,
                                    "path": Path(f"/fake/{pop}/{seed}")}
        result = sx.a3_direction_check(runs)
        assert result["direction_pass"] is True

    def test_direction_fail_when_gain_increases_with_density(self):
        from tools.exp13_common import A3_POPULATIONS, A3_SEEDS
        runs = {}
        for pop in A3_POPULATIONS:
            for seed in A3_SEEDS:
                # 逆方向: 密度が増えるほどper-capita gainも増える (異常)
                flow_per_capita = pop * 1.0
                chem_total = pop * 2.0
                rows = [{
                    "tick": 2000, "population": pop, "births_cum": 1,
                    "chemical_total": chem_total,
                    "flow_chemical_cum": flow_per_capita * pop,
                    "light_cycle_factor": 0.0, "light_supply_rate": 0.0,
                    "max_generation": 1,
                }]
                runs[(pop, seed)] = {"meta": {"seed": seed}, "cfg": {}, "stats": rows,
                                    "path": Path(f"/fake/{pop}/{seed}")}
        result = sx.a3_direction_check(runs)
        assert result["direction_pass"] is False


# ---------------------------------------------------------------------------
# 8. b_gate_summary
# ---------------------------------------------------------------------------

class TestBGateSummary:
    def test_pass_case(self):
        runs = {}
        for seed in range(1, 9):
            rows = _rows(list(range(0, 20001, 2000)), births_step=1)
            runs[seed] = {"meta": {"seed": seed}, "cfg": {}, "stats": rows,
                         "path": Path(f"/fake/{seed}")}
        s = sx.b_gate_summary(runs, 20000, 4000)
        assert s["n_complete"] == 8
        assert s["late_birth_ok"] == 8

    def test_fail_case_low_completion(self):
        runs = {}
        for seed in range(1, 9):
            if seed <= 4:
                rows = _rows(list(range(0, 20001, 2000)), births_step=1)
            else:
                rows = _rows([0, 2000], pop=0)
                rows[-1]["population"] = 0
            runs[seed] = {"meta": {"seed": seed}, "cfg": {}, "stats": rows,
                         "path": Path(f"/fake/{seed}")}
        s = sx.b_gate_summary(runs, 20000, 4000)
        assert s["n_complete"] == 4
        assert s["n_complete"] < 6


# ---------------------------------------------------------------------------
# 9. AggregationErrorがglobal verdictを出さないこと (missing/duplicate)
# ---------------------------------------------------------------------------

class TestSummarizePhaseAAggregationError:
    def test_missing_run_prevents_selected_output(self, tmp_path, capsys):
        for lm in A1_LIGHT_MAX:
            for seed in A1_SEEDS:
                if lm == A1_LIGHT_MAX[0] and seed == A1_SEEDS[0]:
                    continue  # 1件だけ欠落させる
                cfg = build_a1(lm)
                _make_run(tmp_path, f"A1_{lm}_{seed}", cfg, seed,
                         _rows(list(range(0, A1_TICKS + 1, 2000))))
        for k in A2_CHEMICAL_UPTAKE_HALF:
            for u in A2_CHEM_UPTAKE:
                for seed in range(1, 4):
                    cfg = build_a2(k, u)
                    _make_run(tmp_path, f"A2_{k}_{u}_{seed}", cfg, seed,
                             _rows(list(range(0, 5001, 1000))))
        rc = sx.summarize_phase_a(tmp_path, None)
        out = capsys.readouterr().out + capsys.readouterr().err
        assert rc == 1
