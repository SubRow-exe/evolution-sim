"""Exp11 Config 整合性テスト (docs/Exp11_実験計画案.md Phase 0 §P0-4, P0-5)。

P0-4: 全 45 Config で fixed_genes が canonical な
      evosim.genome.GENE_NAMES - {"body_size"} と完全一致することを検証する。
      ローカルに遺伝子名リストを書き写さない — 手書きリストと生成物・checker
      が同じ間違いを共有して全部通過する事故 (2026-09 Exp11 全job失敗の原因)
      を構造的に防ぐため、必ず GENE_NAMES から集合演算で導出する。
P0-5: 全 45 Config で bmr_core の JSON round-trip が一致する。

check_exp11.py と同じ検証を pytest で実行する (CI の停止条件)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES, fixed_mask_from_names

CONFIGS_DIR = ROOT / "configs" / "exp11"

BMR_CORE_CANDIDATES = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

# canonical: body_size 以外の全遺伝子。ローカルにリストを書き写さない。
EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}

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
    """全 Config の bmr_core が候補15水準のいずれかに属する。"""
    for d in config_data:
        core = d["bmr_core"]
        ok = any(abs(core - c) < 1e-9 for c in BMR_CORE_CANDIDATES)
        assert ok, f"bmr_core={core} は候補 15 水準に含まれない"


@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_fixed_genes_exact_match(path):
    """fixed_genes が GENE_NAMES - {"body_size"} と完全一致する (集合として直接比較)。

    件数比較やローカル定数との比較では、Config生成側とテスト側が同じ
    間違った遺伝子名を共有していても検出できない。canonical な GENE_NAMES
    と直接比較することで、不足・過剰・誤字のいずれも検出する。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    fg = set(data.get("fixed_genes", []))
    assert fg == EXPECTED_FIXED_GENES, (
        f"{path.name}: fixed_genes が GENE_NAMES-{{'body_size'}} と不一致。\n"
        f"  不足: {sorted(EXPECTED_FIXED_GENES - fg)}\n"
        f"  想定外: {sorted(fg - EXPECTED_FIXED_GENES)}"
    )


@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_body_size_not_fixed(path):
    """body_size が fixed_genes に含まれない (進化 ON を保証する)。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    fg = data.get("fixed_genes", [])
    assert "body_size" not in fg, (
        f"{path.name}: body_size が fixed_genes に含まれている → 進化 OFF になる"
    )


@pytest.mark.parametrize("path", all_config_paths(),
                         ids=[p.name for p in all_config_paths()])
def test_fixed_genes_pass_fixed_mask_from_names(path):
    """fixed_genes が genome.fixed_mask_from_names() を実際に通る。

    Config.from_json() が例外を出さないことだけでは、fixed_genes の中身が
    Simulation 初期化時に使われる fixed_mask_from_names() を通るかまでは
    保証しない (Simulation.__init__ が実際に呼ぶ関数まで直接検証する)。
    未知の遺伝子名があればここで ValueError になる。
    """
    from evosim.config import Config

    cfg = Config.from_json(path)
    mask = fixed_mask_from_names(cfg.fixed_genes)  # raise しなければ OK
    assert mask is not None
    assert mask.sum() == 13, f"{path.name}: 固定される遺伝子数が13でない ({mask.sum()})"


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


# ---------------------------------------------------------------------------
# Simulation 初期化 smoke test
# ---------------------------------------------------------------------------
# Config.from_json() や fixed_mask_from_names() が個別に通っても、
# Simulation.__init__ の実際の経路 (Config → genome → Simulation) が
# 通ることまでは保証しない。今回の全job失敗はまさに実行直前の
# Simulation 初期化で ValueError が出たことが原因だったため、
# 各環境代表 Config で実際に Simulation を構築できることを確認する。

@pytest.mark.parametrize("env", ENVS)
def test_simulation_initializes(env, config_paths):
    """各環境の代表 Config (bmr_core=0.000) で Simulation の生成まで実行できる。"""
    from evosim.config import Config
    from evosim.simulation import Simulation

    matching = [p for p in config_paths if env in p.name and "bmr0.000" in p.name]
    assert matching, f"{env} の bmr_core=0.000 Config が見つからない"

    cfg = Config.from_json(matching[0])
    sim = Simulation(cfg, seed=1)  # raise しなければ OK
    assert len(sim.organisms) == cfg.initial_population


def test_simulation_runs_a_few_ticks_smoke():
    """少なくとも1 Config で数 tick 実際に進めても例外が出ない (smoke test)。"""
    from evosim.config import Config
    from evosim.simulation import Simulation

    paths = all_config_paths()
    target = next(p for p in paths if "B1_lightonly_lightspec_bmr0.030" in p.name)
    cfg = Config.from_json(target)
    sim = Simulation(cfg, seed=1)
    for _ in range(5):
        sim.step()  # raise しなければ OK
