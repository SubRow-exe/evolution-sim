"""Initial-state normalization for Exp20 Attempt 2 paired fitness assay.

The paired assay must change only the intended trait at t=0.  In the shared
Exp18 setup, initial Energy is assigned as 50% of each organism's own E_max.
Because E_max is proportional to storage_capacity, that makes storage variants
start with different absolute Energy and confounds the trait effect.

For Attempt 2 we therefore keep the *absolute* starting Energy equal to the
baseline phenotype's 50%-filled value.  The storage-capacity variant is allowed
to change the resulting fill fraction, E_max, upkeep, runway and other derived
physiology; those are genuine consequences of the trait and must not be masked.
"""
from __future__ import annotations

import exp18_core
from evosim import physiology
from evosim.genome import INITIAL_GENOME, STORAGE_CAP

_ORIGINAL_SETUP_SIM = exp18_core.setup_sim
_INSTALLED = False


def _baseline_half_full_energy_j(org, cfg) -> float:
    """Absolute t=0 Energy used for every baseline/variant organism."""
    emax_ref = (
        physiology.reference_basal_power_w(cfg)
        * cfg.storage_capacity_hours
        * 3600.0
    )
    baseline_storage = float(INITIAL_GENOME[STORAGE_CAP])
    baseline_emax = emax_ref * baseline_storage * float(org.matter)
    return 0.5 * baseline_emax


def normalized_setup_sim(cfg, seed: int, initial_h2_field, vent_positions=exp18_core.LEGACY_FOUR_CENTERS):
    """Run Exp18 setup, then normalize only the exogenous t=0 Energy condition."""
    sim = _ORIGINAL_SETUP_SIM(cfg, seed, initial_h2_field, vent_positions=vent_positions)

    for org in sim.organisms:
        e0 = _baseline_half_full_energy_j(org, cfg)
        emax = physiology.energy_max(org, cfg)
        tol = max(1e-30, abs(emax) * 1e-12)
        if e0 > emax + tol:
            raise RuntimeError(
                "Attempt2 baseline absolute initial Energy exceeds variant E_max: "
                f"org={org.id} e0={e0:.17g} emax={emax:.17g} "
                f"storage_capacity={org.genome[STORAGE_CAP]:.17g}"
            )
        org.energy = e0
        # starvation state is derived from Energy + the variant phenotype and is
        # intentionally allowed to differ when the target trait changes.
        org.starve_state = physiology.starvation_state(org, cfg)

    # setup_sim recorded the pre-normalization system Energy.  Reset the ledger
    # reference after normalization so formal Energy accounting remains closed.
    sim.initial_system_energy = sim.system_energy()
    return sim


def install() -> None:
    """Patch only the Attempt2 harness' imported Exp18 setup function."""
    global _INSTALLED
    if not _INSTALLED:
        exp18_core.setup_sim = normalized_setup_sim
        _INSTALLED = True
