"""V1.5 異種一次Energy刺激の比較則テスト。

正本: `docs/V1.5_異種刺激比較仕様.md` / `docs/Exp09_実験計画.md` §5

守るもの:
- 無次元受容器応答 `response(x,K) = x/(x+K)` の算術 (0 / half / 単調性 / 上限)
- light と chemical の比較が `ability × response` で決まる
- 交差点stockの両側で選択が反転する (各表現型で両方向を確認)
- exact tie で走査順によるsource固定biasがない / 両score=0はV1.4と同じ挙動
- 単独source世界では選択がV1.4と同じ (raw値の最良セル)
- 観測カウンタがRNGにも結果にも影響しない
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim import behavior
from evosim.config import Config
from evosim.genome import CHEM_ABS, LIGHT_ABS, MOVE_POWER, N_GENES, SENSORY
from evosim.organism import Organism
from evosim.simulation import Simulation
from tools.golden import fingerprint

CUR = (5, 5)          # 個体を置くセル
LIGHT_CELL = (5, 4)   # 光が最大のセル
CHEM_CELL = (5, 6)    # chemical stockが最大のセル


def _sim(**kw) -> Simulation:
    base = dict(light_pattern="uniform", light_max=0.0, chem_vent_flux=0.0,
                nutrient_initial=0.0, initial_population=0)
    base.update(kw)
    return Simulation(Config(**base), 1)


def _place(sim: Simulation, light_abs: float, chem_abs: float,
           energy: float = 5.0) -> Organism:
    g = np.zeros(N_GENES)
    g[0] = 1.0                 # body_size
    g[MOVE_POWER] = 1.0
    g[3] = 1.0                 # movement_efficiency
    g[SENSORY] = 2.0           # 隣接セルまで感知する
    g[LIGHT_ABS] = light_abs
    g[CHEM_ABS] = chem_abs
    cs = sim.cfg.cell_size
    o = Organism(0, -1, 0, 0, 0, g,
                 (CUR[0] + 0.5) * cs, (CUR[1] + 0.5) * cs, 0.0, energy, 0.8)
    sim.organisms.append(o)
    sim.next_id = 1
    sim._build_hashes()
    return o


def _choose(light_val: float, chem_val: float, light_abs: float,
            chem_abs: float, **cfg_kw) -> str:
    """1個体に1回だけ行動させ、選ばれた一次Energy源を返す。"""
    sim = _sim(**cfg_kw)
    sim.world.light[LIGHT_CELL] = light_val
    sim.world.chemical[CHEM_CELL] = chem_val
    _place(sim, light_abs, chem_abs)
    behavior.decide_and_move(sim.organisms[0], sim)
    obs = sim.stim_obs
    if obs["tie"]:
        return "tie"
    if obs["light"]:
        return "light"
    if obs["chemical"]:
        return "chemical"
    return "none"


def _crossover_stock(light_val: float, light_abs: float, chem_abs: float,
                     cfg: Config | None = None) -> float:
    """light scoreとchemical scoreが等しくなるchemical stock (交差点stock)。"""
    cfg = cfg or Config()
    t = (light_abs / chem_abs) * behavior.response(light_val,
                                                   cfg.light_stimulus_half)
    if t >= 1.0:
        return math.inf     # どんなstockでもchemicalは勝てない
    return cfg.chemical_stimulus_half * t / (1.0 - t)


# --- 受容器応答の算術 ---------------------------------------------------

def test_response_at_zero_is_zero():
    assert behavior.response(0.0, 1.2) == 0.0
    assert behavior.response(-1.0, 1.2) == 0.0


@pytest.mark.parametrize("half", [1.2, 12.3, 0.5])
def test_response_at_half_is_one_half(half):
    assert behavior.response(half, half) == pytest.approx(0.5, rel=1e-12)


def test_response_is_monotonic_and_bounded():
    half = 12.3
    xs = [0.0, 0.01, 0.5, 1.0, 12.3, 100.0, 1e6]
    vals = [behavior.response(x, half) for x in xs]
    assert all(b > a for a, b in zip(vals, vals[1:])), "単調増加でない"
    assert all(0.0 <= v < 1.0 for v in vals), "0<=response<1 を外れている"


def test_response_does_not_use_future_information():
    """responseは現在の刺激量とKだけの関数 (未来収益を含まない)。"""
    assert behavior.response(3.0, 12.3) == behavior.response(3.0, 12.3)
    assert behavior.response(3.0, 12.3) == pytest.approx(3.0 / 15.3, rel=1e-12)


# --- 等価刺激と能力差 ---------------------------------------------------

def test_equal_stimulus_and_ability_is_a_tie():
    """light=1.2 / chemical=12.3 / 両ability同値なら同一score → tie。"""
    assert _choose(1.2, 12.3, 1.0, 1.0) == "tie"


def test_ability_difference_decides_at_equal_stimulus():
    assert _choose(1.2, 12.3, 2.0, 0.3) == "light"
    assert _choose(1.2, 12.3, 0.3, 2.0) == "chemical"


# --- 交差点の両側 (各表現型で両方向) ------------------------------------

PHENOTYPES = [
    ("light_specialist", 2.0, 0.3),
    ("chemical_specialist", 0.3, 2.0),
    ("generalist", 1.0, 1.0),
]


@pytest.mark.parametrize("name,la,ca", PHENOTYPES)
def test_selection_flips_across_the_crossover(name, la, ca):
    """交差点の下側でlight、上側でchemicalへ反転する。

    light specialist は標準光では交差点が存在しない (どんなstockでもlight) ため、
    光を十分弱くして交差点を作り、そこでも両側を通す。
    """
    light_val = 1.2
    cross = _crossover_stock(light_val, la, ca)
    if math.isinf(cross):
        light_val = 0.05                      # 交差点が生じる弱い光にする
        cross = _crossover_stock(light_val, la, ca)
    assert math.isfinite(cross) and cross > 0.0

    assert _choose(light_val, cross * 0.5, la, ca) == "light", f"{name}: 下側"
    assert _choose(light_val, cross * 2.0, la, ca) == "chemical", f"{name}: 上側"


def test_light_specialist_cannot_pick_chemical_in_standard_light():
    """標準光ではlight専門型に交差点が無いことを式と実挙動の両方で確認。"""
    assert math.isinf(_crossover_stock(1.2, 2.0, 0.3))
    assert _choose(1.2, 1e6, 2.0, 0.3) == "light"


# --- tie の扱い ---------------------------------------------------------

def test_no_source_scan_order_bias():
    """勝敗はscoreだけで決まり、source種別 (走査順) では決まらない。

    同じ「わずかな差」を light 側 / chemical 側へ交互に与え、常にscoreが
    大きい方が選ばれることを見る。走査順で固定優先していれば片側が必ず勝つ。
    """
    cfg = Config()
    half_c = cfg.chemical_stimulus_half
    # light=1.2 → response 0.5。chemical stock を response 0.5±δ に置く
    lo = half_c * (0.5 - 1e-3) / (0.5 + 1e-3)      # response < 0.5
    hi = half_c * (0.5 + 1e-3) / (0.5 - 1e-3)      # response > 0.5
    assert _choose(1.2, lo, 1.0, 1.0) == "light"
    assert _choose(1.2, hi, 1.0, 1.0) == "chemical"


def test_tie_does_not_steer_when_neither_candidate_is_the_current_cell():
    sim = _sim()
    sim.world.light[LIGHT_CELL] = 1.2
    sim.world.chemical[CHEM_CELL] = 12.3
    o = _place(sim, 1.0, 1.0)
    x0, y0 = o.x, o.y
    behavior.decide_and_move(o, sim)
    assert sim.stim_obs["tie"] == 1
    # Energy源による方向付けはせず、ランダムウォークへ落ちる
    assert sim.stim_obs["walk"] == 1
    assert (o.x, o.y) != (x0, y0)


def test_both_zero_scores_behave_like_v14():
    """両score=0ではEnergy源による方向付けをしない (V1.4と同じ)。"""
    sim = _sim()          # light 0 / chemical 0
    o = _place(sim, 1.0, 1.0)
    behavior.decide_and_move(o, sim)
    obs = sim.stim_obs
    assert obs["light"] == 0 and obs["chemical"] == 0
    assert obs["walk"] == 1, "刺激が無いのでランダムウォークになるはず"


def test_tie_eps_default_is_small():
    """広いtie帯で弱刺激域が一律random walkにならないこと。"""
    assert 0.0 < Config().stimulus_tie_eps <= 1e-6


# --- 単独source ---------------------------------------------------------

def test_light_only_world_picks_the_raw_best_light_cell():
    sim = _sim()
    sim.world.light[LIGHT_CELL] = 1.0
    sim.world.light[(4, 5)] = 0.4
    o = _place(sim, 1.0, 1.0)
    behavior.decide_and_move(o, sim)
    assert sim.stim_obs["light"] == 1 and sim.stim_obs["chemical"] == 0
    cs = sim.cfg.cell_size
    assert sim.world.cell_index(o.x, o.y) in (CUR, LIGHT_CELL)
    assert o.y < (CUR[1] + 0.5) * cs, "光の最良セル (y-方向) へ向かっていない"


def test_chemical_only_world_picks_the_raw_best_chemical_cell():
    sim = _sim()
    sim.world.chemical[CHEM_CELL] = 5.0
    sim.world.chemical[(4, 5)] = 1.0
    o = _place(sim, 1.0, 1.0)
    behavior.decide_and_move(o, sim)
    assert sim.stim_obs["chemical"] == 1 and sim.stim_obs["light"] == 0
    cs = sim.cfg.cell_size
    assert o.y > (CUR[1] + 0.5) * cs, "chemicalの最良セル (y+方向) へ向かっていない"


def test_single_source_worlds_do_not_produce_ties():
    """単独sourceではtie経路に入らない (V1.4との完全一致の前提)。"""
    for kw, field, cell, val in (
            ({}, "light", LIGHT_CELL, 1.0),
            ({}, "chemical", CHEM_CELL, 5.0)):
        sim = _sim(**kw)
        getattr(sim.world, field)[cell] = val
        o = _place(sim, 1.0, 1.0)
        behavior.decide_and_move(o, sim)
        assert sim.stim_obs["tie"] == 0


# --- 観測が結果へ影響しないこと -----------------------------------------

def test_observation_counters_do_not_change_results():
    """同一seedの結果は観測カウンタの有無に依らない (指紋で確認)。"""
    a = Simulation(Config(), 3)
    for _ in range(200):
        a.step()
    fa = fingerprint(a)
    b = Simulation(Config(), 3)
    for _ in range(200):
        b.step()
        b.stim_obs = b._new_stim_obs()      # 途中でリセットしても結果は不変
    assert fingerprint(b) == fa


def test_observation_counters_do_not_consume_rng():
    a = Simulation(Config(), 5)
    for _ in range(100):
        a.step()
    state_a = a.rng.bit_generator.state
    b = Simulation(Config(), 5)
    for _ in range(100):
        b.step()
        b.stim_obs["light"] = 0
    assert b.rng.bit_generator.state == state_a


def test_counters_are_consistent():
    sim = Simulation(Config(), 7)
    for _ in range(200):
        sim.step()
    obs = sim.stim_obs
    # 両候補が存在した回数 = light選択 + chemical選択 + tie + 両score0
    assert obs["light"] + obs["chemical"] + obs["tie"] <= obs["both_events"]
    assert obs["agree"] == obs["light"] + obs["chemical"], \
        "無次元scoreの順位と実際の選択が一致していない"
    assert obs["lost_light"] <= obs["light"]
    assert obs["lost_chemical"] <= obs["chemical"]
    assert all(v >= 0 for v in obs.values())
