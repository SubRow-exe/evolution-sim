"""Exp22 の OFF run が photon flux に依存しないことを検証する。

`light_photon_flux_umol_m2_s` はコード中 `physiology.physical_light_incident_power_w`
の1箇所でしか読まれず、そこへ到達する唯一の経路 `photo_power_chain_w` は
`not org.phototrophy_on` なら (0,0,0) を返す。`run_exp22.setup_paired` は
capability_on=False のとき `exp18_core.setup_sim` をそのまま呼ぶだけなので、
全個体 OFF の run では flux はどこにも効かないはずである。

これが成り立つと、Exp22 の 6 つの flux 水準は「独立した6比較」ではなく
**同一の OFF baseline に対する6回の ON 側測定**になる。したがって
zero-light 行 (-4.56%) は RNG divergence ではなく ON 側の系統的な差である。

所要時間の目安: 約3分 (24h run × 3)。

シミュレーション実験ではなく診断。正式実験ではない。
考察の正本: docs/Exp22_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../exp22_off_run_flux_independence.py
"""
from __future__ import annotations

import glob
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for _p in (ROOT, ROOT / "experiments" / "exp18_v1101_dynamic_vent"):
    sys.path.insert(0, str(_p))
for _d in glob.glob(str(ROOT / "experiments" / "exp22*")):
    sys.path.insert(0, _d)

import exp18_core            # noqa: E402
import run_exp22 as exp22    # noqa: E402

ENVIRONMENT = "A2_DYNAMIC_VENT"
SEED = 22001
HOURS = 24.0
FLUXES = (0.0, 0.5, 1.5)


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    h2_field = exp18_core.common_initial_h2_field(f0r)

    keys, fingerprints = [], []
    for flux in FLUXES:
        cfg = exp22.make_cfg(f0r["f0_mol_s"], ENVIRONMENT, flux)
        started = time.time()
        rows, _summary, fingerprint = exp22.run_one(
            cfg, SEED, h2_field, HOURS, capability_on=False)
        final = rows[-1]
        keys.append((final.get("population"),
                     repr(final.get("total_living_matter")),
                     final.get("births_cum"),
                     final.get("deaths_cum")))
        fingerprints.append(fingerprint)
        print(f"flux={flux:<5} OFF run: population={final.get('population')} "
              f"total_living_matter={final.get('total_living_matter'):.12g} "
              f"births={final.get('births_cum')} deaths={final.get('deaths_cum')}"
              f"  ({time.time() - started:.0f}s)", flush=True)

    print()
    identical = len(set(keys)) == 1
    print(f"全fluxで OFF run が完全一致 : {'YES' if identical else 'NO'}")
    print(f"initial fingerprint 一致    : "
          f"{'YES' if len(set(fingerprints)) == 1 else 'NO'}")
    if identical:
        print()
        print("-> Exp22 の 6 行は同一 OFF baseline に対する 6 回の ON 側測定である。")
        print("   zero-light 行は RNG divergence ではなく ON 側の系統差を測っている。")


if __name__ == "__main__":
    main()
