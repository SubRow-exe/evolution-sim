"""Exp07条件Configの事前登録条件を機械的に守る (docs/Exp07_実験計画.md §3-5)。

Exp07で振ってよい世界パラメータは `chem_vent_flux` **だけ**である。
24個のConfigを手で並べると、1ファイルだけ他の値がずれていても気づけない。
ここでは「生成物と一致するか」と「fluxと診断条件以外は全条件で同一か」を
テストで固定する。
"""
import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evosim.config import Config
from tools.make_exp07_configs import (CONDITIONS, FLUXES, OUT_DIR, build,
                                      config_name)

DIAGNOSTIC_KEYS = {"chem_vent_flux", "diagnostic_placement",
                   "diagnostic_gene_overrides", "fixed_genes"}

# `configs/exp07/` は実行済みExp07 (V1.3) の記録なので再生成しない。
# V1.4以降に追加されたConfig項目は当時のファイルに存在しないため、
# 「後から増えた項目か」だけを確認し、V1.3当時の項目は厳密一致で守る。
POST_V13_KEYS = {"light_uptake_coef", "light_stimulus_half",
                 "chemical_stimulus_half", "stimulus_tie_eps",
                 # V1.6 temporal biased random walk
                 "memory_tau", "response_gain",
                 # V1.7 基礎維持代謝 (docs/V1.7_基礎維持代謝仕様案.md)
                 "bmr_core"}


def load(flux: float, condition: str) -> dict:
    path = OUT_DIR / config_name(flux, condition)
    assert path.exists(), f"{path} が無い (make_exp07_configs.py を実行すること)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_configs_exist_and_match_generator():
    for flux in FLUXES:
        for cond in CONDITIONS:
            stored = load(flux, cond)
            generated = dataclasses.asdict(build(flux, cond))
            added = set(generated) - set(stored)
            assert added <= POST_V13_KEYS, (
                f"{config_name(flux, cond)}: Exp07当時に無かった項目 {added} は "
                "V1.4以降の追加分としてPOST_V13_KEYSへ明示すること")
            assert set(stored) - set(generated) == set(), (
                f"{config_name(flux, cond)}: 現行Configから消えた項目がある")
            for key, value in stored.items():
                assert generated[key] == value, (
                    f"{config_name(flux, cond)}: {key} が生成物と一致しない")


def test_only_flux_and_diagnostics_differ():
    """fluxと診断条件以外は24 Configすべてで同一であること。"""
    base = None
    for flux in FLUXES:
        for cond in CONDITIONS:
            cfg = {k: v for k, v in load(flux, cond).items()
                   if k not in DIAGNOSTIC_KEYS}
            if base is None:
                base = cfg
            else:
                diff = {k for k in base if base[k] != cfg[k]}
                assert not diff, f"flux{flux} {cond} で余計な差分: {diff}"


def test_flux_matches_filename_and_sweep():
    for flux in FLUXES:
        for cond in CONDITIONS:
            assert load(flux, cond)["chem_vent_flux"] == flux
    assert set(FLUXES) == {4.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0}


def test_all_conditions_are_dark():
    for flux in FLUXES:
        for cond in CONDITIONS:
            c = load(flux, cond)
            assert c["light_max"] == 0.0
            assert c["light_pattern"] == "uniform"


def test_observation_intervals_are_preregistered():
    for flux in FLUXES:
        for cond in CONDITIONS:
            c = load(flux, cond)
            assert c["stats_interval"] == 20
            assert c["snapshot_interval"] == 1000


@pytest.mark.parametrize("cond", ["c_chem_vent", "d_chem_random"])
def test_chem_adapted_conditions_fix_the_gene(cond):
    for flux in FLUXES:
        c = load(flux, cond)
        assert c["diagnostic_gene_overrides"] == {"chemical_absorption": 2.0}
        assert c["fixed_genes"] == ["chemical_absorption"]


def test_ancestor_condition_is_untouched():
    for flux in FLUXES:
        c = load(flux, "b_ancestor_vent")
        assert c["diagnostic_gene_overrides"] == {}
        assert c["fixed_genes"] == []


def test_placements():
    for flux in FLUXES:
        assert load(flux, "b_ancestor_vent")["diagnostic_placement"] == "vent"
        assert load(flux, "c_chem_vent")["diagnostic_placement"] == "vent"
        assert load(flux, "d_chem_random")["diagnostic_placement"] == "random"


def test_configs_load_and_source_total_matches_nominal():
    """Configから世界を作ると実効sourceが公称値と一致する (全flux)。"""
    import numpy as np
    from evosim.world import World
    for flux in FLUXES:
        cfg = Config.from_json(OUT_DIR / config_name(flux, "c_chem_vent"))
        for seed in (1, 5, 10):
            w = World(cfg, np.random.Generator(np.random.PCG64(seed)))
            assert w.chem_source_total == pytest.approx(cfg.n_vents * flux, rel=1e-12)
