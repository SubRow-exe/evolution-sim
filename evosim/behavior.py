"""感覚と行動決定 (MVP版・仕様書 Ver.1.1 §9)。

「検出 → 接近、なければランダム探索」のみの意図的に単純なルール。
刺激スコアは遺伝子 (能力) × 資源量。Phase 7 で神経進化に置き換える差し替え点。
"""
from __future__ import annotations

import math

import numpy as np

from .genome import (CHEM_ABS, CORPSE_DIG, LIGHT_ABS, MEMBRANE, MOVE_POWER,
                     NUTRIENT_ABS, PREDATION, SENSORY)

ABILITY_EPS = 1e-3  # これ未満の能力は刺激として無視 (ゼロ能力の空走査を省く)


def decide_and_move(org, sim) -> float:
    """1個体の行動決定と移動。戻り値: 実際に移動した速度 [wu/tick]。"""
    cfg = sim.cfg
    world = sim.world
    g = org.genome

    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    e_max = org.energy_max(cfg.energy_capacity)
    matter_cap = cfg.matter_cap_frac * org.target_size

    # 満ち足りていれば待機
    if org.energy >= cfg.satiety_energy_frac * e_max and org.matter >= org.target_size:
        return 0.0

    v_max = cfg.speed_coef * g[MOVE_POWER] / math.sqrt(max(org.matter, 1e-9)) * phi

    # --- 刺激走査 ---
    sense_r = cfg.sense_coef * g[SENSORY]
    best_score = 0.0
    target: tuple[float, float] | None = None
    stay = False  # 現在セルが最良 → 停止して吸収

    ix0, iy0 = world.cell_index(org.x, org.y)
    cr = int(sense_r / cfg.cell_size)
    x_lo, x_hi = max(0, ix0 - cr), min(cfg.grid_w, ix0 + cr + 1)
    y_lo, y_hi = max(0, iy0 - cr), min(cfg.grid_h, iy0 + cr + 1)

    want_energy = org.energy < cfg.satiety_energy_frac * e_max
    want_matter = org.matter < matter_cap

    # フィールド刺激 (栄養・光・化学): 走査範囲内の最良セル
    field_specs = []
    if g[NUTRIENT_ABS] > ABILITY_EPS and want_matter:
        field_specs.append((world.nutrients, g[NUTRIENT_ABS]))
    if want_energy:
        if g[LIGHT_ABS] > ABILITY_EPS:
            field_specs.append((world.light, g[LIGHT_ABS]))
        if g[CHEM_ABS] > ABILITY_EPS:
            field_specs.append((world.chemical, g[CHEM_ABS]))
    for arr, ability in field_specs:
        sub = arr[x_lo:x_hi, y_lo:y_hi]
        flat = int(np.argmax(sub))
        val = float(sub.flat[flat])
        score = ability * val
        if score > best_score:
            bi, bj = divmod(flat, sub.shape[1])
            cx, cy = world.cell_center(x_lo + bi, y_lo + bj)
            best_score = score
            if (x_lo + bi, y_lo + bj) == (ix0, iy0):
                stay = True
                target = None
            else:
                stay = False
                target = (cx, cy)

    # 死骸
    if g[CORPSE_DIG] > ABILITY_EPS:
        for cell in _cells(sim.corpse_hash, x_lo, x_hi, y_lo, y_hi):
            for c in cell:
                if c.matter <= 0.0:
                    continue
                if _dist2(org.x, org.y, c.x, c.y) > sense_r * sense_r:
                    continue
                score = g[CORPSE_DIG] * c.matter
                if score > best_score:
                    best_score = score
                    target = (c.x, c.y)
                    stay = False

    # 他個体 (捕食対象)。膜を破れる見込みがある相手のみ追跡する。
    if g[PREDATION] > ABILITY_EPS:
        my_attack = cfg.attack_coef * g[PREDATION] * org.matter * phi
        for cell in _cells(sim.org_hash, x_lo, x_hi, y_lo, y_hi):
            for other in cell:
                if other is org or not other.alive:
                    continue
                if _dist2(org.x, org.y, other.x, other.y) > sense_r * sense_r:
                    continue
                defense = cfg.defense_coef * other.genome[MEMBRANE] * other.matter
                if my_attack <= defense:
                    continue
                score = g[PREDATION] * other.matter
                if score > best_score:
                    best_score = score
                    target = (other.x, other.y)
                    stay = False

    # --- 移動 ---
    if stay or v_max <= 0.0:
        return 0.0
    if target is not None:
        dx, dy = target[0] - org.x, target[1] - org.y
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            return 0.0
        org.heading = math.atan2(dy, dx)
        v = min(v_max, dist)
    else:
        # ランダムウォーク
        org.heading += sim.rng.normal(0.0, cfg.wander_turn_sigma)
        v = v_max * cfg.wander_speed_frac

    org.x += math.cos(org.heading) * v
    org.y += math.sin(org.heading) * v
    r = org.radius(cfg.radius_coef)
    org.x = min(max(org.x, r), cfg.world_width - r)
    org.y = min(max(org.y, r), cfg.world_height - r)
    return v


def _cells(hash_map: dict, x_lo: int, x_hi: int, y_lo: int, y_hi: int):
    for ix in range(x_lo, x_hi):
        for iy in range(y_lo, y_hi):
            cell = hash_map.get((ix, iy))
            if cell:
                yield cell


def _dist2(x1: float, y1: float, x2: float, y2: float) -> float:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2
