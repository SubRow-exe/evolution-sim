"""Exp09条件Configの事前登録条件を機械的に守る (docs/Exp09_実験計画.md §7)。

Exp09で変えてよいのは「光/chemicalの有無」と「診断表現型」だけである。
世界パラメータはV1.4で確定した恒久default、受容器スケールはV1.5 defaultのまま
でなければならない。
"""
import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evosim.config import Config
from tools.make_exp09_configs import (CONDITIONS, FIXED, OUT_DIR, PHENOTYPES,
                                      build, config_name)

# 条件ごとに変わってよい項目 (世界のsource構成と診断表現型)
VARIABLE = {"light_pattern", "light_max", "chem_vent_flux",
            "diagnostic_placement", "diagnostic_gene_overrides"}

# `configs/exp09/` は実行済みExp09 (V1.5) の記録なので再生成しない。
# V1.6以降に追加されたConfig項目は当時のファイルに存在しないため、
# 「後から増えた項目か」だけを確認し、V1.5当時の項目は厳密一致で守る。
POST_V15_KEYS = {"memory_tau", "response_gain",
                 # V1.7 基礎維持代謝 (docs/V1.7_基礎維持代謝仕様案.md)
                 "bmr_core"}


def load(condition: str) -> dict:
    path = OUT_DIR / config_name(condition)
    assert path.exists(), f"{path} が無い (make_exp09_configs.py を実行すること)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_configs_exist_and_match_generator():
    for condition in CONDITIONS:
        stored = load(condition)
        generated = dataclasses.asdict(build(condition))
        added = set(generated) - set(stored)
        assert added <= POST_V15_KEYS, (
            f"{condition}: Exp09当時に無かった項目 {added} は V1.6以降の "
            "追加分として POST_V15_KEYS へ明示すること")
        assert set(stored) - set(generated) == set(), (
            f"{condition}: 現行Configから消えた項目がある")
        for key, value in stored.items():
            assert generated[key] == value, (
                f"{condition}: {key} が生成物と一致しない")


def test_condition_count_is_pre_registered():
    """control 2条件 + mixed 3条件 = 5条件 (計画 §7)。"""
    assert len(CONDITIONS) == 5
    assert sum(1 for c in CONDITIONS if c.startswith(("c_", "d_", "e_"))) == 3


@pytest.mark.parametrize("condition", list(CONDITIONS))
def test_world_defaults_are_the_v14_v15_defaults(condition):
    cfg = load(condition)
    d = Config()
    for key in ("light_uptake_coef", "chem_uptake", "n_vents",
                "vent_radius_cells", "chem_loss_frac",
                "light_stimulus_half", "chemical_stimulus_half",
                "stimulus_tie_eps"):
        assert cfg[key] == getattr(d, key), f"{condition}: {key} がdefaultでない"


@pytest.mark.parametrize("condition", list(CONDITIONS))
def test_diagnostic_phenotype_is_fixed(condition):
    cfg = load(condition)
    _, pheno = CONDITIONS[condition]
    assert cfg["diagnostic_gene_overrides"] == PHENOTYPES[pheno]
    assert set(cfg["fixed_genes"]) == set(FIXED), "両能力とも固定していない"


def test_light_only_control_has_no_chemical_source():
    cfg = load("a_light_only_lightspec")
    assert cfg["chem_vent_flux"] == 0.0
    assert cfg["light_max"] == Config().light_max
    assert cfg["n_vents"] == 4, "n_vents=0 にしない (乱数消費を揃える)"


def test_chemical_only_control_is_dark_and_vent_placed():
    cfg = load("b_chem_only_chemspec")
    assert cfg["light_max"] == 0.0
    assert cfg["chem_vent_flux"] == Config().chem_vent_flux
    assert cfg["diagnostic_placement"] == "vent"


@pytest.mark.parametrize("condition", ["c_mixed_lightspec", "d_mixed_chemspec",
                                       "e_mixed_generalist"])
def test_mixed_conditions_have_both_sources_and_same_world(condition):
    cfg = load(condition)
    d = Config()
    assert cfg["light_pattern"] == "vertical" and cfg["light_max"] == d.light_max
    assert cfg["chem_vent_flux"] == d.chem_vent_flux
    assert cfg["diagnostic_placement"] == "random", "混合条件は配置を揃える"


def test_only_source_and_phenotype_differ():
    """source構成と表現型以外は5 Configすべてで同一。"""
    base = None
    for condition in CONDITIONS:
        cfg = {k: v for k, v in load(condition).items() if k not in VARIABLE}
        if base is None:
            base = cfg
        else:
            assert cfg == base, f"{condition} で事前登録外の項目が違う"


def test_intervals_are_pre_registered():
    for condition in CONDITIONS:
        cfg = load(condition)
        assert cfg["stats_interval"] == 20
        assert cfg["snapshot_interval"] == 1000


def test_phenotypes_match_the_plan():
    assert PHENOTYPES["lightspec"] == {"light_absorption": 2.0,
                                       "chemical_absorption": 0.3}
    assert PHENOTYPES["chemspec"] == {"light_absorption": 0.3,
                                      "chemical_absorption": 2.0}
    assert PHENOTYPES["generalist"] == {"light_absorption": 1.0,
                                        "chemical_absorption": 1.0}
