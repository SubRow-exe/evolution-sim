"""V1.10 C/N/P資源分解の必須テスト (docs/V1.10_CNP資源分解_実装仕様.md)。

explicit_cnp_resources=False (既定) の既存V1.9経路はtests/test_conservation.py
やtests/test_v19_iluca.py等で既にカバーしている。ここではexplicit_cnp_
resources=True のときのstoichiometry / diffusion / growth limiter /
corpse-predation recycling / element ledger / determinismを検証する。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim import physiology, stoichiometry
from evosim.config import Config
from evosim.simulation import Simulation


def _cnp_cfg(**overrides) -> Config:
    """小さいgridのphysical_mode + explicit_cnp_resources reference config。"""
    kwargs = dict(
        physical_mode=True,
        explicit_cnp_resources=True,
        dt_seconds=10.0,
        world_width=0.020,
        world_height=0.020,
        cell_size=5.0e-4,
        effective_depth_m=5.0e-4,
        n_vents=4,
        vent_radius_cells=2,
        h2_source_concentration_molm3=10.0,
        h2_diffusion_m2s=5.0e-9,
        h2_exchange_tau_s=900.0,
        initial_population=20,
        initial_energy=0.0,
        initial_matter=0.50,
        nutrient_initial=0.0,
        child_matter_frac=0.50,
        birth_overhead=0.0,
        repro_matter_frac=1.0,
        metabolic_damage=0.0,
        movement_damage=0.0,
        speed_coef=40e-6,
        radius_coef=6.2e-7,
        sense_coef=5e-4,
        max_population_halt=2000,
    )
    kwargs.update(overrides)
    return Config(**kwargs)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def test_explicit_cnp_requires_physical_mode():
    with pytest.raises(ValueError):
        Config(explicit_cnp_resources=True, physical_mode=False)


def test_biomass_fractions_must_not_exceed_one():
    with pytest.raises(ValueError):
        Config(biomass_carbon_mass_frac=0.6, biomass_nitrogen_mass_frac=0.3,
              biomass_phosphorus_mass_frac=0.2)


def test_biomass_fractions_nonnegative():
    with pytest.raises(ValueError):
        Config(biomass_carbon_mass_frac=-0.1)


def test_cnp_background_and_diffusion_must_be_valid():
    with pytest.raises(ValueError):
        _cnp_cfg(dic_background_molm3=-1.0)
    with pytest.raises(ValueError):
        _cnp_cfg(d_dic_m2s=0.0)
    with pytest.raises(ValueError):
        _cnp_cfg(cnp_exchange_tau_s=0.0)
    with pytest.raises(ValueError):
        _cnp_cfg(cnp_subcycle_alpha_max=0.0)


def test_default_explicit_cnp_resources_is_false():
    """既定Falseでは既存V1.9経路に一切影響しない (docs §8)。"""
    cfg = Config()
    assert cfg.explicit_cnp_resources is False
    sim = Simulation(cfg, seed=1)
    assert not hasattr(sim.world, "dic")
    for _ in range(50):
        sim.step()
    assert sim.growth_limiter_cum == {
        "energy": 0, "kinetic": 0, "carbon": 0, "nitrogen": 0,
        "phosphorus": 0, "room": 0,
    }


# ---------------------------------------------------------------------------
# T-stoich: element stoichiometry helper (Step3)
# ---------------------------------------------------------------------------

def test_stoichiometry_reference_mol_per_kgdw():
    cfg = Config(explicit_cnp_resources=False)  # defaultフラクションだけ使う
    assert stoichiometry.carbon_mol_per_kgdw(cfg) == pytest.approx(0.47 / 0.012011)
    assert stoichiometry.nitrogen_mol_per_kgdw(cfg) == pytest.approx(0.11 / 0.014007)
    assert stoichiometry.phosphorus_mol_per_kgdw(cfg) == pytest.approx(0.02 / 0.030974)


def test_matter_to_element_mol_scales_linearly():
    cfg = Config()
    c1, n1, p1 = stoichiometry.matter_to_element_mol(1.0, cfg)
    c2, n2, p2 = stoichiometry.matter_to_element_mol(2.0, cfg)
    assert c2 == pytest.approx(2.0 * c1)
    assert n2 == pytest.approx(2.0 * n1)
    assert p2 == pytest.approx(2.0 * p1)
    assert c1 > 0.0 and n1 > 0.0 and p1 > 0.0


# ---------------------------------------------------------------------------
# World field init / diffusion (Step2)
# ---------------------------------------------------------------------------

def test_world_cnp_fields_initialize_to_background_no_rng():
    cfg = _cnp_cfg()
    sim1 = Simulation(cfg, seed=1)
    sim2 = Simulation(cfg, seed=2)  # 異なるseedでも初期fieldは同一 (RNG不使用)
    assert np.allclose(sim1.world.dic, cfg.dic_background_molm3)
    assert np.allclose(sim1.world.fixed_nitrogen, cfg.fixed_n_background_molm3)
    assert np.allclose(sim1.world.phosphate, cfg.phosphate_background_molm3)
    assert np.array_equal(sim1.world.dic, sim2.world.dic)


def test_cnp_diffusion_alone_conserves_total_no_organisms():
    """exchange OFF + 生物無し -> 拡散だけなので総量厳密保存 (境界反射)。"""
    cfg = _cnp_cfg(initial_population=0, cnp_background_exchange_enabled=False)
    sim = Simulation(cfg, seed=1)
    total0 = sim.world.total_dic()
    for _ in range(50):
        sim.world.update_cnp()
    assert sim.world.total_dic() == pytest.approx(total0, rel=1e-12)


def test_cnp_background_exchange_relaxes_toward_background():
    """exchange ONで摂動を与えたfieldはbackgroundへ緩和する。"""
    cfg = _cnp_cfg(initial_population=0, dic_background_molm3=2.2,
                   cnp_exchange_tau_s=90.0)
    sim = Simulation(cfg, seed=1)
    sim.world.dic[0, 0] = 100.0  # 局所的な摂動
    for _ in range(2000):
        sim.world.update_cnp()
    assert float(sim.world.dic.max()) == pytest.approx(cfg.dic_background_molm3, rel=1e-2)


def test_cfl_subcycle_alpha_within_bound():
    from evosim.world import _cfl_subcycle_params
    cfg = _cnp_cfg()
    n_sub, dt_sub, alpha = _cfl_subcycle_params(
        cfg.d_dic_m2s, cfg.dt_seconds, cfg.cell_size, cfg.cnp_subcycle_alpha_max)
    assert alpha <= cfg.cnp_subcycle_alpha_max + 1e-12
    assert n_sub >= 1


# ---------------------------------------------------------------------------
# Growth: stoichiometric mass balance + limiter classification (Step4)
# ---------------------------------------------------------------------------

def test_growth_consumes_cnp_in_fixed_stoichiometry():
    """biomass成長分だけ、固定biomass組成でC/N/P fieldが減ることを確認する。"""
    cfg = _cnp_cfg(initial_population=5, cnp_background_exchange_enabled=False)
    sim = Simulation(cfg, seed=3)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    m0 = sum(o.matter for o in sim.organisms)
    c0 = sim.world.total_dic()
    n0 = sim.world.total_fixed_nitrogen()
    p0 = sim.world.total_phosphate()
    for _ in range(100):
        sim.step()
    dm = sum(o.matter for o in sim.organisms) - m0
    assert dm > 0.0, "この条件でbiomassが成長しなかった (テスト前提が崩れている)"
    c_expected, n_expected, p_expected = stoichiometry.matter_to_element_mol(dm, cfg)
    assert (c0 - sim.world.total_dic()) == pytest.approx(c_expected, rel=1e-6)
    assert (n0 - sim.world.total_fixed_nitrogen()) == pytest.approx(n_expected, rel=1e-6)
    assert (p0 - sim.world.total_phosphate()) == pytest.approx(p_expected, rel=1e-6)
    assert sim.c_uptake_cum == pytest.approx(c_expected, rel=1e-6)


def test_growth_limiter_carbon_when_dic_scarce():
    """DICだけ極端に希少にすると growth_limiter が carbon 支配になる。"""
    cfg = _cnp_cfg(initial_population=10, cnp_background_exchange_enabled=False,
                   dic_background_molm3=2.2e-9)
    sim = Simulation(cfg, seed=4)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    for _ in range(300):
        sim.step()
    counts = sim.growth_limiter_cum
    assert counts["carbon"] > 0
    assert counts["carbon"] > counts["nitrogen"]
    assert counts["carbon"] > counts["phosphorus"]


def test_growth_limiter_nitrogen_when_fixed_n_scarce():
    cfg = _cnp_cfg(initial_population=10, cnp_background_exchange_enabled=False,
                   fixed_n_background_molm3=1.0e-11)
    sim = Simulation(cfg, seed=5)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    for _ in range(300):
        sim.step()
    counts = sim.growth_limiter_cum
    assert counts["nitrogen"] > 0
    assert counts["nitrogen"] > counts["carbon"]
    assert counts["nitrogen"] > counts["phosphorus"]


def test_growth_limiter_phosphorus_when_phosphate_scarce():
    cfg = _cnp_cfg(initial_population=10, cnp_background_exchange_enabled=False,
                   phosphate_background_molm3=1.0e-12)
    sim = Simulation(cfg, seed=6)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    for _ in range(300):
        sim.step()
    counts = sim.growth_limiter_cum
    assert counts["phosphorus"] > 0
    assert counts["phosphorus"] > counts["carbon"]
    assert counts["phosphorus"] > counts["nitrogen"]


def test_growth_limiter_room_when_at_capacity():
    # repro_matter_frac を届かない値にして、繁殖でmatterが動くのを防ぐ
    # (このテストはgrowthだけを孤立させて見たい)。
    cfg = _cnp_cfg(initial_population=3, matter_cap_frac=1.0, repro_matter_frac=999.0)
    sim = Simulation(cfg, seed=7)
    for o in sim.organisms:
        o.matter = o.target_size  # 既にcapacity上限
        o.energy = physiology.energy_max(o, cfg)
    sim.step()
    assert sim.growth_limiter_cum["room"] > 0
    assert all(o.matter == pytest.approx(o.target_size) for o in sim.organisms)


def test_growth_protected_reserve_blocks_growth_near_starvation():
    """energy < E_protected ならgrowthは0 (dm_energy<=0 -> limiter=energy)。"""
    cfg = _cnp_cfg(initial_population=1)
    sim = Simulation(cfg, seed=8)
    o = sim.organisms[0]
    o.energy = 1e-30  # ほぼ0。E_protectedを確実に下回る
    m0 = o.matter
    sim.step()
    assert o.matter == pytest.approx(m0)
    assert sim.growth_limiter_cum["energy"] >= 1


# ---------------------------------------------------------------------------
# Corpse / predation / waste recycling (Step5)
# ---------------------------------------------------------------------------

def test_corpse_decay_returns_cnp_in_fixed_stoichiometry():
    cfg = _cnp_cfg(initial_population=0, cnp_background_exchange_enabled=False)
    sim = Simulation(cfg, seed=9)
    from evosim.corpse import Corpse
    corpse = Corpse(0.001, 0.001, matter=5.0, energy=0.0)
    sim.corpses.append(corpse)
    c0 = sim.world.total_dic()
    n0 = sim.world.total_fixed_nitrogen()
    p0 = sim.world.total_phosphate()
    decay_m = corpse.matter * cfg.corpse_decay
    sim._decay_corpses()
    c_expected, n_expected, p_expected = stoichiometry.matter_to_element_mol(decay_m, cfg)
    assert (sim.world.total_dic() - c0) == pytest.approx(c_expected, rel=1e-6)
    assert (sim.world.total_fixed_nitrogen() - n0) == pytest.approx(n_expected, rel=1e-6)
    assert (sim.world.total_phosphate() - p0) == pytest.approx(p_expected, rel=1e-6)


def test_corpse_full_disposal_returns_remaining_cnp():
    cfg = _cnp_cfg(initial_population=0, cnp_background_exchange_enabled=False,
                   corpse_min_matter=10.0)  # 初期matterが常にmin未満 -> 即時全量放出
    sim = Simulation(cfg, seed=10)
    from evosim.corpse import Corpse
    corpse = Corpse(0.001, 0.001, matter=1.0, energy=0.0)
    sim.corpses.append(corpse)
    c0 = sim.world.total_dic()
    sim._decay_corpses()
    assert sim.corpses == []
    c_expected, _, _ = stoichiometry.matter_to_element_mol(1.0, cfg)
    assert (sim.world.total_dic() - c0) == pytest.approx(c_expected, rel=1e-6)


# ---------------------------------------------------------------------------
# Element ledger closure (Step6) — P0-A/P0-B相当のmechanical closure
# ---------------------------------------------------------------------------

def test_element_ledgers_close_open_background_exchange():
    """open (exchange ON) でも in/out ledgerを引けばresidualはほぼ0。"""
    cfg = _cnp_cfg(initial_population=20)
    sim = Simulation(cfg, seed=11)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    c0, n0, p0 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    for _ in range(500):
        sim.step()
    c1, n1, p1 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    c_resid = c1 - (c0 + sim.c_in_external_cum - sim.c_out_external_cum)
    n_resid = n1 - (n0 + sim.n_in_external_cum - sim.n_out_external_cum)
    p_resid = p1 - (p0 + sim.p_in_external_cum - sim.p_out_external_cum)
    assert abs(c_resid) <= 1e-9 * max(c1, 1e-30)
    assert abs(n_resid) <= 1e-9 * max(n1, 1e-30)
    assert abs(p_resid) <= 1e-9 * max(p1, 1e-30)


def test_element_ledgers_strict_conservation_closed_system():
    """closed (exchange OFF, no organisms入れ替え無し) では厳密保存。"""
    cfg = _cnp_cfg(initial_population=20, cnp_background_exchange_enabled=False)
    sim = Simulation(cfg, seed=12)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    c0, n0, p0 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    for _ in range(300):
        sim.step()
    assert sim.system_carbon() == pytest.approx(c0, rel=1e-9)
    assert sim.system_nitrogen() == pytest.approx(n0, rel=1e-9)
    assert sim.system_phosphorus() == pytest.approx(p0, rel=1e-9)
    assert sim.c_in_external_cum == 0.0 and sim.c_out_external_cum == 0.0


# ---------------------------------------------------------------------------
# Backward compatibility / determinism
# ---------------------------------------------------------------------------

def test_same_seed_determinism_cnp_mode():
    cfg = _cnp_cfg(initial_population=20)

    def run():
        sim = Simulation(cfg, seed=42)
        for o in sim.organisms:
            o.energy = physiology.energy_max(o, cfg)
        for _ in range(200):
            sim.step()
        return sim

    sim_a = run()
    sim_b = run()
    assert sim_a.system_carbon() == sim_b.system_carbon()
    assert sim_a.system_nitrogen() == sim_b.system_nitrogen()
    assert sim_a.system_phosphorus() == sim_b.system_phosphorus()
    assert [o.matter for o in sim_a.organisms] == [o.matter for o in sim_b.organisms]
    assert sim_a.growth_limiter_cum == sim_b.growth_limiter_cum


def test_recorder_stats_row_length_matches_header_with_cnp(tmp_path):
    cfg = _cnp_cfg(initial_population=10, stats_interval=5, snapshot_interval=1000)
    sim = Simulation(cfg, seed=13, run_dir=tmp_path / "run")
    for _ in range(10):
        sim.step()
    sim.close()
    import csv
    with open(tmp_path / "run" / "stats.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, data_rows = rows[0], rows[1:]
    assert data_rows, "stats.csvにデータ行が無い"
    for row in data_rows:
        assert len(row) == len(header)
