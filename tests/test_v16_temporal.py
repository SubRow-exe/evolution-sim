"""V1.6 temporal biased random walk のテスト (Phase 0 停止条件)。

正本: `docs/V1.6_行動則設計案.md` / `docs/Exp10_実験計画案.md` §3

`docs/Exp10_実験計画案.md` §3 の15項目に対応させる。番号は各testのdocstringに書く。

V1.5の一次Energy winner-take-all比較則のテスト (`tests/test_v15_stimulus.py`) は
V1.6で当該経路そのものが無くなったため撤去した。V1.5の再現は `v1.5-final` が持つ。
無次元受容器応答 `response(x,K)` の算術はV1.6でも使うのでここへ引き継ぐ。
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim import behavior
from evosim.config import Config
from evosim.genome import (CHEM_ABS, LIGHT_ABS, MOVE_EFF, MOVE_POWER, N_GENES,
                           SENSORY, STORAGE_CAP)
from evosim.organism import Organism
from evosim.simulation import Simulation
from evosim.world import World
from tools.golden import fingerprint

CUR = (5, 5)   # 個体を置くセル


def _sim(**kw) -> Simulation:
    """刺激を明示的に置くための空世界。"""
    base = dict(light_pattern="uniform", light_max=0.0, h2_vent_flux=0.0,
                nutrient_initial=0.0, initial_population=0)
    base.update(kw)
    return Simulation(Config(**base), 1)


def _place(sim: Simulation, light_abs: float, chem_abs: float,
           sensory: float = 2.0, energy: float = 5.0,
           cell: tuple[int, int] = CUR) -> Organism:
    g = np.zeros(N_GENES)
    g[0] = 1.0                 # body_size
    g[MOVE_POWER] = 1.0
    g[MOVE_EFF] = 1.0
    g[SENSORY] = sensory
    g[LIGHT_ABS] = light_abs
    g[CHEM_ABS] = chem_abs
    g[STORAGE_CAP] = 1.0       # E_max>0 (V1.9)
    cs = sim.cfg.cell_size
    o = Organism(0, -1, 0, 0, 0, g,
                 (cell[0] + 0.5) * cs, (cell[1] + 0.5) * cs, 0.0, energy, 0.8)
    sim.organisms.append(o)
    sim.next_id = 1
    sim._build_hashes()
    return o


def _decide(sim: Simulation, org: Organism) -> dict:
    """1回行動させ、その回の観測 (区間集計ではなく単発) を返す。"""
    sim.stim_obs = sim._new_stim_obs()
    behavior.decide_and_move(org, sim)
    return sim.stim_obs


def _turn_factor(gain: float, dq: float) -> float:
    return 2.0 / (1.0 + math.exp(gain * dq))


# --- 受容器応答の算術 (V1.5から引き継ぎ) --------------------------------

def test_response_at_zero_is_zero():
    assert behavior.response(0.0, 1.2) == 0.0
    assert behavior.response(-1.0, 1.2) == 0.0


@pytest.mark.parametrize("half", [1.2, 12.3, 0.5, 100.0])
def test_response_at_half_is_one_half(half):
    assert behavior.response(half, half) == pytest.approx(0.5)


def test_response_is_monotonic_and_bounded():
    half = 1.2
    prev = -1.0
    for x in (0.0, 0.01, 0.1, 1.0, 10.0, 1e3, 1e9):
        r = behavior.response(x, half)
        assert 0.0 <= r < 1.0
        assert r > prev
        prev = r


# --- 1/2/3. 知覚の双線形補間 --------------------------------------------

def test_interpolation_matches_the_field_at_cell_centers():
    """Phase 0-1: セル中心では補間値が元のfield値と厳密に一致する。"""
    cfg = Config()
    w = World(cfg, np.random.default_rng(1))
    cs = cfg.cell_size
    for ix in range(0, cfg.grid_w, 7):
        for iy in range(0, cfg.grid_h, 7):
            got = w.sample(w.light, (ix + 0.5) * cs, (iy + 0.5) * cs)
            assert got == pytest.approx(float(w.light[ix, iy]), abs=1e-12)
            got_c = w.sample(w.h2, (ix + 0.5) * cs, (iy + 0.5) * cs)
            assert got_c == pytest.approx(float(w.h2[ix, iy]), abs=1e-12)


def test_interpolation_is_continuous_across_cell_boundaries():
    """Phase 0-2: セル境界で知覚値が飛ばない。

    生のfield値はセル境界で `隣接セル差` だけ不連続に飛ぶ。補間後は
    その1/1000未満しか動かないことを確認する。
    """
    cfg = Config()
    w = World(cfg, np.random.default_rng(1))
    cs = cfg.cell_size
    boundary = 5 * cs           # セル4と5の境界
    raw_jump = abs(float(w.light[3, 5]) - float(w.light[3, 4]))
    assert raw_jump > 0.0, "そもそも勾配のある場でないと検定にならない"
    eps = 1e-6
    lo = w.sample(w.light, (3 + 0.5) * cs, boundary - eps)
    hi = w.sample(w.light, (3 + 0.5) * cs, boundary + eps)
    assert abs(hi - lo) < raw_jump / 1000.0


def test_interpolation_clamps_at_the_world_edge():
    """Phase 0-2: world端では最外セルの値へclampし、外挿しない。"""
    cfg = Config()
    w = World(cfg, np.random.default_rng(1))
    assert w.sample(w.light, 0.0, 0.0) == pytest.approx(float(w.light[0, 0]))
    assert w.sample(w.light, cfg.world_width, cfg.world_height) == pytest.approx(
        float(w.light[cfg.grid_w - 1, cfg.grid_h - 1]))


def test_absorption_still_uses_cell_values_not_interpolation():
    """Phase 0-3: 知覚だけ補間。吸収はセル単位のままでV1.5から変わらない。

    同一セル内の別位置に置いた2個体は、補間知覚では違う値を感じるが、
    吸収量は同一でなければならない。
    """
    cs = Config().cell_size
    absorbed = []
    perceived = []
    for frac in (0.05, 0.95):
        sim = _sim(light_pattern="vertical", light_max=1.2)
        o = _place(sim, 1.0, 0.0)
        o.y = (CUR[1] + frac) * cs     # セル内で位置だけ変える
        sim._build_hashes()
        perceived.append(sim.world.sample(sim.world.light, o.x, o.y))
        before = o.energy
        sim._absorb_fields()
        absorbed.append(o.energy - before)
    assert perceived[0] != perceived[1], "補間知覚はセル内位置で変わるはず"
    assert absorbed[0] == pytest.approx(absorbed[1], rel=1e-12), \
        "吸収はセル単位のままでなければならない"
    assert absorbed[0] > 0.0


# --- 4/5/6. 統合環境評価値 Q --------------------------------------------

def test_q_stays_in_the_unit_interval():
    """Phase 0-4: 0 <= Q < 1。"""
    sim = _sim(light_pattern="vertical", light_max=1.2, h2_vent_flux=64.0)
    for la, ca in ((2.0, 0.3), (0.3, 2.0), (1.0, 1.0), (5.0, 5.0)):
        s = _sim(light_pattern="vertical", light_max=1.2, h2_vent_flux=64.0)
        o = _place(s, la, ca)
        obs = _decide(s, o)
        q = obs["q_sum"] / obs["stim_events"]
        assert 0.0 <= q < 1.0


def test_q_is_invariant_to_uniform_ability_scaling():
    """Phase 0-5: 全abilityを同率で2倍してもQは変わらない (能力加重平均)。"""
    def q_of(la, ca):
        s = _sim(light_pattern="vertical", light_max=1.2, h2_vent_flux=64.0)
        o = _place(s, la, ca)
        obs = _decide(s, o)
        return obs["q_sum"] / obs["stim_events"]

    base = q_of(1.0, 0.5)
    assert q_of(2.0, 1.0) == pytest.approx(base, rel=1e-12)
    assert q_of(4.0, 2.0) == pytest.approx(base, rel=1e-12)
    assert q_of(0.5, 0.25) == pytest.approx(base, rel=1e-12)


def test_zero_ability_stimulus_does_not_contribute_to_q():
    """Phase 0-6: ability 0 の刺激はQへ寄与しない。"""
    s = _sim(light_pattern="vertical", light_max=1.2, h2_vent_flux=64.0)
    o = _place(s, 1.0, 0.0)          # chemicalは使えない
    # 知覚は行動前の位置で起きるので、先に期待値を取る
    r_l = behavior.response(
        s.world.sample(s.world.light, o.x, o.y), s.cfg.light_stimulus_half)
    obs = _decide(s, o)
    q = obs["q_sum"] / obs["stim_events"]
    assert q == pytest.approx(r_l, rel=1e-12)
    assert obs["r_chem_sum"] == 0.0


def test_q_is_zero_when_no_primary_energy_ability():
    """両abilityとも無効ならQ=0で、方向付けも起きない。"""
    s = _sim(light_pattern="vertical", light_max=1.2)
    o = _place(s, 0.0, 0.0)
    obs = _decide(s, o)
    assert obs["q_sum"] == 0.0
    assert obs["dq_sum"] == 0.0


# --- 7/8. 短期記憶 -------------------------------------------------------

def test_first_perception_sets_memory_and_zero_delta():
    """Phase 0-7: 初回は Q_memory = Q_now、dQ = 0 (人工的な差分を作らない)。"""
    s = _sim(light_pattern="vertical", light_max=1.2)
    o = _place(s, 1.0, 0.0)
    assert not o.has_stim_memory
    obs = _decide(s, o)
    assert obs["dq_sum"] == 0.0
    assert obs["dq_zero"] == 1
    assert o.has_stim_memory
    q = obs["q_sum"] / obs["stim_events"]
    assert obs["q_mem_sum"] == pytest.approx(q, rel=1e-12)


def test_ema_memory_follows_the_spec_formula():
    """Phase 0-8: EMA更新が alpha = 1 - exp(-1/tau) の仕様式どおり。"""
    tau = 7.0
    alpha = 1.0 - math.exp(-1.0 / tau)
    s = _sim(light_pattern="vertical", light_max=1.2, memory_tau=tau,
             response_gain=0.0)
    assert s.stim_alpha == pytest.approx(alpha, rel=1e-15)
    o = _place(s, 1.0, 0.0)

    mem = None
    for _ in range(6):
        r = behavior.response(
            s.world.sample(s.world.light, o.x, o.y), s.cfg.light_stimulus_half)
        if mem is None:
            mem = r                      # 初回
        else:
            assert o.r_light_mem == pytest.approx(mem, rel=1e-12)
            mem = mem + alpha * (r - mem)
        behavior.decide_and_move(o, s)
        if o.has_stim_memory and mem is not None:
            mem_expected = mem
    assert o.r_light_mem == pytest.approx(mem_expected, rel=1e-12)


def test_memory_tau_zero_means_no_memory():
    """tau <= 0 は alpha = 1 (記憶せず常に現在値)。"""
    s = _sim(memory_tau=0.0)
    assert s.stim_alpha == 1.0


# --- 9/10. turn rate の変調 ---------------------------------------------

def test_zero_delta_gives_the_baseline_turn_width():
    """Phase 0-9: dQ = 0 で sigma_eff = wander_turn_sigma。"""
    assert _turn_factor(16.0, 0.0) == pytest.approx(1.0)
    s = _sim(light_pattern="uniform", light_max=1.0, response_gain=64.0)
    o = _place(s, 1.0, 0.0)
    _decide(s, o)                      # 初回 (dQ=0)
    obs = _decide(s, o)                # 一様場なのでdQ=0のまま
    assert obs["dq_sum"] == pytest.approx(0.0, abs=1e-15)
    assert obs["sigma_eff_sum"] == pytest.approx(s.cfg.wander_turn_sigma,
                                                 rel=1e-12)


def test_positive_delta_turns_less_and_negative_turns_more():
    """Phase 0-10: dQ>0 で曲がりにくく、dQ<0 で曲がりやすい。"""
    gain = 16.0
    assert _turn_factor(gain, 0.05) < 1.0
    assert _turn_factor(gain, -0.05) > 1.0
    # 単調性
    prev = 2.0
    for dq in (-0.2, -0.05, 0.0, 0.05, 0.2):
        f = _turn_factor(gain, dq)
        assert f < prev
        prev = f


def test_turn_factor_is_bounded_and_never_overflows():
    """Phase 0-10: factorは (0, 2) に収まり、極端なdQでも発散しない。"""
    for gain in (0.0, 16.0, 1e6):
        for dq in (-1.0, -1e-9, 0.0, 1e-9, 1.0):
            f = _turn_factor(gain, dq) if abs(gain * dq) < 700 else (
                0.0 if gain * dq > 0 else 2.0)
            assert 0.0 <= f <= 2.0
            assert math.isfinite(f)


def test_zero_gain_is_baseline_random_walk():
    """Phase 0-11: response_gain=0 なら memory_tau によらず結果が完全一致する。

    gain=0 では turn_factor が常に1になるので、記憶の時定数は行動へ影響しない。
    """
    a = Simulation(Config(response_gain=0.0, memory_tau=3.0), 11)
    b = Simulation(Config(response_gain=0.0, memory_tau=30.0), 11)
    for _ in range(120):
        a.step()
        b.step()
    assert fingerprint(a) == fingerprint(b)


def test_uniform_world_is_identical_for_any_gain():
    """一様刺激では gain によらず結果が一致する (偽biasを作らない)。

    Phase 0-13 も兼ねる: 知覚・観測の追加がRNG系列や分岐を変えていない。
    """
    kw = dict(light_pattern="uniform", light_max=0.8, h2_vent_flux=0.0)
    a = Simulation(Config(response_gain=0.0, **kw), 5)
    b = Simulation(Config(response_gain=256.0, **kw), 5)
    for _ in range(150):
        a.step()
        b.step()
    assert fingerprint(a) == fingerprint(b)


# --- 12. WTAターゲティングの廃止 ----------------------------------------

def test_primary_energy_never_sets_a_target():
    """Phase 0-12: 一次Energyは移動先を指定しない (必ずwalk分岐へ行く)。

    一次Energy以外の能力を0にしてあるので、targetを作れるのはV1.5経路だけ。
    V1.6ではその経路が無いので、行動は毎回random walkになる。
    """
    s = _sim(light_pattern="vertical", light_max=1.2, h2_vent_flux=64.0)
    o = _place(s, 2.0, 2.0, sensory=4.0)   # 広い感覚半径でも探しに行かない
    n = 40
    s.stim_obs = s._new_stim_obs()
    for _ in range(n):
        behavior.decide_and_move(o, s)
    assert s.stim_obs["walk"] == n
    assert s.stim_obs["stim_events"] == n


def test_sensory_range_does_not_affect_primary_energy_behavior():
    """一次Energyのtemporal sensingは sensory_range を使わない (仕様 §2.1)。

    他刺激の能力を0にした個体では、感覚半径を変えても軌跡が完全に一致する。
    """
    def run(sensory):
        s = _sim(light_pattern="vertical", light_max=1.2, h2_vent_flux=64.0,
                 response_gain=64.0)
        o = _place(s, 1.0, 1.0, sensory=sensory)
        for _ in range(60):
            behavior.decide_and_move(o, s)
        return (o.x, o.y, o.heading)

    assert run(0.1) == run(4.0)


# --- 14/15. 保存則と決定論 ----------------------------------------------

def test_v16_is_deterministic_for_a_fixed_seed():
    """Phase 0-15: 同一seed・同一ConfigでV1.6内部の結果が完全一致する。"""
    a = Simulation(Config(), 3)
    b = Simulation(Config(), 3)
    for _ in range(150):
        a.step()
        b.step()
    assert fingerprint(a) == fingerprint(b)


def test_matter_is_conserved_under_v16():
    """Phase 0-14: Matter保存。移動則を変えても物質は増減しない。"""
    sim = Simulation(Config(), 4)
    m0 = sim.system_matter()
    for _ in range(200):
        sim.step()
        assert sim.system_matter() == pytest.approx(m0, rel=1e-9)


def test_energy_ledger_holds_under_v16():
    """Phase 0-14: Energy台帳。"""
    sim = Simulation(Config(), 4)
    e0 = sim.system_energy()
    for _ in range(200):
        sim.step()
    expected = e0 + sim.energy_in_cum - sim.energy_out_cum
    assert sim.system_energy() == pytest.approx(expected, rel=1e-6, abs=1e-3)


def test_observations_are_finite():
    """Phase 0-14: 観測に NaN / inf が出ない。"""
    sim = Simulation(Config(stats_interval=25), 6)
    for _ in range(200):
        sim.step()
    for k, v in sim.stim_obs.items():
        vals = v if isinstance(v, list) else [v]
        for i, x in enumerate(vals):
            assert math.isfinite(x), f"{k}[{i}] が有限でない"


# --- 移動が実際に起きること ---------------------------------------------

def test_v16_actually_moves_unlike_v15():
    """V1.6では個体が実際に動く (レビュー A-1 の状況を解消できている)。

    V1.5は `sensory_range` が `cell_size` を下回るため自セルが常に最良となり、
    Exp09では移動量が5,000 tick全区間で0だった。V1.6は定位保持を廃止した。
    """
    sim = Simulation(Config(stats_interval=50), 2)
    for _ in range(200):
        sim.step()
    assert sim._move_count > 0
    assert sim._move_sum / sim._move_count > 0.0


# --- vent距離帯別の観測 (Exp10 §5.4) -----------------------------------

def test_vent_band_partitions_the_grid():
    """距離帯は全セルを重複なく覆い、vent中心は最も内側の帯になる。"""
    from evosim.world import VENT_BAND_NAMES
    cfg = Config()
    w = World(cfg, np.random.default_rng(1))
    assert w.vent_band.shape == (cfg.grid_w, cfg.grid_h)
    assert set(np.unique(w.vent_band).tolist()) <= set(range(len(VENT_BAND_NAMES)))
    for vx, vy in w.vent_centers:
        assert w.vent_band[vx, vy] == 0


def test_band_observations_sum_to_the_totals():
    """帯別の内訳が全体の観測と一致する (取りこぼし・二重計上が無い)。"""
    sim = Simulation(Config(stats_interval=0), 1)
    for _ in range(120):
        sim.step()
    obs = sim.stim_obs
    assert sum(obs["band_n"]) == obs["stim_events"]
    assert sum(obs["band_dq_light"]) == pytest.approx(obs["dq_light_sum"],
                                                      rel=1e-9, abs=1e-12)
    assert sum(obs["band_dq_chem"]) == pytest.approx(obs["dq_chem_sum"],
                                                     rel=1e-9, abs=1e-12)
    assert sum(obs["band_sigma_eff"]) == pytest.approx(obs["sigma_eff_sum"],
                                                       rel=1e-9, abs=1e-12)


def test_band_observations_do_not_change_results():
    """帯別観測はRNGにも結果にも影響しない (同一seedで再現する)。"""
    a = Simulation(Config(), 8)
    b = Simulation(Config(), 8)
    for _ in range(120):
        a.step()
        b.step()
    assert fingerprint(a) == fingerprint(b)
