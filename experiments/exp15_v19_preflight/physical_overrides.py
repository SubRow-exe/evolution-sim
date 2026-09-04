"""Temporary V1.9 Phase0-only corrections for identified physical-mode wiring gaps.

No scientific parameter tuning is performed. Formal Exp15 remains blocked until
these semantics are moved into evosim core and covered by tests.
"""
from __future__ import annotations

import math
import numpy as np

from evosim import behavior, physiology, world as world_module

_INSTALLED = False
_ORIG_DECIDE = behavior.decide_and_move


def _diffuse_h2_physical_fixed(h2: np.ndarray, cfg, source_mask: np.ndarray):
    n_sub, dt_sub, alpha = world_module._h2_subcycle_params(cfg)
    voxel_volume = cfg.cell_size * cfg.cell_size * cfg.effective_depth_m
    c_source = cfg.h2_source_concentration_molm3
    c = h2.copy()
    source_in_mol = 0.0
    exchange_loss_mol = 0.0
    for _ in range(n_sub):
        loss = c * (dt_sub / cfg.h2_exchange_tau_s)
        exchange_loss_mol += float(loss.sum()) * voxel_volume
        c = c - loss
        padded = np.pad(c, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * c)
        c = c + alpha * lap
        if np.any(source_mask):
            deficit = c_source - c[source_mask]
            source_in_mol += float(deficit.sum()) * voxel_volume
            c[source_mask] = c_source
    return c, source_in_mol, exchange_loss_mol


def _physical_maintenance_and_movement_fixed(org, cfg, v: float, state: float) -> float:
    p_ref = physiology.reference_basal_power_w(cfg)
    fr = physiology._basal_component_fractions(org.genome, org.matter)
    core = p_ref * cfg.basal_weight_core * fr["core"]
    functional = p_ref * (
        cfg.basal_weight_organ * fr["organ"]
        + cfg.basal_weight_sense * fr["sense"]
        + cfg.basal_weight_membrane * fr["membrane"]
        + cfg.basal_weight_resistance * fr["resistance"]
        + cfg.basal_weight_storage * fr["storage"]
    )
    mfac = physiology.metabolic_factor(state, cfg)
    move = physiology.physical_move_power_w(org.matter, v, cfg)
    cost_j = (core + mfac * functional + move) * cfg.dt_seconds
    org.energy -= cost_j
    org.damage += cfg.metabolic_damage * org.matter
    org.damage += cfg.movement_damage * org.matter * v * v
    return cost_j


def _decide_and_move_physical_fixed(org, sim):
    cfg = sim.cfg
    if not cfg.physical_mode:
        return _ORIG_DECIDE(org, sim)
    x0, y0 = org.x, org.y
    v = _ORIG_DECIDE(org, sim)
    if v <= 0.0:
        return v
    displacement = v * cfg.dt_seconds
    r = physiology.physical_radius_m(org.matter, cfg)
    org.x = min(max(x0 + math.cos(org.heading) * displacement, r), cfg.world_width - r)
    org.y = min(max(y0 + math.sin(org.heading) * displacement, r), cfg.world_height - r)
    return v


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    world_module._diffuse_h2_physical = _diffuse_h2_physical_fixed
    physiology._physical_maintenance_and_movement = _physical_maintenance_and_movement_fixed
    behavior.decide_and_move = _decide_and_move_physical_fixed
    _INSTALLED = True
