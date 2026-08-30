"""V1.2 光場の検証 (docs/V1.2_V1.2.1_詳細実装仕様.md §4)。

Control (`vertical`) が V1.1 から1ビットも変わっていないこと、
Treatment (`high_contrast_vertical`) が
「総光量はControlと同じ / 空間偏在だけが強い」構造になっていることを保証する。
"""
import numpy as np
import pytest

from evosim.config import Config
from evosim.simulation import Simulation
from evosim.world import World, build_light_field

CONTROL_TOTAL = 1248.0  # 40x40, light_max=1.2, light_floor=0.3 の総光供給量


def hc_cfg(**kw) -> Config:
    return Config(light_pattern="high_contrast_vertical", **kw)


# --- Control 不変 ---------------------------------------------------------

def test_control_shape_and_total():
    light = build_light_field(Config())
    assert light.shape == (40, 40)
    assert light.sum() == pytest.approx(CONTROL_TOTAL, rel=1e-12)


def test_control_formula_unchanged():
    """V1.1 の計算式をそのまま再現しているか (比較基準そのもの)。"""
    cfg = Config()
    frac = 1.0 - (np.arange(cfg.grid_h) + 0.5) / cfg.grid_h
    col = cfg.light_max * (cfg.light_floor + (1.0 - cfg.light_floor) * frac)
    expected = np.tile(col, (cfg.grid_w, 1))
    assert np.array_equal(build_light_field(cfg), expected)


def test_uniform_unchanged():
    cfg = Config(light_pattern="uniform")
    assert np.array_equal(build_light_field(cfg),
                          np.full((40, 40), cfg.light_max))


# --- Treatment: 総光量 ----------------------------------------------------

def test_treatment_total_matches_control():
    """total_scale=1.0 なら世界全体のエネルギー流入量はControlと同一。"""
    assert build_light_field(hc_cfg()).sum() == pytest.approx(
        build_light_field(Config()).sum(), rel=1e-12)


@pytest.mark.parametrize("scale,expected", [
    (0.75, 936.0), (1.0, 1248.0), (1.25, 1560.0)])
def test_total_scale_axis(scale, expected):
    """shapeを固定したまま総光量だけを振れること (将来の光量実験の前提)。"""
    assert build_light_field(hc_cfg(light_hc_total_scale=scale)).sum() == \
        pytest.approx(expected, rel=1e-12)


def test_shape_independent_of_total_scale():
    """total_scale は一様スケールであり、形状比を変えない。"""
    a = build_light_field(hc_cfg(light_hc_total_scale=1.0))
    b = build_light_field(hc_cfg(light_hc_total_scale=0.75))
    assert np.allclose(b, a * 0.75, rtol=1e-12)


# --- Treatment: 帯構造 ----------------------------------------------------

def test_treatment_zone_structure():
    light = build_light_field(hc_cfg())
    col = light[0]  # 列方向は一様
    assert np.array_equal(light, np.tile(col, (40, 1)))

    bright, transition, dark = col[:8], col[8:28], col[28:]
    assert len(bright) == 8 and len(transition) == 20 and len(dark) == 12

    assert np.allclose(bright, bright[0], rtol=1e-12), "北8行はplateau"
    assert np.all(np.diff(transition) < 0), "中20行は単調減少"
    assert np.allclose(dark, 0.0, atol=1e-12), "南12行は完全暗部"
    assert np.all(light >= 0.0), "負の光量があってはならない"


def test_treatment_peak_value():
    """実効ピークは 1.2 * 13/9。空間偏在の代償としての上昇幅を固定する。"""
    light = build_light_field(hc_cfg())
    assert light.max() == pytest.approx(1.2 * 13.0 / 9.0, rel=1e-9)


def test_treatment_brighter_than_control_in_north_darker_in_south():
    c = build_light_field(Config())[0]
    t = build_light_field(hc_cfg())[0]
    assert t[:8].min() > c[:8].max(), "明部はControlより明るい"
    assert t[28:].max() < c[28:].min(), "暗部はControlより暗い"


# --- 乱数への非干渉 -------------------------------------------------------

def test_light_pattern_does_not_consume_rng():
    """光場生成が乱数を消費しないこと。

    消費していると同一seedでも chem_mask や初期個体配置がズレ、
    Control/Treatment の比較が「光以外も違う」ものになってしまう。
    """
    a = World(Config(), np.random.Generator(np.random.PCG64(7)))
    b = World(hc_cfg(), np.random.Generator(np.random.PCG64(7)))
    assert np.array_equal(a.chem_mask, b.chem_mask)
    assert np.array_equal(a.nutrients, b.nutrients)
    assert not np.array_equal(a.light, b.light), "光場は変わっているはず"


def test_initial_population_identical_across_patterns():
    """同一seedなら初期個体の遺伝子・配置も一致する。"""
    a = Simulation(Config(), 3)
    b = Simulation(hc_cfg(), 3)
    assert len(a.organisms) == len(b.organisms)
    for x, y in zip(a.organisms, b.organisms):
        assert (x.id, x.x, x.y) == (y.id, y.x, y.y)
        assert np.array_equal(x.genome, y.genome)


# --- Config validation ----------------------------------------------------

@pytest.mark.parametrize("kw", [
    {"light_hc_dark_floor": -0.1},
    {"light_hc_dark_floor": 1.0},
    {"light_hc_bright_frac": 0.0},
    {"light_hc_bright_frac": 1.0},
    {"light_hc_transition_frac": 0.0},
    {"light_hc_transition_frac": 1.5},
    {"light_hc_bright_frac": 0.6, "light_hc_transition_frac": 0.5},
    {"light_hc_total_scale": 0.0},
    {"light_hc_total_scale": -1.0},
])
def test_invalid_config_rejected(kw):
    with pytest.raises(ValueError):
        build_light_field(hc_cfg(**kw))


def test_unknown_pattern_rejected():
    with pytest.raises(ValueError, match="未知の light_pattern"):
        build_light_field(Config(light_pattern="spiral"))
