"""Exp22 — V1.11 primitive phototrophy photon-flux calibration
(docs/Exp22_実験計画.md)。

Stage-1 paired fitness-effect assay: 同一environment/seed/photon fluxで
phototrophy capability OFF/ONの2 runを行い (どちらも同じphysical photon
fluxを設定する。docs §8)、stored Energy protection / starvation exposure
のcontinuous effectを直接測る。competition/evolutionは扱わない
(Exp23候補)。

Exp18/Exp20 Attempt2のharnessを最大限再利用する。
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXP18_DIR = ROOT / "experiments" / "exp18_v1101_dynamic_vent"
for p in (ROOT, EXP18_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import exp18_core  # noqa: E402
import run_exp18  # noqa: E402
from evosim.genome import GENE_NAMES, LIGHT_ABS  # noqa: E402

DT_SECONDS = 10.0
DURATION_H = 72.0  # docs §7: 0-48h (turnover前) + 48-72h (turnover後)
SAMPLE_EVERY_S = 600.0
ENVIRONMENTS = ("A0_STATIC", "A2_DYNAMIC_VENT")
_ENV_TO_CONDITION = {"A0_STATIC": "A0", "A2_DYNAMIC_VENT": "A2"}

# docs §6: 事前固定するflux水準 (結果を見て追加・削除しない)。
# 0.0は"negative control + structural cost only" (config.pyの
# light_photon_flux_umol_m2_s>=0緩和により physical_light_enabled=True
# のまま表現できる。structural N assemblyコストは維持しつつ光income=0)。
FLUX_LEVELS_UMOL_M2_S = (0.0, 0.015, 0.05, 0.15, 0.5, 1.5)

# docs §9: Exp22専用番号帯。結果を見て差し替えない。
SEEDS = (22001, 22002, 22003)

# docs §5: V1.11 rev2 primitive phenotype (固定)。
PHOTOTROPH_LIGHT_ABSORPTION = 0.01

CAPABILITY_STATES = ("OFF", "ON")


def load_calibration(calibration_dir: Path) -> tuple[float, np.ndarray]:
    f0_data = json.loads((calibration_dir / "f0_calibration.json").read_text(encoding="utf-8"))
    h2_field = np.load(calibration_dir / "common_initial_h2_field.npy")
    return float(f0_data["f0_mol_s"]), h2_field


def env_kwargs(environment: str) -> dict:
    condition = _ENV_TO_CONDITION[environment]
    kw = dict(run_exp18.CONDITIONS[condition])
    if kw["turnover"]:
        kw = {**kw, **run_exp18.TURNOVER_KW}
    return kw


def make_cfg(f0: float, environment: str, flux: float):
    """docs §3 G2 / §4 / §6: physical light ON、24h一定uniform flux、
    innovation/mutation全OFF。OFF/ON runとも同じcfg (physical photon flux
    は同一) を使い、capabilityの有無だけをsetup後に分ける (docs §8)。
    """
    return exp18_core.make_flux_cfg(
        f0, evolve_genes=(), initial_jitter_sigma=0.0,
        physical_light_enabled=True,
        light_cycle_enabled=False,
        light_photon_flux_umol_m2_s=flux,
        phototrophy_innovation_prob=0.0,
        phototrophy_loss_prob=0.0,
        dt_seconds=DT_SECONDS,
        **env_kwargs(environment),
    )


def validate_effective_config(cfg, environment: str, flux: float) -> None:
    """docs §3 G2: effective configをfield単位で条件表と比較。"""
    cond = _ENV_TO_CONDITION[environment]
    expected = run_exp18.CONDITIONS[cond]
    assert cfg.physical_mode is True
    assert cfg.physical_light_enabled is True
    assert cfg.light_cycle_enabled is False
    assert cfg.light_physical_pattern == "uniform"
    assert cfg.light_photon_flux_umol_m2_s == flux
    assert cfg.light_effective_wavelength_nm == 800.0
    assert cfg.phototrophy_radiant_to_usable_eff == 0.10
    assert cfg.photo_apparatus_n_multiplier == 10.0
    assert cfg.bchl_extinction_mM_cm == 213.0
    assert cfg.phototrophy_innovation_prob == 0.0
    assert cfg.phototrophy_loss_prob == 0.0
    assert set(cfg.fixed_genes) == set(GENE_NAMES)  # continuous mutation OFF
    assert cfg.initial_jitter_sigma == 0.0
    assert cfg.initial_population == 100
    assert cfg.h2_source_mode == "flux"
    assert cfg.h2_vent_temporal_enabled is bool(expected["temporal"])
    assert cfg.h2_vent_turnover_enabled is bool(expected["turnover"])


def setup_paired(cfg, seed: int, h2_field: np.ndarray, capability_on: bool):
    """docs §5/§8: ONはcapability=True, light_absorption=0.01を明示的に
    設定するだけで、他は共通のexp18_core.setup_sim()に完全に委ねる
    (追加RNG消費なし。docs §3 G5)。photo_structural_n_molは両者0から開始。
    """
    sim = exp18_core.setup_sim(cfg, seed, h2_field)
    if capability_on:
        for o in sim.organisms:
            o.phototrophy_on = True
            o.genome = o.genome.copy()
            o.genome[LIGHT_ABS] = PHOTOTROPH_LIGHT_ABSORPTION
        # E_max/runwayに依存する初期energyはsetup_sim内で既に確定済みだが、
        # LIGHT_ABSはE_max計算に影響しない (STORAGE_CAPのみ影響) ので
        # 変更後も absolute stored Energy は不変 (docs G5)。
    return sim


def initial_fingerprint(sim) -> str:
    """docs §3 G5: capability/light_absorption以外の初期状態一致確認用。"""
    h = hashlib.sha256()
    h.update(np.asarray(sim.world.h2, dtype=np.float64).tobytes())
    h.update(np.asarray(sim.world.dic, dtype=np.float64).tobytes())
    h.update(np.asarray(sim.world.fixed_nitrogen, dtype=np.float64).tobytes())
    h.update(np.asarray(sim.world.phosphate, dtype=np.float64).tobytes())
    for o in sorted(sim.organisms, key=lambda x: x.id):
        h.update(np.asarray([o.id, o.x, o.y, o.matter, o.energy, o.damage],
                            dtype=np.float64).tobytes())
        g = np.asarray(o.genome, dtype=np.float64).copy()
        g[LIGHT_ABS] = 0.0  # capabilityで意図的に変える唯一のgeneをmask
        h.update(g.tobytes())
    return h.hexdigest()


def snapshot(sim, t_s: float) -> dict:
    orgs = sim.organisms
    n = len(orgs)
    row = {
        "time_s": t_s, "time_h": t_s / 3600.0,
        "population": n,
        "births_cum": int(sim.births_cum), "deaths_cum": int(sim.deaths_cum),
        "starvation_deaths_cum": int(sim.deaths_by_cause.get("starvation", 0)),
        "h2_biological_uptake_cum_mol": float(sim.h2_biological_uptake_mol_cum),
        "vent_turnover_count_cum": int(sim.world.vent_turnover_count_cum),
        "photo_incident_j_cum": float(sim.photo_incident_j_cum),
        "photo_absorbed_j_cum": float(sim.photo_absorbed_j_cum),
        "photo_usable_max_j_cum": float(sim.photo_usable_max_j_cum),
        "photo_used_j_cum": float(sim.photo_used_j_cum),
        "photo_unused_j_cum": float(sim.photo_unused_j_cum),
        "photo_conversion_loss_j_cum": float(sim.photo_conversion_loss_j_cum),
        "photo_n_assembly_cum": float(sim.photo_n_assembly_cum),
        "photo_n_released_cum": float(sim.photo_n_released_cum),
        "legacy_light_flow_cum": float(sim.flows.get("light", 0.0)),
    }
    if n:
        row["total_living_matter"] = float(sum(o.matter for o in orgs))
        row["mean_matter"] = float(np.mean([o.matter for o in orgs]))
        row["mean_stored_energy_j"] = float(np.mean([o.energy for o in orgs]))
        row["mean_starve_state"] = float(np.mean([o.starve_state for o in orgs]))
        row["starvation_exposed_fraction"] = float(np.mean([o.starve_state < 0.99 for o in orgs]))
        row["photo_structural_n_mol_total"] = float(sum(o.photo_structural_n_mol for o in orgs))
        row["photo_structural_n_mol_mean"] = float(np.mean([o.photo_structural_n_mol for o in orgs]))
    else:
        row.update({
            "total_living_matter": 0.0, "mean_matter": None, "mean_stored_energy_j": None,
            "mean_starve_state": None, "starvation_exposed_fraction": None,
            "photo_structural_n_mol_total": 0.0, "photo_structural_n_mol_mean": None,
        })
    return row


def run_one(cfg, seed: int, h2_field: np.ndarray, hours: float, capability_on: bool) -> tuple[list[dict], dict, str]:
    sim = setup_paired(cfg, seed, h2_field, capability_on)
    fp = initial_fingerprint(sim)
    steps = int(round(hours * 3600.0 / cfg.dt_seconds))
    every = max(1, int(round(SAMPLE_EVERY_S / cfg.dt_seconds)))
    rows = [snapshot(sim, 0.0)]
    extinction_time_h = None
    first_birth_time_h = None

    for step in range(1, steps + 1):
        before_births = sim.births_cum
        sim.step()
        t_s = step * cfg.dt_seconds
        if first_birth_time_h is None and sim.births_cum > before_births:
            first_birth_time_h = t_s / 3600.0
        if step % every == 0:
            rows.append(snapshot(sim, t_s))
        if not sim.organisms:
            extinction_time_h = t_s / 3600.0
            if rows[-1]["time_s"] != t_s:
                rows.append(snapshot(sim, t_s))
            break
        if len(sim.organisms) >= cfg.max_population_halt:
            if rows[-1]["time_s"] != t_s:
                rows.append(snapshot(sim, t_s))
            break

    # G1: physical upper-bound identity + legacy light contamination check
    for r in rows:
        assert r["photo_used_j_cum"] <= r["photo_usable_max_j_cum"] + 1e-9 * max(abs(r["photo_usable_max_j_cum"]), 1e-300)
        assert r["photo_usable_max_j_cum"] <= r["photo_absorbed_j_cum"] + 1e-9 * max(abs(r["photo_absorbed_j_cum"]), 1e-300)
        assert r["photo_absorbed_j_cum"] <= r["photo_incident_j_cum"] + 1e-9 * max(abs(r["photo_incident_j_cum"]), 1e-300)
        assert r["legacy_light_flow_cum"] == 0.0, "legacy light contamination (G0)"
        assert r["photo_used_j_cum"] >= 0.0

    summary = {
        "final": rows[-1],
        "extinction_time_h": extinction_time_h,
        "first_birth_time_h": first_birth_time_h,
        "duration_completed_h": rows[-1]["time_h"],
    }
    return rows, summary, fp


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--environment", choices=ENVIRONMENTS, required=True)
    p.add_argument("--seed", type=int, choices=SEEDS, required=True)
    p.add_argument("--hours", type=float, default=DURATION_H)
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    f0, h2_field = load_calibration(args.calibration_dir)

    manifest = []
    for flux in FLUX_LEVELS_UMOL_M2_S:
        cfg = make_cfg(f0, args.environment, flux)
        validate_effective_config(cfg, args.environment, flux)
        label = f"flux{flux:g}"
        flux_dir = args.outdir / label
        flux_dir.mkdir(parents=True, exist_ok=True)
        (flux_dir / "effective_config.json").write_text(
            json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")

        # G5: OFF/ONの初期状態がcapability/light_absorption以外で一致すること
        off_check = setup_paired(cfg, args.seed, h2_field, capability_on=False)
        on_check = setup_paired(cfg, args.seed, h2_field, capability_on=True)
        fp_off, fp_on = initial_fingerprint(off_check), initial_fingerprint(on_check)
        if fp_off != fp_on:
            raise RuntimeError(f"G5 violated for flux={flux}: OFF/ON initial state differs beyond trait")

        off_rows, off_summary, _ = run_one(cfg, args.seed, h2_field, args.hours, capability_on=False)
        on_rows, on_summary, _ = run_one(cfg, args.seed, h2_field, args.hours, capability_on=True)
        write_csv(flux_dir / "off.csv", off_rows)
        write_csv(flux_dir / "on.csv", on_rows)
        (flux_dir / "pair_summary.json").write_text(json.dumps({
            "environment": args.environment, "seed": args.seed, "flux": flux,
            "initial_state_match_except_trait": True,
            "off_summary": off_summary, "on_summary": on_summary,
        }, indent=2), encoding="utf-8")
        manifest.append({"flux": flux, "label": label})

    (args.outdir / "manifest.json").write_text(json.dumps({
        "environment": args.environment, "seed": args.seed,
        "flux_levels": list(FLUX_LEVELS_UMOL_M2_S), "duration_h": args.hours,
        "f0_mol_s_per_vent": f0,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"environment": args.environment, "seed": args.seed,
                      "n_flux_levels": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
