"""Exp20 A0の「phototroph 16x」がV1.11機構由来かを切り分ける。

診断内容:
  1. V1.11 photo credit の理論値 (P_usable * dt) を実baselineで出す
  2. Exp20 formal config を1 step走らせ、phototrophが実際に得たEnergyと比較する
  3. legacy `Simulation._absorb_light()` を無効化して同じ条件を再実行し、差分を見る

`_absorb_light()` は physical_mode / physical_light_enabled で分岐しておらず、
旧arbitrary単位 (`world.light` max 1.2、`light_uptake_coef` 2.0) の需要を
Joule建ての `org.energy` へ直接加算する。phototrophy OFF個体は capability gate で
light_absorption=0 に固定されるため需要0となり、Exp19以前は顕在化しなかった。

シミュレーション実験ではなく診断。正式実験ではない。
考察の正本: docs/Exp20_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../exp20_legacy_light_leak.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for _p in (ROOT,
           ROOT / "experiments" / "exp20_v111_phototrophy_invasion",
           ROOT / "experiments" / "exp18_v1101_dynamic_vent"):
    sys.path.insert(0, str(_p))

import exp18_core                       # noqa: E402
import exp20_core as core               # noqa: E402
from evosim import physiology           # noqa: E402
from evosim.simulation import Simulation  # noqa: E402

STEPS = 30
SEED = 20001
FREQ = 0.50


def _trial(legacy_off: bool, f0: float, h2f):
    cfg = core.make_cfg(f0, "A0_STATIC")
    original = Simulation._absorb_light
    if legacy_off:
        Simulation._absorb_light = lambda self, *a, **k: None
    try:
        sim, _ = core.setup_sim(cfg, SEED, h2f, FREQ)
        photo = next(o for o in sim.organisms if o.phototrophy_on)
        ancestor = next(o for o in sim.organisms if not o.phototrophy_on)
        e_start = photo.energy
        for _ in range(STEPS):
            sim.step()
        return cfg, sim, photo, ancestor, e_start
    finally:
        Simulation._absorb_light = original


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    f0 = f0r["f0_mol_s"]
    h2f = exp18_core.common_initial_h2_field(f0r)

    cfg_on, sim_on, ph_on, an_on, e0 = _trial(False, f0, h2f)
    cfg_off, sim_off, ph_off, an_off, _ = _trial(True, f0, h2f)

    p_inc, p_abs, p_use = physiology.photo_power_chain_w(ph_off, cfg_off)
    pf_a = physiology.full_activity_expenditure_rate(an_off, cfg_off)
    pf_p = physiology.full_activity_expenditure_rate(ph_off, cfg_off)

    print("=" * 70)
    print("1. V1.11 photo credit の理論値 (Exp20 formal config)")
    print("=" * 70)
    print(f"  photon flux              : {cfg_off.light_photon_flux_umol_m2_s} µmol/m2/s")
    print(f"  light_absorption         : {core.PHOTOTROPH_LIGHT_ABSORPTION}")
    print(f"  P_incident               : {p_inc * 1e15:.4f} fW")
    print(f"  P_absorbed               : {p_abs * 1e15:.5f} fW")
    print(f"  P_usable (= credit)      : {p_use * 1e15:.5f} fW")
    print(f"  ancestor maintenance     : {pf_a * 1e15:.5f} fW")
    print(f"  credit / maintenance     : {p_use / pf_a * 100:.3f} %")
    print(f"  phototrophの追加維持コスト : {(pf_p - pf_a) * 1e15:+.6f} fW")
    print(f"  正味                      : {(p_use - (pf_p - pf_a)) / pf_a * 100:+.3f} % of maintenance")
    print(f"  -> {STEPS} step (= {STEPS * cfg_off.dt_seconds:.0f} s) の credit = "
          f"{p_use * cfg_off.dt_seconds * STEPS:.4e} J")

    print()
    print("=" * 70)
    print(f"2. 実際の {STEPS} step の挙動")
    print("=" * 70)
    print(f"  {'':34}{'phototroph':>15}{'ancestor':>15}")
    print(f"  {'t=0 energy [J]':34}{e0:15.4e}{e0:15.4e}")
    print(f"  {'legacy ON  : energy [J]':34}{ph_on.energy:15.4e}{an_on.energy:15.4e}")
    print(f"  {'legacy OFF : energy [J]':34}{ph_off.energy:15.4e}{an_off.energy:15.4e}")
    print(f"  {'legacy ON  : matter':34}{ph_on.matter:15.5f}{an_on.matter:15.5f}")
    print(f"  {'legacy OFF : matter':34}{ph_off.matter:15.5f}{an_off.matter:15.5f}")

    leak = ph_on.energy - ph_off.energy
    credit = p_use * cfg_off.dt_seconds * STEPS
    print()
    print("=" * 70)
    print("3. 判定")
    print("=" * 70)
    print(f"  legacy有効時に phototroph が余分に得たEnergy : {leak:.4e} J")
    print(f"  V1.11 photo credit が与えたEnergy            : {credit:.4e} J")
    print(f"  倍率                                          : {leak / credit:.4e} x")
    print()
    print("  E_max =", f"{physiology.energy_max(ph_off, cfg_off):.4e} J")
    print("  -> legacyの需要はheadroomでclampされるため、毎step E_max まで充填される。")


if __name__ == "__main__":
    main()
