"""空間・行動指標 (V1.2.1)。

docs/V1.2_V1.2.1_詳細実装仕様.md §6。

**世界ルールを変えない読み取り専用の観測**。乱数を消費せず、
個体・環境の状態を書き換えない。観測ON/OFFで科学結果は完全に一致する。

地理帯は Treatment の設計zoneに合わせ、Control でも同じ位置・面積で算出する
(そうしないと「同じ場所を比べている」と言えないため)。

    North  / bright-design band : 0.00 <= y/H < 0.20
    Middle / transition-design  : 0.20 <= y/H < 0.70
    South  / dark-design band   : 0.70 <= y/H <= 1.00
"""
from __future__ import annotations

import math

import numpy as np

BAND_NORTH_END = 0.20
BAND_MIDDLE_END = 0.70
BAND_NAMES = ("north", "middle", "south")


def band_of(y: float, world_height: float) -> str:
    """個体のy座標が属する地理帯。Control/Treatment共通の固定定義。"""
    u = y / world_height if world_height > 0 else 0.0
    if u < BAND_NORTH_END:
        return "north"
    if u < BAND_MIDDLE_END:
        return "middle"
    return "south"


def band_counts(organisms, world_height: float) -> dict[str, int]:
    counts = {b: 0 for b in BAND_NAMES}
    for o in organisms:
        counts[band_of(o.y, world_height)] += 1
    return counts


def population_spatial(sim) -> dict:
    """集団全体の空間指標。stats.csv へ書き出す。"""
    orgs = sim.organisms
    n = len(orgs)
    cfg = sim.cfg
    counts = band_counts(orgs, cfg.world_height)

    light = sim.world.light
    chem_mask = sim.world.chem_mask
    hi_q = sim.hi_q_mask
    local_light = 0.0
    vent_pop = 0
    hi_q_pop = 0
    for o in orgs:
        ix, iy = sim.world.cell_index(o.x, o.y)
        local_light += float(light[ix, iy])
        if chem_mask[ix, iy]:
            vent_pop += 1
        if hi_q[ix, iy]:
            hi_q_pop += 1

    out: dict = {}
    for b in BAND_NAMES:
        out[f"pop_{b}_band"] = counts[b]
        out[f"frac_{b}_band"] = round(counts[b] / n, 6) if n else 0.0
    out["mean_local_light"] = round(local_light / n, 6) if n else 0.0
    out["vent_cell_population"] = vent_pop
    out["vent_cell_frac"] = round(vent_pop / n, 6) if n else 0.0
    # high-Q領域滞在率 (Exp10 §4/§5 の主観測)。面積で上位25%と定義してある
    out["hi_q_frac"] = round(hi_q_pop / n, 6) if n else 0.0
    return out


def lineage_spatial(sim, members: list) -> dict:
    """1系統の空間・行動指標。lineages.csv の行へ追加する。

    重心からの平均距離は「その系統がどれだけ広がっているか」を表す。
    占有セル数と併せて、局在しているのか世界中に散っているのかを見る。
    """
    cfg = sim.cfg
    world = sim.world
    n = len(members)
    if n == 0:
        return {}

    cells = set()
    sx = sy = 0.0
    local_light = 0.0
    vent = 0
    for o in members:
        ix, iy = world.cell_index(o.x, o.y)
        cells.add((ix, iy))
        sx += o.x
        sy += o.y
        local_light += float(world.light[ix, iy])
        if world.chem_mask[ix, iy]:
            vent += 1
    cx, cy = sx / n, sy / n
    radius = sum(math.hypot(o.x - cx, o.y - cy) for o in members) / n

    lid = members[0].lineage_id
    mc = sim._movecnt_by_lineage.get(lid, 0)
    move = (sim._move_by_lineage.get(lid, 0.0) / mc) if mc else float("nan")

    g = np.stack([o.genome for o in members])
    from .genome import CHEM_ABS

    return {
        "occupied_cells": len(cells),
        "centroid_x": round(cx, 3),
        "centroid_y": round(cy, 3),
        "mean_radius_from_centroid": round(radius, 3),
        "mean_move_per_org_tick": (round(move, 6) if mc else ""),
        "mean_local_light": round(local_light / n, 6),
        "vent_cell_frac": round(vent / n, 6),
        "mean_chemical_absorption": round(float(g[:, CHEM_ABS].mean()), 6),
    }


def save_static_environment(path, sim) -> None:
    """実行を通じて不変な環境 (光場・噴出口配置) を1度だけ保存する。"""
    np.savez_compressed(path, light=sim.world.light, chem_mask=sim.world.chem_mask)


def save_environment_snapshot(path, sim) -> None:
    """時間変化する環境 (化学ストック・無機栄養) を保存する。"""
    np.savez_compressed(path, chemical=sim.world.chemical,
                        nutrients=sim.world.nutrients)
