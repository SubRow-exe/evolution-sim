"""CI entrypoint for Exp24 preflight.

The formal Exp24 population has no births during the first ~48 h in some seeds.
The original preflight tried to observe de-novo phototrophy within 6-12 h, so
G1 (and several founder gates) could fail/pass vacuously simply because no
birth occurred.  This wrapper keeps every formal scientific parameter intact
and replaces only the diagnostic implementations of G1-G7/G9 with
forced-birth diagnostics that deterministically exercise the real
Simulation._try_reproduce -> structural_mutate path.
"""
from __future__ import annotations

import dataclasses

import preflight_exp24 as base
import run_exp24 as core
from evosim import physiology
from evosim.genome import LIGHT_ABS, REPRO_HORIZON


def _prepare_birth_parent(sim, org):
    """Make one existing organism reproduction-eligible for diagnostic use.

    This mutates diagnostic state only; no formal Exp24 config or run uses this
    helper.  The actual reproduction/structural-mutation implementation is left
    untouched and is invoked through Simulation._try_reproduce().
    """
    org.genome[REPRO_HORIZON] = 0.0
    threshold = sim.cfg.repro_matter_frac * org.target_size
    org.matter = max(org.matter, threshold * 1.05 + 1e-12)
    org.energy = physiology.energy_max(org, sim.cfg)
    return org


def _force_birth(sim, org):
    _prepare_birth_parent(sim, org)
    child = sim._try_reproduce(org)
    if child is None:
        raise RuntimeError("Exp24 diagnostic could not force an eligible birth")
    sim.organisms.append(child)
    return child


def check_g1_g7(f0, h2_field, seed: int, hours: float = 6.0) -> dict:
    """Deterministically verify structural-only OFF->ON acquisition.

    innovation=1 is diagnostic-only so an eligible OFF parent must create an ON
    child through the production reproduction path. innovation=0 must create an
    OFF child with zero LIGHT_ABS, proving continuous mutation cannot bypass the
    capability gate.
    """
    cfg_on = dataclasses.replace(
        core.make_cfg(f0, 1.5),
        phototrophy_innovation_prob=1.0,
        phototrophy_loss_prob=0.0,
    )
    sim_on = core.setup_all_off(cfg_on, seed, h2_field)
    child_on = _force_birth(sim_on, sim_on.organisms[0])
    any_on = (
        sim_on.phototrophy_innovation_events == 1
        and child_on.phototrophy_on
        and child_on.photo_founder_id is not None
        and child_on.genome[LIGHT_ABS] == core.PHOTOTROPH_SEED_ABSORPTION
    )

    cfg_off = dataclasses.replace(
        core.make_cfg(f0, 1.5),
        phototrophy_innovation_prob=0.0,
        phototrophy_loss_prob=0.0,
    )
    sim_off = core.setup_all_off(cfg_off, seed, h2_field)
    child_off = _force_birth(sim_off, sim_off.organisms[0])
    none_on = (
        sim_off.phototrophy_innovation_events == 0
        and not child_off.phototrophy_on
        and child_off.photo_founder_id is None
        and child_off.genome[LIGHT_ABS] == 0.0
    )
    return {
        "seed": seed,
        "diagnostic_forced_birth": True,
        "innovation_on_any_on": bool(any_on),
        "innovation_off_none_on": bool(none_on),
        "G1_structural_only": bool(any_on and none_on),
        "G7_no_continuous_bypass": bool(none_on),
    }


def check_g2_g3_g4_g9(f0, h2_field, seed: int, hours: float = 12.0) -> dict:
    """Exercise founder phenotype, inheritance, distinct IDs and assembly.

    Two independent OFF parents are forced to reproduce at the same simulation
    tick with diagnostic innovation=1, then one founder is forced to reproduce
    again.  This makes G2/G3/G4 non-vacuous.  G9 checks that a new founder has
    zero absorbed/usable light before structural-N assembly, and that assembly
    draws N without breaking the system-N ledger.
    """
    cfg = dataclasses.replace(
        core.make_cfg(f0, 1.5),
        phototrophy_innovation_prob=1.0,
        phototrophy_loss_prob=0.0,
    )
    sim = core.setup_all_off(cfg, seed, h2_field)

    founder1 = _force_birth(sim, sim.organisms[0])
    founder2 = _force_birth(sim, sim.organisms[1])
    founders = [founder1, founder2]

    g2_ok = all(
        o.phototrophy_on
        and o.genome[LIGHT_ABS] == core.PHOTOTROPH_SEED_ABSORPTION
        and o.photo_founder_id is not None
        for o in founders
    )
    fids = [o.photo_founder_id for o in founders]
    g4_ok = len(fids) == 2 and None not in fids and len(set(fids)) == 2

    descendant = _force_birth(sim, founder1)
    g3_ok = (
        descendant.phototrophy_on
        and descendant.photo_founder_id == founder1.photo_founder_id
        and descendant.genome[LIGHT_ABS] > 0.0
    )

    # A de-novo founder receives no structural-N from its OFF parent.
    pre_n = founder2.photo_structural_n_mol
    _, p_abs_before, p_use_before = physiology.photo_power_chain_w(founder2, cfg)
    n_before_assembly = sim.system_nitrogen()
    sim._assemble_photo_structural_n()
    n_after_assembly = sim.system_nitrogen()
    ledger_rel = abs(n_after_assembly - n_before_assembly) / max(abs(n_before_assembly), 1e-300)
    g9_ok = (
        pre_n == 0.0
        and p_abs_before == 0.0
        and p_use_before == 0.0
        and founder2.photo_structural_n_mol > 0.0
        and ledger_rel < 1e-6
    )

    return {
        "seed": seed,
        "n_founders_observed": 2,
        "same_tick_multi_origin_observed": True,
        "descendant_inheritance_observed": True,
        "assembly_ledger_relative_residual": float(ledger_rel),
        "G2_founder_phenotype": bool(g2_ok),
        "G3_founder_tag_inheritance": bool(g3_ok),
        "G4_independent_founder_ids": bool(g4_ok),
        "G9_credit_zero_before_assembly": bool(g9_ok),
    }


def check_g4_same_tick(f0, h2_field, seed: int) -> dict:
    cfg = dataclasses.replace(
        core.make_cfg(f0, 1.5),
        phototrophy_innovation_prob=1.0,
        phototrophy_loss_prob=0.0,
    )
    sim = core.setup_all_off(cfg, seed, h2_field)
    tick0 = sim.tick
    a = _force_birth(sim, sim.organisms[0])
    b = _force_birth(sim, sim.organisms[1])
    fids = [a.photo_founder_id, b.photo_founder_id]
    found = sim.tick == tick0 and all(fid is not None for fid in fids)
    ok = found and len(set(fids)) == 2
    return {
        "seed": seed,
        "found_same_tick_multi_origin": bool(found),
        "G4_same_tick_distinct_ids": bool(ok),
    }


def check_g5(f0, h2_field, seed: int, hours: float = 6.0) -> dict:
    """Verify formal probability is 0.01 and no first-origin lock exists."""
    formal_cfg = core.make_cfg(f0, 1.5)
    formal_prob_ok = formal_cfg.phototrophy_innovation_prob == core.PHOTOTROPH_INNOVATION_PROB

    diag_cfg = dataclasses.replace(
        formal_cfg,
        phototrophy_innovation_prob=1.0,
        phototrophy_loss_prob=0.0,
    )
    sim = core.setup_all_off(diag_cfg, seed, h2_field)
    prob_before = sim.cfg.phototrophy_innovation_prob
    _force_birth(sim, sim.organisms[0])
    first_origin_seen = sim.phototrophy_innovation_events > 0
    prob_after = sim.cfg.phototrophy_innovation_prob
    unchanged = prob_before == prob_after == 1.0
    return {
        "seed": seed,
        "formal_prob": float(formal_cfg.phototrophy_innovation_prob),
        "first_origin_seen": bool(first_origin_seen),
        "prob_unchanged_after_forced_origin": bool(unchanged),
        "G5_no_single_origin_lock": bool(formal_prob_ok and first_origin_seen and unchanged),
    }


def check_g6(f0, h2_field, seed: int, hours: float = 24.0) -> dict:
    """Create an ON founder, then verify loss=0 preserves ON inheritance."""
    cfg = dataclasses.replace(
        core.make_cfg(f0, 1.5),
        phototrophy_innovation_prob=1.0,
        phototrophy_loss_prob=0.0,
    )
    sim = core.setup_all_off(cfg, seed, h2_field)
    founder = _force_birth(sim, sim.organisms[0])
    child = _force_birth(sim, founder)
    ok = (
        sim.phototrophy_loss_events == 0
        and founder.phototrophy_on
        and child.phototrophy_on
        and child.photo_founder_id == founder.photo_founder_id
    )
    return {
        "seed": seed,
        "loss_events": int(sim.phototrophy_loss_events),
        "n_on_ever": 2,
        "G6_loss_disabled": bool(ok),
    }


# Replace only diagnostic gates. Formal configuration/run code is unchanged.
base.check_g1_g7 = check_g1_g7
base.check_g2_g3_g4_g9 = check_g2_g3_g4_g9
base.check_g4_same_tick = check_g4_same_tick
base.check_g5 = check_g5
base.check_g6 = check_g6


if __name__ == "__main__":
    base.main()
