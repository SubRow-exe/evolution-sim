"""Exp12 Config 整合性テスト (docs/Exp12_実験計画確定.md §5 P0-1, §19)。

期待値はテスト内で独立に (実装のローカル定数を再利用せず) 事前登録値として
書き下す。これはExp11 fixed_genes事故の再発防止 (Config生成・checker・test
が同じ間違った定数を共有して全部通る事故) に対応する。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES, fixed_mask_from_names

CONFIGS_DIR = ROOT / "configs" / "exp12"

# 事前登録値を独立に書き下す (docs/Exp12_実験計画確定.md §3, §18)
EXPECTED_B1_BMR = [0.000, 0.050, 0.075, 0.100, 0.150, 0.200, 0.300]
EXPECTED_B2_BMR = [0.000, 0.100, 0.300]
EXPECTED_B1_SEEDS = list(range(1, 9))
EXPECTED_B2_SEEDS = list(range(1, 6))
EXPECTED_B1_JOBS = 7 * 8   # 56
EXPECTED_B2_JOBS = 3 * 5   # 15
EXPECTED_TOTAL = 71

EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}


def all_config_paths() -> list[Path]:
    if not CONFIGS_DIR.exists():
        return []
    return sorted(CONFIGS_DIR.glob("exp12_*.json"))


pytestmark = pytest.mark.skipif(
    not CONFIGS_DIR.exists() or len(all_config_paths()) == 0,
    reason="configs/exp12/ が存在しない。make_exp12_configs.py を先に実行してください",
)


@pytest.fixture(scope="session")
def config_paths() -> list[Path]:
    return all_config_paths()


@pytest.fixture(scope="session")
def config_data(config_paths) -> dict[str, dict]:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in config_paths}


# ---------------------------------------------------------------------------
# §19-1/2: 71条件matrix件数テスト (Config単位 + seed展開の独立検算)
# ---------------------------------------------------------------------------

def test_config_count_is_10(config_paths):
    """Config自体は bmr_core×環境の組で 7(B1) + 3(B2) = 10 ファイル。"""
    assert len(config_paths) == 7 + 3


def test_b1_bmr_values_exact_match(config_data):
    b1_names = [n for n in config_data if "B1" in n]
    assert len(b1_names) == 7
    cores = sorted(config_data[n]["bmr_core"] for n in b1_names)
    assert cores == EXPECTED_B1_BMR


def test_b2_bmr_values_exact_match(config_data):
    b2_names = [n for n in config_data if "B2" in n]
    assert len(b2_names) == 3
    cores = sorted(config_data[n]["bmr_core"] for n in b2_names)
    assert cores == EXPECTED_B2_BMR


def test_seed_expansion_total_is_71():
    """Config×seed展開 (workflow matrix相当) が71 runになることを独立に検算する。"""
    b1_total = len(EXPECTED_B1_BMR) * len(EXPECTED_B1_SEEDS)
    b2_total = len(EXPECTED_B2_BMR) * len(EXPECTED_B2_SEEDS)
    assert b1_total == EXPECTED_B1_JOBS
    assert b2_total == EXPECTED_B2_JOBS
    assert b1_total + b2_total == EXPECTED_TOTAL


# ---------------------------------------------------------------------------
# fixed_genes canonical一致 (§19-3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", all_config_paths(), ids=[p.name for p in all_config_paths()])
def test_fixed_genes_exact_match(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    fg = set(data.get("fixed_genes", []))
    assert fg == EXPECTED_FIXED_GENES, (
        f"{path.name}: fixed_genes不一致\n"
        f"  不足: {sorted(EXPECTED_FIXED_GENES - fg)}\n"
        f"  想定外: {sorted(fg - EXPECTED_FIXED_GENES)}"
    )


@pytest.mark.parametrize("path", all_config_paths(), ids=[p.name for p in all_config_paths()])
def test_body_size_not_fixed(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "body_size" not in data.get("fixed_genes", [])


@pytest.mark.parametrize("path", all_config_paths(), ids=[p.name for p in all_config_paths()])
def test_fixed_genes_pass_fixed_mask_from_names(path):
    from evosim.config import Config
    cfg = Config.from_json(path)
    mask = fixed_mask_from_names(cfg.fixed_genes)
    assert mask is not None
    assert mask.sum() == 13


# ---------------------------------------------------------------------------
# bmr_core round-trip (§19-5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", all_config_paths(), ids=[p.name for p in all_config_paths()])
def test_bmr_core_roundtrip(path):
    from evosim.config import Config
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = data["bmr_core"]
    loaded = Config.from_json(path)
    assert abs(loaded.bmr_core - expected) < 1e-12


@pytest.mark.parametrize("path", all_config_paths(), ids=[p.name for p in all_config_paths()])
def test_config_valid(path):
    from evosim.config import Config
    Config.from_json(path)


# ---------------------------------------------------------------------------
# 共通パラメータ (§4, §5 P0-1)
# ---------------------------------------------------------------------------

def test_common_params(config_data):
    for name, d in config_data.items():
        assert d["initial_population"] == 100, name
        assert d["initial_energy"] == 50.0, name
        assert abs(d["initial_matter"] - 0.8) < 1e-9, name
        assert abs(d["memory_tau"] - 10.0) < 1e-9, name
        assert abs(d["response_gain"] - 64.0) < 1e-9, name
        assert d["stats_interval"] == 20, name
        assert d["snapshot_interval"] == 1000, name
        assert d["max_population_halt"] == 10000, name


def test_b1_environment_matches_exp11_template(config_data):
    for name, d in config_data.items():
        if "B1" not in name:
            continue
        assert d["light_pattern"] == "vertical"
        assert d["chem_vent_flux"] == 0.0
        assert d["diagnostic_placement"] == "random"
        assert d["diagnostic_gene_overrides"] == {"light_absorption": 2.0, "chemical_absorption": 0.3}


def test_b2_environment_matches_exp11_template(config_data):
    for name, d in config_data.items():
        if "B2" not in name:
            continue
        assert d["light_max"] == 0.0
        assert d["chem_vent_flux"] == 16.0
        assert d["diagnostic_placement"] == "vent"
        assert d["diagnostic_gene_overrides"] == {"light_absorption": 0.3, "chemical_absorption": 2.0}


# ---------------------------------------------------------------------------
# Simulation smoke test (§19-4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "exp12_B1_lightonly_lightspec_bmr0.000.json",
    "exp12_B1_lightonly_lightspec_bmr0.100.json",
    "exp12_B1_lightonly_lightspec_bmr0.300.json",
    "exp12_B2_chemonly_chemspec_bmr0.000.json",
])
def test_simulation_smoke(name, config_paths):
    from evosim.config import Config
    from evosim.simulation import Simulation

    matching = [p for p in config_paths if p.name == name]
    assert matching, f"{name} が見つからない"
    cfg = Config.from_json(matching[0])
    sim = Simulation(cfg, seed=1)
    assert len(sim.organisms) == cfg.initial_population
    for _ in range(5):
        sim.step()
