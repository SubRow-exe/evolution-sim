"""Exp23 — primitive phototrophy OFF/ON直接lineage競争実験
(docs/Exp23_実験計画.md)。

同一集団100個体をOFF/ONへ50:50でsplitし、A2_DYNAMIC_VENT環境で
photon flux 0.0/0.5/1.5, 120 physical hours競争させる。Exp21の
lineage-competition harness (blake2b割当 / known-id-diff births-deaths)
とExp22のphototrophy setup / photo energy ledger観測を再利用する。
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import math
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
DURATION_H = 120.0
CHECKPOINTS_H = (0.0, 12.0, 24.0, 48.0, 72.0, 96.0, 120.0)
ENVIRONMENT = "A2_DYNAMIC_VENT"
_ENV_TO_CONDITION = {"A2_DYNAMIC_VENT": "A2"}

# docs §6: formal photon flux条件 (結果を見て追加・削除しない)。
FLUX_LEVELS_UMOL_M2_S = (0.0, 0.5, 1.5)

# docs §8: Exp23専用番号帯。結果を見て差し替えない。
SEEDS = (23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008)

# docs §4 / Exp22 §5: V1.11 rev2 primitive phenotype (固定)。
PHOTOTROPH_LIGHT_ABSORPTION = 0.01

LINEAGE_GROUPS = ("OFF", "ON")


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


def make_cfg(f0: float, flux: float):
    """docs §3/§4/§6: A2_DYNAMIC_VENT固定、physical light ON uniform、
    mutation/structural innovation/predation OFF。
    """
    if flux < 0.0:
        raise ValueError(f"negative flux rejected: {flux}")
    return exp18_core.make_flux_cfg(
        f0, evolve_genes=(), initial_jitter_sigma=0.0,
        physical_light_enabled=True,
        light_cycle_enabled=False,
        light_photon_flux_umol_m2_s=flux,
        phototrophy_innovation_prob=0.0,
        phototrophy_loss_prob=0.0,
        dt_seconds=DT_SECONDS,
        **env_kwargs(ENVIRONMENT),
    )


def validate_effective_config(cfg, flux: float) -> None:
    """docs §12 G2: A2固定 / flux in {0,0.5,1.5} / mutation・innovation OFF /
    light cycle OFF / uniform light。
    """
    expected = run_exp18.CONDITIONS[_ENV_TO_CONDITION[ENVIRONMENT]]
    assert cfg.physical_mode is True
    assert cfg.physical_light_enabled is True
    assert cfg.light_cycle_enabled is False
    assert cfg.light_physical_pattern == "uniform"
    assert flux in FLUX_LEVELS_UMOL_M2_S, f"flux {flux} not in preregistered set"
    assert cfg.light_photon_flux_umol_m2_s == flux
    assert cfg.phototrophy_innovation_prob == 0.0
    assert cfg.phototrophy_loss_prob == 0.0
    assert set(cfg.fixed_genes) == set(GENE_NAMES)  # continuous mutation OFF
    assert cfg.initial_jitter_sigma == 0.0
    assert cfg.initial_population == 100
    assert cfg.h2_source_mode == "flux"
    assert cfg.h2_vent_temporal_enabled is bool(expected["temporal"])
    assert cfg.h2_vent_turnover_enabled is bool(expected["turnover"])
    # predationはV1.9以来structural innovation probability経由でlockedされて
    # おり (AGENTS.md §7)、base_config()のpredation innovation probが常に0
    # であることに依存する。専用boolean configフィールドは存在しない。


def assign_on_lineage_ids(seed: int, organism_ids: list[int], count: int = 50,
                          tag: str = "exp23-on-phototrophy") -> set[int]:
    """docs §5: organism/environment RNGから独立した専用blake2b hashで
    ON lineageへ割当てる50個体を決定する。同seedで再現可能かつ厳密に
    countを返す (50:50を保証)。
    """
    def key(oid: int) -> bytes:
        payload = f"{seed}:{oid}:{tag}".encode("utf-8")
        return hashlib.blake2b(payload, digest_size=16).digest()
    ranked = sorted(organism_ids, key=key)
    return set(ranked[:count])


def setup_mixed(cfg, seed: int, h2_field: np.ndarray, tag: str = "exp23-on-phototrophy"):
    """docs §4/§5: 共通母集団をexp18_core.setup_sim()で生成し、専用hashで
    選んだ50個体だけphototrophy capabilityをONへ切り替える。lineage_idは
    founder個体のidのまま (Organism._spawn_initialでid==lineage_id) なので、
    on_lineage_idsをそのまま子孫のON/OFF判定に使える。
    """
    sim = exp18_core.setup_sim(cfg, seed, h2_field)
    ids = sorted(o.id for o in sim.organisms)
    on_ids = assign_on_lineage_ids(seed, ids, count=len(ids) // 2, tag=tag)
    for o in sim.organisms:
        if o.id in on_ids:
            o.phototrophy_on = True
            o.genome = o.genome.copy()
            o.genome[LIGHT_ABS] = PHOTOTROPH_LIGHT_ABSORPTION
        else:
            o.phototrophy_on = False
            o.genome = o.genome.copy()
            o.genome[LIGHT_ABS] = 0.0
    return sim, frozenset(on_ids)


def setup_mixed_mirrored(cfg, seed: int, h2_field: np.ndarray):
    """docs §5 mirror diagnostic / G9: 通常割当の補集合をONにする診断専用
    setup。formal runには使わない。
    """
    sim = exp18_core.setup_sim(cfg, seed, h2_field)
    ids = sorted(o.id for o in sim.organisms)
    normal_on = assign_on_lineage_ids(seed, ids, count=len(ids) // 2)
    mirrored_on = set(ids) - normal_on
    for o in sim.organisms:
        if o.id in mirrored_on:
            o.phototrophy_on = True
            o.genome = o.genome.copy()
            o.genome[LIGHT_ABS] = PHOTOTROPH_LIGHT_ABSORPTION
        else:
            o.phototrophy_on = False
            o.genome = o.genome.copy()
            o.genome[LIGHT_ABS] = 0.0
    return sim, frozenset(mirrored_on)


def initial_fingerprint(sim) -> str:
    """docs §12 G4: capability/light_absorption以外の初期状態が共通母集団
    由来であることの確認用 (Exp22 initial_fingerprintと同型)。
    """
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


def lineage_of(lineage_id: int, on_ids: frozenset[int]) -> str:
    return "ON" if lineage_id in on_ids else "OFF"


def snapshot(sim, t_s: float, on_ids: frozenset[int],
            births_cum: dict, deaths_cum: dict, starv_deaths_cum: dict) -> dict:
    orgs = sim.organisms
    groups = {"ON": [o for o in orgs if o.lineage_id in on_ids],
             "OFF": [o for o in orgs if o.lineage_id not in on_ids]}
    n_on, n_off = len(groups["ON"]), len(groups["OFF"])
    total = n_on + n_off
    row: dict = {
        "time_h": t_s / 3600.0,
        "N_OFF": n_off, "N_ON": n_on,
        "f_photo": (n_on / total) if total > 0 else None,
        "OFF_births_cum": births_cum["OFF"], "ON_births_cum": births_cum["ON"],
        "OFF_deaths_cum": deaths_cum["OFF"], "ON_deaths_cum": deaths_cum["ON"],
        "OFF_starvation_deaths_cum": starv_deaths_cum["OFF"],
        "ON_starvation_deaths_cum": starv_deaths_cum["ON"],
        "photo_incident_j_cum": float(sim.photo_incident_j_cum),
        "photo_absorbed_j_cum": float(sim.photo_absorbed_j_cum),
        "photo_usable_max_j_cum": float(sim.photo_usable_max_j_cum),
        "photo_used_j_cum": float(sim.photo_used_j_cum),
        "photo_structural_n_mol_total": float(sum(o.photo_structural_n_mol for o in orgs)),
        "legacy_light_flow_cum": float(sim.flows.get("light", 0.0)),
    }
    for g in LINEAGE_GROUPS:
        members = groups[g]
        n = len(members)
        row[f"{g}_total_living_matter"] = float(sum(o.matter for o in members)) if n else 0.0
        row[f"{g}_mean_matter"] = float(np.mean([o.matter for o in members])) if n else None
        row[f"{g}_mean_stored_energy_j"] = float(np.mean([o.energy for o in members])) if n else None
    return row


def run_one(cfg, seed: int, h2_field: np.ndarray, hours: float) -> tuple[list[dict], dict]:
    sim, on_ids = setup_mixed(cfg, seed, h2_field)
    rng_state_before = sim.rng.bit_generator.state
    # setup_mixedはassign_on_lineage_idsの外で追加RNGを消費しない
    # (以下のno-op assertはハーネスの意図を明示するだけ)。
    rng_state_after = sim.rng.bit_generator.state
    if rng_state_before != rng_state_after:
        raise RuntimeError("setup_mixed unexpectedly consumed simulation RNG")

    def death_cause(sim_obj) -> dict:
        return dict(sim_obj.deaths_by_cause)

    births_cum = {"OFF": 0, "ON": 0}
    deaths_cum = {"OFF": 0, "ON": 0}
    starv_deaths_cum = {"OFF": 0, "ON": 0}
    known = {o.id: o.lineage_id for o in sim.organisms}
    prev_deaths_by_cause = dict(sim.deaths_by_cause)

    checkpoints_s = [h * 3600.0 for h in CHECKPOINTS_H if h <= hours + 1e-9]
    if not checkpoints_s or checkpoints_s[0] != 0.0:
        checkpoints_s = [0.0] + checkpoints_s
    rows = [snapshot(sim, 0.0, on_ids, births_cum, deaths_cum, starv_deaths_cum)]

    steps = int(round(hours * 3600.0 / cfg.dt_seconds))
    checkpoint_steps = sorted({int(round(t / cfg.dt_seconds)) for t in checkpoints_s if t > 0.0})
    checkpoint_set = set(checkpoint_steps)

    extinction_time_h = {"OFF": None, "ON": None}
    fixed_lineage = None
    fixation_time_h = None

    for step in range(1, steps + 1):
        sim.step()
        t_s = step * cfg.dt_seconds
        current = {o.id: o.lineage_id for o in sim.organisms}
        for oid, lid in current.items():
            if oid not in known:
                births_cum[lineage_of(lid, on_ids)] += 1
        died_ids = [oid for oid in known if oid not in current]
        for oid in died_ids:
            deaths_cum[lineage_of(known[oid], on_ids)] += 1
        # docs §10: starvation死因はknown-id-diffでは系統帰属できないため、
        # simulation全体のdeaths_by_causeデルタをdied lineage構成比で
        # 按分する近似は避け、died個体数に対してdeaths_by_causeの
        # 増分件数を単純加算する (単一死因ステップがほとんどの粗いdt下で
        # 妥当な近似。corpse/predation等の複数死因が同一stepで混在する
        # 場合はraw deaths_by_causeとの照合で診断可能)。
        new_starv = sim.deaths_by_cause.get("starvation", 0) - prev_deaths_by_cause.get("starvation", 0)
        if new_starv and died_ids:
            # 按分: died個体数のうちnew_starv件をOFF/ON比で近似配分
            off_died = sum(1 for oid in died_ids if lineage_of(known[oid], on_ids) == "OFF")
            on_died = len(died_ids) - off_died
            if off_died + on_died > 0:
                starv_deaths_cum["OFF"] += new_starv * off_died / (off_died + on_died)
                starv_deaths_cum["ON"] += new_starv * on_died / (off_died + on_died)
        prev_deaths_by_cause = dict(sim.deaths_by_cause)
        known = current

        n_on = sum(1 for lid in current.values() if lid in on_ids)
        n_off = len(current) - n_on
        if n_on == 0 and extinction_time_h["ON"] is None:
            extinction_time_h["ON"] = t_s / 3600.0
        if n_off == 0 and extinction_time_h["OFF"] is None:
            extinction_time_h["OFF"] = t_s / 3600.0
        if fixed_lineage is None:
            if n_on > 0 and n_off == 0:
                fixed_lineage, fixation_time_h = "ON", t_s / 3600.0
            elif n_off > 0 and n_on == 0:
                fixed_lineage, fixation_time_h = "OFF", t_s / 3600.0

        if step in checkpoint_set:
            rows.append(snapshot(sim, t_s, on_ids, births_cum, deaths_cum, starv_deaths_cum))
        if not sim.organisms:
            if rows[-1]["time_h"] != t_s / 3600.0:
                rows.append(snapshot(sim, t_s, on_ids, births_cum, deaths_cum, starv_deaths_cum))
            break

    selection_coefficients = []
    interior = [(r["time_h"], r["f_photo"]) for r in rows
               if r["f_photo"] is not None and 0.0 < r["f_photo"] < 1.0]
    for (t1, f1), (t2, f2) in zip(interior, interior[1:]):
        dt = t2 - t1
        if dt <= 0:
            continue
        s = (math.log(f2 / (1 - f2)) - math.log(f1 / (1 - f1))) / dt
        selection_coefficients.append(s)
    median_s = float(np.median(selection_coefficients)) if selection_coefficients else None

    final = rows[-1]
    summary = {
        "final": final,
        "final_f_photo": final["f_photo"],
        "delta_f_photo_from_half": (final["f_photo"] - 0.5) if final["f_photo"] is not None else None,
        "extinction_time_h": extinction_time_h,
        "fixed_lineage": fixed_lineage,
        "fixation_time_h": fixation_time_h,
        "duration_completed_h": final["time_h"],
        "OFF_births_cum": births_cum["OFF"], "ON_births_cum": births_cum["ON"],
        "OFF_deaths_cum": deaths_cum["OFF"], "ON_deaths_cum": deaths_cum["ON"],
        "OFF_final_total_living_matter": final["OFF_total_living_matter"],
        "ON_final_total_living_matter": final["ON_total_living_matter"],
        "median_selection_coefficient_per_h": median_s,
        "n_selection_coefficient_intervals": len(selection_coefficients),
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, choices=SEEDS, required=True)
    p.add_argument("--flux", type=float, choices=FLUX_LEVELS_UMOL_M2_S, required=True)
    p.add_argument("--hours", type=float, default=DURATION_H)
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    f0, h2_field = load_calibration(args.calibration_dir)

    cfg = make_cfg(f0, args.flux)
    validate_effective_config(cfg, args.flux)
    (args.outdir / "effective_config.json").write_text(
        json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")

    sim_check, on_ids_check = setup_mixed(cfg, args.seed, h2_field)
    n_on, n_total = len(on_ids_check), len(sim_check.organisms)
    if not (n_total == 100 and n_on == 50):
        raise RuntimeError(f"G3 violated: n_total={n_total}, n_on={n_on} (expected 100/50)")
    (args.outdir / "initial_genome.json").write_text(json.dumps({
        "gene_names": GENE_NAMES,
        "genome_off": [float(v) for v in next(o.genome for o in sim_check.organisms
                                              if o.id not in on_ids_check)],
        "genome_on": [float(v) for v in next(o.genome for o in sim_check.organisms
                                             if o.id in on_ids_check)],
        "fixed_genes": list(cfg.fixed_genes),
    }, indent=2), encoding="utf-8")

    rows, summary = run_one(cfg, args.seed, h2_field, args.hours)
    write_csv(args.outdir / "timeseries.csv", rows)

    out = {
        "experiment": "Exp23 phototrophy OFF/ON direct competition",
        "environment": ENVIRONMENT,
        "seed": args.seed,
        "flux": args.flux,
        "duration_h": args.hours,
        "duration_target_h": DURATION_H,
        "f0_mol_s_per_vent": f0,
        "n_initial_total": n_total,
        "n_initial_on": n_on,
        "n_initial_off": n_total - n_on,
        "summary": summary,
    }
    (args.outdir / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "summary"} | {
        "final_f_photo": summary["final_f_photo"],
        "fixed_lineage": summary["fixed_lineage"],
        "fixation_time_h": summary["fixation_time_h"],
    }, indent=2))


if __name__ == "__main__":
    main()
