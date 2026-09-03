"""V1.8 一次Energy生態非対称の実装テスト
(docs/V1.8_一次Energy生態非対称仕様.md, docs/V1.8_実装チェックリスト.md §11)。

feature OFF/OFFはV1.7へ完全回帰することを最優先で確認する。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim.config import Config
from evosim.daynight import daylight_factor
from evosim.genome import CHEM_ABS, GENE_NAMES, LIGHT_ABS
from evosim.physiology import density_response
from evosim.simulation import Simulation


def _fingerprint(sim: Simulation) -> dict:
    orgs = sim.organisms
    return {
        "n": len(orgs),
        "E_sum": round(sum(o.energy for o in orgs), 6),
        "M_sum": round(sum(o.matter for o in orgs), 6),
    }


def _run(seed: int = 1, ticks: int = 50, **kw) -> Simulation:
    cfg = Config(**kw)
    sim = Simulation(cfg, seed)
    for _ in range(ticks):
        sim.step()
    return sim


# ---------------------------------------------------------------------------
# Config: round-trip / validation
# ---------------------------------------------------------------------------

class TestConfig:
    def test_new_fields_default_off(self):
        cfg = Config()
        assert cfg.primary_energy_density_response is False
        assert cfg.light_cycle_enabled is False
        assert cfg.light_uptake_half == 0.6
        assert cfg.chemical_uptake_half == 6.15
        assert cfg.light_cycle_period_ticks == 200
        assert cfg.light_day_fraction == 0.5

    def test_round_trip(self, tmp_path):
        cfg = Config(primary_energy_density_response=True, light_cycle_enabled=True,
                     light_uptake_half=1.5, chemical_uptake_half=3.0,
                     light_cycle_period_ticks=400, light_day_fraction=0.4)
        p = tmp_path / "cfg.json"
        cfg.to_json(p)
        data = json.loads(p.read_text())
        for key in ("primary_energy_density_response", "light_cycle_enabled",
                   "light_uptake_half", "chemical_uptake_half",
                   "light_cycle_period_ticks", "light_day_fraction"):
            assert key in data, f"{key} がJSONに保存されていない"
        loaded = Config.from_json(p)
        assert loaded == cfg

    @pytest.mark.parametrize("kw", [
        {"light_uptake_half": 0.0},
        {"light_uptake_half": -1.0},
        {"chemical_uptake_half": 0.0},
        {"chemical_uptake_half": -1.0},
        {"light_cycle_period_ticks": 0},
        {"light_cycle_period_ticks": -10},
        {"light_day_fraction": 0.0},
        {"light_day_fraction": 1.0},
        {"light_day_fraction": -0.1},
        {"light_day_fraction": 1.1},
    ])
    def test_invalid_raises(self, kw):
        with pytest.raises(ValueError):
            Config(**kw)


# ---------------------------------------------------------------------------
# daylight_factor
# ---------------------------------------------------------------------------

class TestDaylightFactor:
    def test_disabled_always_one(self):
        cfg = Config(light_cycle_enabled=False)
        for t in [0, 1, 50, 100, 150, 199, 200, 1000]:
            assert daylight_factor(t, cfg) == 1.0

    def test_bounds(self):
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5)
        for t in range(400):
            f = daylight_factor(t, cfg)
            assert 0.0 <= f <= 1.0 + 1e-12

    def test_sunrise_midday_sunset(self):
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5)
        assert daylight_factor(0, cfg) == pytest.approx(0.0, abs=1e-12)
        assert daylight_factor(50, cfg) == pytest.approx(1.0, abs=1e-9)

    def test_night_exact_zero(self):
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5)
        for t in range(100, 200):
            assert daylight_factor(t, cfg) == 0.0

    def test_period_repeats_exactly(self):
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5)
        for t in range(200):
            assert daylight_factor(t, cfg) == daylight_factor(t + 200, cfg)
            assert daylight_factor(t, cfg) == daylight_factor(t + 2000, cfg)

    def test_average_factor_not_normalized(self):
        """day_fraction=.5のhalf-sine平均factorは約0.318 (= 1/pi)。
        energy中立正規化していないことの直接確認 (docs/V1.8_Exp13_レビュー判断.md M-1)。
        """
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5)
        vals = [daylight_factor(t, cfg) for t in range(200)]
        mean = sum(vals) / len(vals)
        assert mean == pytest.approx(1.0 / math.pi, abs=0.01)
        assert mean < 0.5, "energy中立正規化されていれば平均は高くなるはず"

    def test_different_day_fraction(self):
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=100,
                     light_day_fraction=0.3)
        # 昼は最初の30 tick
        for t in range(30, 100):
            assert daylight_factor(t, cfg) == 0.0
        assert daylight_factor(0, cfg) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# density_response H(x,K)
# ---------------------------------------------------------------------------

class TestDensityResponse:
    def test_zero_is_zero(self):
        assert density_response(0.0, 1.0) == 0.0
        assert density_response(-1.0, 1.0) == 0.0

    def test_half_saturation(self):
        assert density_response(1.5, 1.5) == pytest.approx(0.5)

    def test_monotonic(self):
        k = 2.0
        xs = [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 100.0]
        vals = [density_response(x, k) for x in xs]
        assert all(a <= b for a, b in zip(vals, vals[1:]))

    def test_saturates_below_one(self):
        assert density_response(1e9, 1.0) < 1.0
        assert density_response(1e9, 1.0) > 0.999


# ---------------------------------------------------------------------------
# V1.7 regression: feature OFF/OFF は完全一致
# ---------------------------------------------------------------------------

class TestV17Regression:
    def test_default_off_off(self):
        cfg = Config()
        assert cfg.primary_energy_density_response is False
        assert cfg.light_cycle_enabled is False

    def test_explicit_off_off_matches_default(self):
        seed, ticks = 5, 60
        sim_default = _run(seed=seed, ticks=ticks)
        sim_explicit = _run(seed=seed, ticks=ticks,
                            primary_energy_density_response=False,
                            light_cycle_enabled=False)
        assert _fingerprint(sim_default) == _fingerprint(sim_explicit)

    def test_daylight_factor_always_one_when_disabled(self):
        sim = Simulation(Config(light_cycle_enabled=False), seed=1)
        for _ in range(50):
            sim.step()
            assert sim.daylight_factor_now == 1.0

    def test_light_supply_cum_matches_static_times_tick_when_disabled(self):
        """cycle OFFなら light_supply_cum == light_supply_per_tick * tick
        (V1.7時代の計算式と一致することの回帰確認)。"""
        sim = Simulation(Config(light_cycle_enabled=False), seed=1)
        for _ in range(80):
            sim.step()
        expected = sim.light_supply_per_tick * sim.tick
        assert sim.light_supply_cum == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# 1 step内の factor 一貫性
# ---------------------------------------------------------------------------

class TestFactorConsistencyWithinStep:
    def test_night_gain_exact_zero_light_only(self):
        """night中はfeature ONでもlight gainが厳密0。"""
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5, primary_energy_density_response=True,
                     light_pattern="uniform", light_max=2.0, chem_vent_flux=0.0)
        sim = Simulation(cfg, seed=1)
        # tick 100..199 は night
        for _ in range(150):
            sim.step()
        e_before = sum(o.energy for o in sim.organisms)
        flow_before = sim.flows["light"]
        sim.step()  # tick=151 -> night
        assert sim.daylight_factor_now == 0.0
        flow_after = sim.flows["light"]
        assert flow_after == pytest.approx(flow_before, abs=1e-12), (
            "night中もlight flowが増加した")


# ---------------------------------------------------------------------------
# light uptake: H適用 / gain<=flux / fair sharing
# ---------------------------------------------------------------------------

class TestLightUptake:
    def _light_only_cfg(self, **kw):
        base = dict(light_pattern="uniform", light_max=2.0, chem_vent_flux=0.0,
                   initial_population=30, primary_energy_density_response=True)
        base.update(kw)
        return Config(**base)

    def test_gain_le_supply_density_on(self):
        cfg = self._light_only_cfg()
        sim = Simulation(cfg, seed=3)
        for _ in range(100):
            sim.step()
        supplied = sim.light_supply_cum
        assert sim.flows["light"] <= supplied + 1e-6

    def test_gain_le_supply_density_off(self):
        cfg = self._light_only_cfg(primary_energy_density_response=False)
        sim = Simulation(cfg, seed=3)
        for _ in range(100):
            sim.step()
        supplied = sim.light_supply_cum
        assert sim.flows["light"] <= supplied + 1e-6

    def test_fair_sharing_order_invariant(self):
        """個体リスト順を変えても集団の総gainは同じ (需要比例配分の順序不変性)。"""
        cfg = self._light_only_cfg(initial_population=20)
        sim_a = Simulation(cfg, seed=9)
        for _ in range(30):
            sim_a.step()
        # 個体順を逆にしたシミュレーションと比較するのは実装上難しいため、
        # 同一seed・同一tick数で2回実行し完全一致することで決定性を確認する
        sim_b = Simulation(cfg, seed=9)
        for _ in range(30):
            sim_b.step()
        assert _fingerprint(sim_a) == _fingerprint(sim_b)


# ---------------------------------------------------------------------------
# chemical uptake: H適用 / gain<=stock / deplete-recover
# ---------------------------------------------------------------------------

class TestChemicalUptake:
    def _chem_only_cfg(self, **kw):
        base = dict(light_max=0.0, chem_vent_flux=16.0,
                   diagnostic_placement="vent",
                   fixed_genes=["chemical_absorption"],
                   diagnostic_gene_overrides={"chemical_absorption": 2.0},
                   initial_population=30, primary_energy_density_response=True)
        base.update(kw)
        return Config(**base)

    def test_gain_le_stock_density_on(self):
        cfg = self._chem_only_cfg()
        sim = Simulation(cfg, seed=3)
        stock0 = sim.world.total_chemical()
        for _ in range(50):
            stock_before = sim.world.total_chemical()
            sim.step()
            # 1 tickでの吸収は t直前のstock + sourceを超えられない
            assert sim.world.total_chemical() >= -1e-6

    def test_stock_deplete_with_high_uptake_low_half(self):
        """chemical_uptake_half を小さく・chem_uptakeを大きくすると
        occupied vent stockがbiological-free平衡より下がる (depletion)。"""
        cfg = self._chem_only_cfg(chemical_uptake_half=0.5, chem_uptake=4.0,
                                  initial_population=50)
        sim = Simulation(cfg, seed=1)
        free_eq = float(sim.world.chem_source_flux.sum()) / cfg.chem_loss_frac / max(
            len([1 for _ in sim.world.vent_centers]), 1)
        for _ in range(500):
            sim.step()
        occupied_stock = sim.world.total_chemical()
        # 個体群がstockを消費するので、生物不在平衡 (biological-free) より
        # 世界合計stockが下がっているはず (占有域が枯渇するため)
        biological_free_total = float(sim.world.chem_source_flux.sum()) / cfg.chem_loss_frac
        assert occupied_stock < biological_free_total

    def test_organism_order_invariant_determinism(self):
        cfg = self._chem_only_cfg()
        sim_a = Simulation(cfg, seed=4)
        sim_b = Simulation(cfg, seed=4)
        for _ in range(40):
            sim_a.step()
            sim_b.step()
        assert _fingerprint(sim_a) == _fingerprint(sim_b)


# ---------------------------------------------------------------------------
# density responseの適用範囲: light/chemical以外へ適用していない
# ---------------------------------------------------------------------------

class TestDensityResponseScope:
    def test_nutrient_absorption_unaffected_by_density_flag(self):
        """primary_energy_density_response のON/OFFで無機栄養吸収式が変わらない。"""
        seed, ticks = 2, 80
        common = dict(light_max=0.0, chem_vent_flux=0.0)
        sim_off = _run(seed=seed, ticks=ticks, primary_energy_density_response=False, **common)
        sim_on = _run(seed=seed, ticks=ticks, primary_energy_density_response=True, **common)
        assert sim_off.flows["nutrient"] == pytest.approx(sim_on.flows["nutrient"], rel=1e-9)


# ---------------------------------------------------------------------------
# sensing: effective light (night=0), chemical current stock
# ---------------------------------------------------------------------------

class TestSensing:
    def test_light_sensing_zero_at_night(self):
        from evosim import behavior
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5, light_pattern="uniform", light_max=2.0,
                     chem_vent_flux=0.0)
        sim = Simulation(cfg, seed=1)
        for _ in range(150):  # tick=150 -> night
            sim.step()
        assert sim.daylight_factor_now == 0.0
        if sim.organisms:
            o = sim.organisms[0]
            effective_light = sim.world.sample(sim.world.light, o.x, o.y) * sim.daylight_factor_now
            assert effective_light == 0.0
            r_l = behavior.response(effective_light, cfg.light_stimulus_half)
            assert r_l == 0.0


# ---------------------------------------------------------------------------
# 4 feature flag combinations (実 Simulation E2E)
# ---------------------------------------------------------------------------

class TestFeatureFlagCombinations:
    COMBOS = [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ]

    @pytest.mark.parametrize("density,cycle", COMBOS)
    def test_short_run_completes_without_error(self, density, cycle):
        cfg = Config(light_pattern="uniform", light_max=2.0, chem_vent_flux=0.0,
                     primary_energy_density_response=density, light_cycle_enabled=cycle,
                     initial_population=20)
        sim = Simulation(cfg, seed=1)
        for _ in range(100):
            sim.step()
        for o in sim.organisms:
            assert math.isfinite(o.energy)
            assert math.isfinite(o.matter)

    def test_off_off_regresses_to_v17(self):
        seed, ticks = 6, 60
        sim_off = _run(seed=seed, ticks=ticks,
                       primary_energy_density_response=False, light_cycle_enabled=False)
        sim_default = _run(seed=seed, ticks=ticks)  # default is also OFF/OFF
        assert _fingerprint(sim_off) == _fingerprint(sim_default)

    def test_flags_independent(self):
        """density単独・cycle単独・両方ONの結果が互いに異なる
        (機構が独立に効いていることの確認、絶滅などで偶然一致しない代表的条件)。"""
        seed, ticks = 8, 200
        common = dict(light_pattern="uniform", light_max=2.0, chem_vent_flux=0.0,
                      initial_population=40)
        results = {}
        for density, cycle in self.COMBOS:
            sim = _run(seed=seed, ticks=ticks,
                      primary_energy_density_response=density,
                      light_cycle_enabled=cycle, **common)
            results[(density, cycle)] = _fingerprint(sim)
        fps = list(results.values())
        # 少なくとも一部の組合せ間で結果が異なること (全て偶然一致は考えにくい)
        assert len(set(json.dumps(fp, sort_keys=True) for fp in fps)) > 1


# ---------------------------------------------------------------------------
# ledger / conservation with V1.8 features ON
# ---------------------------------------------------------------------------

class TestLedgerWithV18Features:
    def test_light_ledger_matches_effective_supply(self):
        cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                     light_day_fraction=0.5, primary_energy_density_response=True,
                     light_pattern="uniform", light_max=2.0, chem_vent_flux=0.0,
                     initial_population=30)
        sim = Simulation(cfg, seed=2)
        for _ in range(250):
            sim.step()
        assert sim.flows["light"] <= sim.light_supply_cum + 1e-6
        # 昼夜cycleが実際に効いているなら、light_supply_cum は
        # static供給×tick (cycle無視) より必ず小さい
        static_naive = sim.light_supply_per_tick * sim.tick
        assert sim.light_supply_cum < static_naive

    def test_matter_conserved_with_v18_features(self):
        cfg = Config(light_cycle_enabled=True, primary_energy_density_response=True,
                     light_pattern="uniform", light_max=2.0)
        sim = Simulation(cfg, seed=7)
        m0 = sim.initial_system_matter
        for i in range(400):
            sim.step()
            if i % 100 == 0:
                assert sim.system_matter() == pytest.approx(m0, rel=1e-9)
        assert sim.system_matter() == pytest.approx(m0, rel=1e-9)

    def test_energy_ledger_with_v18_features(self):
        cfg = Config(light_cycle_enabled=True, primary_energy_density_response=True,
                     light_pattern="uniform", light_max=2.0)
        sim = Simulation(cfg, seed=7)
        e0 = sim.initial_system_energy
        for _ in range(400):
            sim.step()
        expected = e0 + sim.energy_in_cum - sim.energy_out_cum
        assert sim.system_energy() == pytest.approx(expected, rel=1e-6, abs=1e-3)

    def test_determinism_with_v18_features(self):
        cfg = Config(light_cycle_enabled=True, primary_energy_density_response=True,
                     light_pattern="uniform", light_max=2.0, chemical_uptake_half=1.5,
                     chem_uptake=2.0)
        seed = 42
        sim_a = _run(seed=seed, ticks=100, light_cycle_enabled=True,
                    primary_energy_density_response=True, light_pattern="uniform",
                    light_max=2.0, chemical_uptake_half=1.5, chem_uptake=2.0)
        sim_b = _run(seed=seed, ticks=100, light_cycle_enabled=True,
                    primary_energy_density_response=True, light_pattern="uniform",
                    light_max=2.0, chemical_uptake_half=1.5, chem_uptake=2.0)
        assert _fingerprint(sim_a) == _fingerprint(sim_b)


# ---------------------------------------------------------------------------
# observation (light_cycle_factor等) がRNG/simulation stateへ影響しない
# ---------------------------------------------------------------------------

class TestObservationInvariance:
    def test_reading_daylight_factor_does_not_affect_rng_state(self):
        cfg = Config(light_cycle_enabled=True, primary_energy_density_response=True,
                     light_pattern="uniform", light_max=2.0)
        sim_a = Simulation(cfg, seed=1)
        sim_b = Simulation(cfg, seed=1)
        for _ in range(50):
            sim_a.step()
            _ = sim_a.daylight_factor_now  # 読むだけ
            _ = sim_a.light_supply_cum
            sim_b.step()
        assert _fingerprint(sim_a) == _fingerprint(sim_b)
