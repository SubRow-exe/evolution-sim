"""Exp20 A0_STATIC / freq=0.50 / seed=20001 を legacy light OFF で48h再現する。

Exp20実測 (legacy有効):  P0=50 -> P48=800 (16x) ,  A0=50 -> A48=50 (1.00x)

`Simulation._absorb_light()` (旧arbitrary単位light経路) を無効化すると、
V1.11 photo credit だけが残る。その条件で phototroph と ancestor が
区別できるかを見る。

所要時間の目安: 約150 s。

シミュレーション実験ではなく診断。正式実験ではない。
考察の正本: docs/Exp20_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../exp20_a0_legacy_off_replication.py
    # legacy を有効のまま比較したい場合:
    EXP20_LEGACY_LIGHT=on uv run python .../exp20_a0_legacy_off_replication.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for _p in (ROOT,
           ROOT / "experiments" / "exp20_v111_phototrophy_invasion",
           ROOT / "experiments" / "exp18_v1101_dynamic_vent"):
    sys.path.insert(0, str(_p))

import numpy as np                      # noqa: E402
import exp18_core                       # noqa: E402
import exp20_core as core               # noqa: E402
from evosim.simulation import Simulation  # noqa: E402

HOURS = 48.0
SEED = 20001
FREQ = 0.50
LEGACY_OFF = os.environ.get("EXP20_LEGACY_LIGHT", "off").lower() != "on"


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    cfg = core.make_cfg(f0r["f0_mol_s"], "A0_STATIC")
    if LEGACY_OFF:
        Simulation._absorb_light = lambda self, *a, **k: None
    sim, _ = core.setup_sim(cfg, SEED, exp18_core.common_initial_h2_field(f0r), FREQ)

    started = time.time()
    steps = int(HOURS * 3600.0 / cfg.dt_seconds)
    print(f"legacy _absorb_light = {'OFF' if LEGACY_OFF else 'ON'}   "
          f"(flux={cfg.light_photon_flux_umol_m2_s} µmol/m2/s)")
    print(f"{'h':>4}{'N_ph':>7}{'N_an':>7}{'meanM_ph':>10}{'meanM_an':>10}"
          f"{'meanE_ph':>12}{'meanE_an':>12}")
    for k in range(1, steps + 1):
        sim.step()
        if k % 720 != 0:
            continue
        photo = [o for o in sim.organisms if o.phototrophy_on]
        anc = [o for o in sim.organisms if not o.phototrophy_on]
        avg = lambda group, f: (float(np.mean([f(o) for o in group])) if group else float("nan"))
        print(f"{k * cfg.dt_seconds / 3600:4.0f}{len(photo):7d}{len(anc):7d}"
              f"{avg(photo, lambda o: o.matter):10.4f}{avg(anc, lambda o: o.matter):10.4f}"
              f"{avg(photo, lambda o: o.energy):12.4e}{avg(anc, lambda o: o.energy):12.4e}",
              flush=True)

    photo = [o for o in sim.organisms if o.phototrophy_on]
    anc = [o for o in sim.organisms if not o.phototrophy_on]
    print(f"\n{HOURS:.0f}h: P0=50 -> P48={len(photo)} ({len(photo) / 50:.2f}x) ; "
          f"A0=50 -> A48={len(anc)} ({len(anc) / 50:.2f}x)")
    print("Exp20報告値 (legacy有効): P48=800 (16.00x) ; A48=50 (1.00x)")
    print(f"elapsed {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
