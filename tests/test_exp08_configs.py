"""Exp08条件Configの事前登録条件を機械的に守る (docs/Exp08_実験計画.md §4-5)。

Exp08で振ってよい世界パラメータは、Phase Aでは `light_uptake_coef` だけ、
Phase Bでは `chem_vent_flux` だけである。9個のConfigを手で並べると、
1ファイルだけ他の値がずれていても気づけない。ここでは
「生成物と一致するか」と「振る対象と診断条件以外は同一か」を固定する。
"""
import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evosim.config import Config
from tools.make_exp08_configs import (CHEM_FLUXES, L2_COEF, LIGHT_COEFS,
                                      OUT_DIR, build_b, build_l0, build_l2,
                                      cases, flux_name, l0_name, l2_name)

# `configs/exp08/` は実行済みExp08 (V1.4) の記録なので再生成しない。
# V1.5以降に追加されたConfig項目は当時のファイルに存在しないため、
# 「後から増えた項目か」だけを確認し、V1.4当時の項目は厳密一致で守る。
POST_V14_KEYS = {"light_stimulus_half", "chemical_stimulus_half",
                 "stimulus_tie_eps",
                 # V1.6 temporal biased random walk
                 "memory_tau", "response_gain"}

# Phase A内で条件ごとに変わってよい項目
A_VARIABLE = {"light_uptake_coef", "diagnostic_gene_overrides"}
# Phase B内で条件ごとに変わってよい項目
B_VARIABLE = {"chem_vent_flux"}


def load(name: str) -> dict:
    path = OUT_DIR / name
    assert path.exists(), f"{path} が無い (make_exp08_configs.py を実行すること)"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_matches_generator(name: str, cfg) -> None:
    stored = load(name)
    generated = dataclasses.asdict(cfg)
    added = set(generated) - set(stored)
    assert added <= POST_V14_KEYS, (
        f"{name}: Exp08当時に無かった項目 {added} は V1.5以降の追加分として "
        "POST_V14_KEYS へ明示すること")
    assert set(stored) - set(generated) == set(), (
        f"{name}: 現行Configから消えた項目がある")
    for key, value in stored.items():
        assert generated[key] == value, f"{name}: {key} が生成物と一致しない"


def test_all_configs_exist_and_match_generator():
    for name, cfg in cases():
        _assert_matches_generator(name, cfg)


def test_case_count_is_pre_registered():
    """Phase A 6 (L0 5水準 + L2 1水準) + Phase B 3 = 9 Config。"""
    assert len(LIGHT_COEFS) == 5
    assert len(CHEM_FLUXES) == 3
    assert len(cases()) == len(LIGHT_COEFS) + 1 + len(CHEM_FLUXES) == 9


@pytest.mark.parametrize("coef", LIGHT_COEFS)
def test_phase_a_l0_fixes_ancestor_light_absorption(coef):
    """L0は祖先の初期値のまま固定する (上書きしない)。"""
    cfg = load(l0_name(coef))
    assert cfg["fixed_genes"] == ["light_absorption"]
    assert cfg["diagnostic_gene_overrides"] == {}
    assert cfg["light_uptake_coef"] == coef


def test_phase_a_l2_is_a_single_level_positive_control():
    cfg = load(l2_name(L2_COEF))
    assert cfg["diagnostic_gene_overrides"] == {"light_absorption": 2.0}
    assert "light_absorption" in cfg["fixed_genes"]
    assert cfg["light_uptake_coef"] == L2_COEF
    l2_files = sorted(OUT_DIR.glob("exp08_a_l2_*.json"))
    assert len(l2_files) == 1, "L2は1水準のみ (計画 §4.3)"


@pytest.mark.parametrize("coef", LIGHT_COEFS)
def test_phase_a_is_light_only_but_keeps_vent_rng(coef):
    """光単独。ただし n_vents=4 を維持して乱数消費をPhase Bと揃える。"""
    cfg = load(l0_name(coef))
    assert cfg["light_pattern"] == "vertical"
    assert cfg["light_max"] == Config().light_max
    assert cfg["chem_vent_flux"] == 0.0
    assert cfg["n_vents"] == 4, "n_vents=0 にしない (計画 §4.1)"


@pytest.mark.parametrize("flux", CHEM_FLUXES)
def test_phase_b_is_dark_and_vent_placed(flux):
    cfg = load(flux_name(flux))
    assert cfg["light_max"] == 0.0
    assert cfg["chem_vent_flux"] == flux
    assert cfg["chem_uptake"] == 0.5, "chem_uptakeはExp08で固定 (計画 §7.3)"
    assert cfg["diagnostic_placement"] == "vent"
    assert cfg["diagnostic_gene_overrides"] == {"chemical_absorption": 2.0}
    assert "chemical_absorption" in cfg["fixed_genes"]


def test_only_the_pre_registered_axis_differs_within_phase_a():
    base = None
    for coef in LIGHT_COEFS:
        cfg = {k: v for k, v in load(l0_name(coef)).items() if k not in A_VARIABLE}
        if base is None:
            base = cfg
        else:
            assert cfg == base, f"L0 coef={coef} で light_uptake_coef 以外が違う"
    l2 = {k: v for k, v in load(l2_name(L2_COEF)).items() if k not in A_VARIABLE}
    assert l2 == base, "L2がL0とlight_uptake_coef/上書き以外で違う"


def test_only_flux_differs_within_phase_b():
    base = None
    for flux in CHEM_FLUXES:
        cfg = {k: v for k, v in load(flux_name(flux)).items() if k not in B_VARIABLE}
        if base is None:
            base = cfg
        else:
            assert cfg == base, f"flux={flux} で chem_vent_flux 以外が違う"


def test_intervals_are_pre_registered():
    for name, _ in cases():
        cfg = load(name)
        assert cfg["stats_interval"] == 20
        assert cfg["snapshot_interval"] == 1000


def test_generator_functions_match_files():
    _assert_matches_generator(l0_name(LIGHT_COEFS[0]), build_l0(LIGHT_COEFS[0]))
    _assert_matches_generator(l2_name(L2_COEF), build_l2(L2_COEF))
    _assert_matches_generator(flux_name(CHEM_FLUXES[0]), build_b(CHEM_FLUXES[0]))
