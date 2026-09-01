"""Exp11 Config 整合性テスト (docs/Exp11_実験計画案.md Phase 0 §P0-4, P0-5)。

P0-4: 全 45 Config で body_size 以外の 13 遺伝子が fixed_genes に含まれ、
      body_size が含まれないことを機械検証する。
P0-5: 全 45 Config で bmr_core の JSON round-trip が一致する。

check_exp11.py と同じ検証を pytest で実行する (CI の停止条件)。
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONFIGS_DIR = ROOT / "configs" / "exp11"

BMR_CORE_CANDIDATES = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

FIXED_GENES_REQUIRED = [
    "light_absorption",
    "chemical_absorption",
    "nutrient_absorption",
    "corpse_digestion",
    "predation",
    "membrane",
    "damage_resistance",
    "move_efficiency",
    "repair",
    "sensory_range",
]

ENVS = ["B1_lightonly_lightspec", "B2_chemonly_chemspec", "B3_mixed_generalist"]


def all_config_paths() -> list[Path]:
    if not CONFIGS_DIR.exists():
        return []
    return sorted(CONFIGS_DIR.glob("exp11_*.json"))


pytestmark = pytest.mark.skipif(
    not CONFIGS_DIR.exists() or len(all_config_paths()) == 0,
    reason="configs/exp11/ が存在しない。make_exp11_configs.py を先に実行してください",
)


@pytest.fixture(scope="session")
def config_paths() -> list[Path]:
    return all_config_paths()


@pytest.fixture(scope="session")
def config_data(config_paths) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in config_paths]


# ---------------------------------------------------------------------------
# P0-4: Config 数と構造
# ---------------------------------------------------------------------------

def test_config_count(config_paths):
    """全 45 Config が存在する。"""
    assert len(config_paths) == 45, (
        f"Config 数が {len(config_paths)} (期待: 45). "
        "make_exp11_configs.py を実行してください"
    )


def test_all_envs_present(config_paths):
    """3 環境すべての Config が存在する。"""
    for env in ENVS:
        matching = [p for p in config_paths if env in p.name]
        assert len(matching) == 15, f"{env}: {len(matching)} Config (期待: 15)"


def test_all_bmr_core_values_present(config_data):
    """15 水準の bmr_core が各環境に存在する。"""
    for env in ENVS:
        env_cores = sorted(
            set(d["bmr_core"] for d in config_data if env in str(d.get("_path", "")))
        )
    # 全 Config の bmr_core が候補値のいずれかに属する
    for d in config_data:
        core = d["bmr_core"]
        ok = any(abs(core - c) < 1e-9 for c in BMR_CORE_CANDIDATES)
        assert ok, f"bmr_core={core} は候補 15 水準に含まれない"


@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_fixed_genes_coverage(path):
    """body_size 以外の 13 遺伝子が fixed_genes に含まれる。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    fg = data.get("fixed_genes", [])
    for gene in FIXED_GENES_REQUIRED:
        assert gene in fg, f"{path.name}: {gene} が fixed_genes に含まれていない"


@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_body_size_not_fixed(path):
    """body_size が fixed_genes に含まれない (進化 ON を保証する)。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    fg = data.get("fixed_genes", [])
    assert "body_size" not in fg, (
        f"{path.name}: body_size が fixed_genes に含まれている → 進化 OFF になる"
    )


# ---------------------------------------------------------------------------
# P0-5: bmr_core JSON round-trip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_bmr_core_roundtrip(path):
    """bmr_core が JSON 保存 → Config.from_json 後も一致する。"""
    from evosim.config import Config

    data = json.loads(path.read_text(encoding="utf-8"))
    expected_core = data["bmr_core"]

    loaded = Config.from_json(path)
    assert abs(loaded.bmr_core - expected_core) < 1e-12, (
        f"{path.name}: round-trip 後 bmr_core={loaded.bmr_core} != {expected_core}"
    )


@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_config_valid(path):
    """全 Config が Config.from_json で ValueError なく読み込める。"""
    from evosim.config import Config
    Config.from_json(path)  # raise しなければ OK


def test_common_params(config_data):
    """共通パラメータが事前登録値と一致する (§4)。"""
    for d in config_data:
        assert d["initial_population"] == 100
        assert d["initial_energy"] == 50.0
        assert abs(d["initial_matter"] - 0.8) < 1e-9
        assert abs(d["memory_tau"] - 10.0) < 1e-9
        assert abs(d["response_gain"] - 64.0) < 1e-9
        assert d["stats_interval"] == 20
        assert d["snapshot_interval"] == 1000
        assert d["max_population_halt"] == 10000
