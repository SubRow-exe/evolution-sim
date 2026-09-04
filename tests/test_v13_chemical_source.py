"""H2 substrate field のテスト (V1.9: 旧V1.3 chemical fieldをH2へ再設計)。

正本: docs/V1.9_iLUCA再設計仕様.md §8-10, 実装チェックリスト.md F節。

V1.9でvent配置アルゴリズム自体を再設計した (world端からr以上内側・
source disk非重複・全vent同一総flux・決定的候補順序からrng選択)。
旧V1.3の「edge clipping時share再配分」「1ventにつきrng.integers 2回」
という仕様はここでは成立しないため、本ファイルは新アルゴリズムの
不変条件を検証する。
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim.config import Config
from evosim.world import World, _equilibrium_h2, _place_vents


def _rng(seed=1):
    return np.random.Generator(np.random.PCG64(seed))


# --- vent配置 (§9) -----------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_vent_centers_stay_r_inside_edges(seed):
    cfg = Config(n_vents=4, vent_radius_cells=2)
    centers = _place_vents(cfg, _rng(seed))
    r = cfg.vent_radius_cells
    for vx, vy in centers:
        assert r <= vx <= cfg.grid_w - r - 1
        assert r <= vy <= cfg.grid_h - r - 1


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_vent_source_disks_do_not_overlap(seed):
    cfg = Config(n_vents=4, vent_radius_cells=2)
    centers = _place_vents(cfg, _rng(seed))
    r = cfg.vent_radius_cells
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            (x1, y1), (x2, y2) = centers[i], centers[j]
            assert (x1 - x2) ** 2 + (y1 - y2) ** 2 > (2 * r) ** 2, (
                f"vent {centers[i]} と {centers[j]} のsource diskが重なる")


def test_vent_placement_raises_when_infeasible():
    """world/半径に対してn_ventsが多すぎる場合はValueError。"""
    with pytest.raises(ValueError):
        Config(world_width=40.0, world_height=40.0, cell_size=20.0,
               n_vents=100, vent_radius_cells=1)


def test_vent_placement_deterministic_for_same_seed():
    cfg = Config(n_vents=4, vent_radius_cells=2)
    c1 = _place_vents(cfg, _rng(7))
    c2 = _place_vents(cfg, _rng(7))
    assert c1 == c2


def test_all_vents_have_equal_total_flux():
    """全vent中心がedgeから離れているため、source diskは常に欠けず、
    各ventの総fluxはn_ventsで均等分配される (§9)。"""
    cfg = Config(n_vents=4, vent_radius_cells=2, h2_vent_flux=16.0)
    world = World(cfg, _rng(3))
    r = cfg.vent_radius_cells
    for vx, vy in world.vent_centers:
        cells = [(ix, iy) for ix in range(vx - r, vx + r + 1)
                 for iy in range(vy - r, vy + r + 1)
                 if (ix - vx) ** 2 + (iy - vy) ** 2 <= r * r]
        total = sum(world.h2_source_flux[ix, iy] for ix, iy in cells)
        assert total == pytest.approx(cfg.h2_vent_flux, rel=1e-9)


def test_world_h2_source_total_is_n_vents_times_flux():
    cfg = Config(n_vents=4, vent_radius_cells=2, h2_vent_flux=16.0)
    world = World(cfg, _rng(1))
    assert world.h2_source_total == pytest.approx(cfg.n_vents * cfg.h2_vent_flux, rel=1e-9)


# --- 拡散 (§10) ---------------------------------------------------------

def test_diffusion_alone_conserves_total_h2():
    """source/lossを止めても拡散だけでは総H2量が変わらない。"""
    gw, gh = 10, 10
    rng = np.random.Generator(np.random.PCG64(1))
    h2 = rng.uniform(0.0, 10.0, size=(gw, gh))
    from evosim.world import _diffuse_h2
    zero_source = np.zeros((gw, gh))
    before = float(h2.sum())
    after = _diffuse_h2(h2, loss_frac=0.0, diffusion=0.1, source_flux=zero_source)
    assert float(after.sum()) == pytest.approx(before, rel=1e-9)


def test_diffusion_forms_halo_around_source():
    """source周辺セルのH2濃度がsourceから離れるほど連続的に下がる (halo)。"""
    cfg = Config(n_vents=1, vent_radius_cells=1, h2_vent_flux=16.0,
                 h2_diffusion=0.1, h2_loss_frac=0.1)
    world = World(cfg, _rng(1))
    vx, vy = world.vent_centers[0]
    vals = [float(world.h2[vx + d, vy]) for d in range(0, 6)]
    # source中心から離れるにつれ単調非増加 (halo/勾配)
    for a, b in zip(vals, vals[1:]):
        assert b <= a + 1e-9
    # source外 (半径を超えた位置) にも非ゼロのH2が存在する (階段場ではない)
    assert vals[3] > 0.0


def test_equilibrium_h2_is_deterministic_and_rng_free():
    cfg = Config(n_vents=4, vent_radius_cells=2)
    w1 = World(cfg, _rng(11))
    w2 = World(cfg, _rng(11))
    assert np.array_equal(w1.h2, w2.h2)


def test_equilibrium_h2_matches_manual_fixed_point_iteration():
    cfg = Config(n_vents=2, vent_radius_cells=2, h2_vent_flux=16.0,
                 h2_loss_frac=0.1, h2_diffusion=0.05)
    world = World(cfg, _rng(1))
    source = world.h2_source_flux
    manual = _equilibrium_h2(source, cfg.h2_loss_frac, cfg.h2_diffusion)
    assert np.array_equal(world.h2, manual)


def test_update_conserves_h2_via_influx_minus_loss():
    cfg = Config(n_vents=4, vent_radius_cells=2)
    world = World(cfg, _rng(1))
    before = float(world.h2.sum())
    influx, loss = world.update()
    after = float(world.h2.sum())
    assert after == pytest.approx(before + influx - loss, rel=1e-9)


def test_stock_is_never_negative():
    cfg = Config(n_vents=4, vent_radius_cells=2, h2_loss_frac=0.5)
    world = World(cfg, _rng(1))
    for _ in range(500):
        world.update()
        assert float(world.h2.min()) >= 0.0
