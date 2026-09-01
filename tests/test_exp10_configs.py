"""Exp10 Phase B 条件Configの事前登録条件を機械的に守る。

Issue #41「Phase B 正式再トライアル方針」に従い、Phase Bは
**進化OFF・固定表現型**でなければならない。旧実装は light/chemical の
2吸収能力しか固定しておらず、body_size 等の残り12遺伝子が自由進化していた
(中間報告の個体数20倍・小型化はその帰結)。この回帰を二度と通さないため、
「全14遺伝子が固定されていること」をテストで固定する。

Exp10で条件ごとに変えてよいのは「光/chemicalの有無」「診断表現型
(2吸収能力の初期値)」「行動則パラメータ (response_gain / memory_tau)」だけ。
"""
import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evosim.config import Config
from evosim.genome import GENE_NAMES, N_GENES
from tools.make_exp10_configs import (CONDITIONS, FIXED, OUT_DIR, PHENOTYPES,
                                      RULES, build, config_name, load_selection)

# 条件・行動則で変わってよい項目
VARIABLE = {"light_pattern", "light_max", "chem_vent_flux",
            "diagnostic_placement", "diagnostic_gene_overrides",
            "response_gain", "memory_tau"}

# `configs/exp10/` は実行済みExp10 (V1.6) の記録なので再生成しない。
# V1.7以降に追加されたConfig項目は当時のファイルに存在しないため、
# 「後から増えた項目か」だけを確認し、V1.6当時の項目は厳密一致で守る。
POST_V16_KEYS = {"bmr_core"}  # V1.7 基礎維持代謝 (docs/V1.7_基礎維持代謝仕様案.md)


def load(condition: str, rule: str) -> dict:
    path = OUT_DIR / config_name(condition, rule)
    assert path.exists(), f"{path} が無い (make_exp10_configs.py を実行すること)"
    return json.loads(path.read_text(encoding="utf-8"))


def all_cases():
    return [(c, r) for c in CONDITIONS for r in RULES]


def test_all_configs_exist_and_match_generator():
    sel = load_selection()
    for condition, rule in all_cases():
        stored = load(condition, rule)
        generated = dataclasses.asdict(build(condition, rule, sel))
        added = set(generated) - set(stored)
        assert added <= POST_V16_KEYS, (
            f"{condition}/{rule}: Exp10当時に無かった項目 {added} は V1.7以降の "
            "追加分として POST_V16_KEYS へ明示すること")
        assert set(stored) - set(generated) == set(), (
            f"{condition}/{rule}: 現行Configから消えた項目がある")
        for key, value in stored.items():
            assert generated[key] == value, (
                f"{condition}/{rule}: {key} が生成物と一致しない "
                f"(make_exp10_configs.py を再実行すること)")


def test_phase_b_is_evolution_off_all_genes_fixed():
    """進化OFFの核心: 全14遺伝子が fixed_genes に入っていること。"""
    assert set(FIXED) == set(GENE_NAMES)
    assert len(FIXED) == N_GENES
    for condition, rule in all_cases():
        cfg = load(condition, rule)
        assert set(cfg["fixed_genes"]) == set(GENE_NAMES), (
            f"{condition}/{rule}: 全遺伝子が固定されていない "
            f"(進化OFFが崩れる。fixed={sorted(cfg['fixed_genes'])})")


@pytest.mark.parametrize("condition,rule", all_cases())
def test_only_phenotype_two_genes_are_overridden(condition, rule):
    """初期値の上書きは表現型2遺伝子だけ。残りは INITIAL_GENOME 据え置き。"""
    cfg = load(condition, rule)
    _, pheno = CONDITIONS[condition]
    assert cfg["diagnostic_gene_overrides"] == PHENOTYPES[pheno]
    assert set(cfg["diagnostic_gene_overrides"]) == {"light_absorption",
                                                     "chemical_absorption"}


@pytest.mark.parametrize("condition,rule", all_cases())
def test_world_defaults_are_the_permanent_defaults(condition, rule):
    cfg = load(condition, rule)
    d = Config()
    for key in ("light_uptake_coef", "chem_uptake", "n_vents",
                "vent_radius_cells", "light_stimulus_half",
                "chemical_stimulus_half", "stimulus_tie_eps"):
        assert cfg[key] == getattr(d, key), (
            f"{condition}/{rule}: {key} がdefaultでない")


@pytest.mark.parametrize("condition", list(CONDITIONS))
def test_control_is_pure_random_walk(condition):
    """control は response_gain=0。treatment/control で memory_tau は同一。"""
    ctrl = load(condition, "control")
    treat = load(condition, "treatment")
    assert ctrl["response_gain"] == 0.0
    assert treat["response_gain"] != 0.0
    assert ctrl["memory_tau"] == treat["memory_tau"], (
        f"{condition}: 行動則の軸だけを振る (memory_tau は control/treatment 同一)")


def test_condition_count_is_pre_registered():
    """5条件 × control/treatment = 10 Config (計画 §5)。"""
    assert len(CONDITIONS) == 5
    assert len(all_cases()) == 10


def test_source_configuration_per_condition():
    d = Config()
    assert load("b1_light_only_lightspec", "control")["chem_vent_flux"] == 0.0
    b2 = load("b2_chem_only_chemspec", "control")
    assert b2["light_max"] == 0.0 and b2["diagnostic_placement"] == "vent"
    for c in ("b3_mixed_lightspec", "b4_mixed_chemspec", "b5_mixed_generalist"):
        cfg = load(c, "control")
        assert cfg["light_max"] == d.light_max and cfg["chem_vent_flux"] > 0.0


def test_phenotypes_match_the_plan():
    assert PHENOTYPES["lightspec"] == {"light_absorption": 2.0,
                                       "chemical_absorption": 0.3}
    assert PHENOTYPES["chemspec"] == {"light_absorption": 0.3,
                                      "chemical_absorption": 2.0}
    assert PHENOTYPES["generalist"] == {"light_absorption": 1.0,
                                        "chemical_absorption": 1.0}
