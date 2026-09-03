"""tools/summarize_exp14.py のテスト。

late window N/A semantics regressionと、scientific/technical分離、
実Recorder出力を使ったE2Eを確認する (実装チェックリスト.md §5/7/9)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.recorder import Recorder
from evosim.simulation import Simulation
from tools import summarize_exp14 as sx


def _run_real_simulation(tmp_path, ticks=200, initial_population=20):
    cfg = Config(initial_population=initial_population, stats_interval=20,
                 snapshot_interval=1000, light_cycle_enabled=True,
                 light_cycle_period_ticks=200, light_day_fraction=0.5,
                 fixed_genes=list(__import__("evosim.genome", fromlist=["GENE_NAMES"]).GENE_NAMES))
    run_dir = tmp_path / "run"
    sim = Simulation(cfg, seed=1, run_dir=run_dir)
    rec = Recorder(run_dir, cfg, 1)
    sim.recorder = rec
    for _ in range(ticks):
        sim.step()
    rec.finalize(sim)
    rec.close()
    return run_dir


def test_run_status_complete_e2e(tmp_path):
    run_dir = _run_real_simulation(tmp_path, ticks=200)
    kind, status = sx.run_status(run_dir, expected_ticks=200)
    assert kind == "scientific"
    assert status in ("COMPLETE", "EXTINCT", "POP_HALT")  # 実runの帰結次第


def test_run_status_missing_files_is_integrity_fail(tmp_path):
    run_dir = tmp_path / "empty"
    run_dir.mkdir()
    kind, status = sx.run_status(run_dir, expected_ticks=2000)
    assert kind == "technical"
    assert status == "INTEGRITY_FAIL"


def test_run_status_incomplete_resource_marker(tmp_path):
    run_dir = tmp_path / "r"
    run_dir.mkdir()
    Config().to_json(run_dir / "config.json")
    (run_dir / "meta.json").write_text(
        json.dumps({"seed": 1, "incomplete_resource": True}), encoding="utf-8")
    (run_dir / "stats.csv").write_text("tick,population\n0,10\n", encoding="utf-8")
    kind, status = sx.run_status(run_dir, expected_ticks=2000)
    assert kind == "technical"
    assert status == "INCOMPLETE_RESOURCE"


def test_run_status_extinct_is_scientific_not_technical(tmp_path):
    run_dir = tmp_path / "r"
    run_dir.mkdir()
    Config().to_json(run_dir / "config.json")
    (run_dir / "meta.json").write_text(json.dumps({"seed": 1}), encoding="utf-8")
    (run_dir / "stats.csv").write_text(
        "tick,population\n0,100\n500,10\n900,0\n", encoding="utf-8")
    kind, status = sx.run_status(run_dir, expected_ticks=2000)
    assert kind == "scientific"
    assert status == "EXTINCT"


def test_late_window_na_never_registers_as_pass(tmp_path):
    """final_tick(80) < late_window(500) の early-extinction run で
    late_population_mean が None (N/A) になり、全tick平均を誤って
    late PASS扱いしない (Exp13バグの回帰テスト)。
    """
    run_dir = tmp_path / "r"
    run_dir.mkdir()
    build_cfg = Config(light_cycle_enabled=True)
    build_cfg.to_json(run_dir / "config.json")
    (run_dir / "meta.json").write_text(json.dumps({"seed": 1}), encoding="utf-8")
    # 序盤は高population、80tickで絶滅 (population=0の行を含む)
    rows = ["tick,population,light_cycle_factor"]
    for t, pop in [(0, 100), (20, 90), (40, 50), (60, 20), (80, 0)]:
        rows.append(f"{t},{pop},1.0")
    (run_dir / "stats.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = sx.summarize_phase_a_run(run_dir, expected_ticks=2000, late_window=500)
    assert result["status"] == "EXTINCT"
    assert result["late_population_mean"] is None  # N/Aのまま。誤PASSしない
