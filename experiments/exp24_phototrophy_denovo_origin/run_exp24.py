"""Exp24 -- de novo Phototrophy recurrent-origin establishment assay
(docs/Exp24_実験計画.md, docs/Exp24_レビュー依頼.md)。

全個体Phototrophy OFFから開始し、structural innovation
(phototrophy_innovation_prob=0.01/birth, 100x default) を1920h全期間
維持する。独立したOFF->ON originごとに `photo_founder_id` を付与し
(evosim/organism.py, evosim/simulation.py)、各founder lineageの
+240/+480/+960h生存・頻度を追跡する。primary endpointは、前半960hに
生じたoriginについての `survive_960` (seed-level establishment rate)。

計算量対策 (docs §9.3, G14): 1920h runは単一Actions jobのtimeout内に
収まらないため、pickleベースのcheckpoint/resumeを実装する。Simulation
オブジェクト全体 (rng状態を含む) と本harnessのfounder追跡bookkeeping
をまとめてpickle化し、複数回のCLI呼び出し (同一job内の複数step、
またはjobをまたいだartifact受け渡し) で1920hを分割実行できる。
科学条件 (duration/seed/flux/innovation率) はcheckpoint分割によって
一切変更しない。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pickle
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
ENVIRONMENT = "A2_DYNAMIC_VENT"
_ENV_TO_CONDITION = {"A2_DYNAMIC_VENT": "A2"}

# docs §7: formal photon flux条件 (結果を見て追加・削除しない)。
FLUX_LEVELS_UMOL_M2_S = (0.0, 0.5, 1.5)

# docs §8: Exp24専用番号帯 (16 seeds)。結果を見て差し替えない。
SEEDS = tuple(range(24001, 24017))

# docs §4.1/§5: recurrent-origin acceleration + seed absorption (固定)。
PHOTOTROPH_INNOVATION_PROB = 0.01
PHOTOTROPH_LOSS_PROB = 0.0
PHOTOTROPH_SEED_ABSORPTION = 0.01

# docs §9.1/§9.2: formal duration / primary cohort window。
DURATION_H = 1920.0
PRIMARY_COHORT_CUTOFF_H = 960.0
PRIMARY_TRACK_WINDOW_H = 960.0

# founder population census cadence。1920h run全体でoutput sizeを抑えつつ
# +240/+480/+960h読み出しの丸め誤差を抑えるための実装上の選択
# (interpretive judgment call — docs は具体的cadenceを指定していない)。
# 12h刻みなら1920h runで160サンプル、founder読み出し誤差は最大12h。
CENSUS_INTERVAL_H = 12.0


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
    """docs §4/§6: A2_DYNAMIC_VENT固定、physical light ON uniform、
    phototrophy structural innovationのみON (0.01/birth)。continuous
    mutation/predation innovationはOFF。
    """
    if flux < 0.0:
        raise ValueError(f"negative flux rejected: {flux}")
    return exp18_core.make_flux_cfg(
        f0, evolve_genes=(), initial_jitter_sigma=0.0,
        physical_light_enabled=True,
        light_cycle_enabled=False,
        light_photon_flux_umol_m2_s=flux,
        phototrophy_innovation_prob=PHOTOTROPH_INNOVATION_PROB,
        phototrophy_loss_prob=PHOTOTROPH_LOSS_PROB,
        phototrophy_seed_absorption=PHOTOTROPH_SEED_ABSORPTION,
        dt_seconds=DT_SECONDS,
        **env_kwargs(ENVIRONMENT),
    )


def validate_effective_config(cfg, flux: float) -> None:
    """docs §13 G0/G5/G6: A2固定 / flux in {0,0.5,1.5} / continuous mutation
    OFF / innovation=0.01が維持される / loss=0 / uniform light。
    """
    expected = run_exp18.CONDITIONS[_ENV_TO_CONDITION[ENVIRONMENT]]
    assert cfg.physical_mode is True
    assert cfg.physical_light_enabled is True
    assert cfg.light_cycle_enabled is False
    assert cfg.light_physical_pattern == "uniform"
    assert flux in FLUX_LEVELS_UMOL_M2_S, f"flux {flux} not in preregistered set"
    assert cfg.light_photon_flux_umol_m2_s == flux
    assert cfg.phototrophy_innovation_prob == PHOTOTROPH_INNOVATION_PROB
    assert cfg.phototrophy_loss_prob == PHOTOTROPH_LOSS_PROB
    assert cfg.phototrophy_seed_absorption == PHOTOTROPH_SEED_ABSORPTION
    assert set(cfg.fixed_genes) == set(GENE_NAMES)  # continuous mutation OFF
    assert cfg.initial_jitter_sigma == 0.0
    assert cfg.initial_population == 100
    assert cfg.h2_source_mode == "flux"
    assert cfg.h2_vent_temporal_enabled is bool(expected["temporal"])
    assert cfg.h2_vent_turnover_enabled is bool(expected["turnover"])


def setup_all_off(cfg, seed: int, h2_field: np.ndarray):
    """docs §0/G0: 全個体Phototrophy OFFから開始する。exp18_core.setup_sim()
    がV1.9 baseline initial_capability()=OFFのままiLUCA daughter cellを
    生成するため、post-setupでの追加flipは不要 (Exp23の50:50 split等とは
    異なりExp24は「起源そのもの」を見るため、setup後にcapabilityを
    書き換えない)。
    """
    sim = exp18_core.setup_sim(cfg, seed, h2_field)
    for o in sim.organisms:
        assert o.phototrophy_on is False
        assert o.genome[LIGHT_ABS] == 0.0
        assert o.photo_founder_id is None
    return sim


def initial_fingerprint(sim) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(np.asarray(sim.world.h2, dtype=np.float64).tobytes())
    h.update(np.asarray(sim.world.dic, dtype=np.float64).tobytes())
    h.update(np.asarray(sim.world.fixed_nitrogen, dtype=np.float64).tobytes())
    h.update(np.asarray(sim.world.phosphate, dtype=np.float64).tobytes())
    for o in sorted(sim.organisms, key=lambda x: x.id):
        h.update(np.asarray([o.id, o.x, o.y, o.matter, o.energy, o.damage],
                            dtype=np.float64).tobytes())
        h.update(np.asarray(o.genome, dtype=np.float64).tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Founder tracking state (checkpoint-serializable, plain dict/list only)
# ---------------------------------------------------------------------------

def new_tracking_state(seed: int, flux: float) -> dict:
    return {
        "seed": seed,
        "flux": flux,
        "elapsed_h": 0.0,
        "known_ids": {},  # organism id -> photo_founder_id (as of last step)
        # founder_id -> record dict (see _register_founder)
        "founders": {},
        "census": [],  # list of {"time_h":..., "counts": {founder_id: N}, "total_pop": N}
        "next_census_h": 0.0,
        "total_births_cum": 0,
        "total_deaths_cum": 0,
        "degenerate_windows": [],  # G13 diagnostic flags
        "_prev_births_cum": 0,
        "_prev_deaths_cum": 0,
        "_window_start_h": 0.0,
        "_window_births": 0,
        "_window_deaths": 0,
    }


def _register_founder(state: dict, sim, org, t_h: float, pop_at_origin: int) -> None:
    fid = org.photo_founder_id
    state["founders"][fid] = {
        "photo_founder_id": fid,
        "organism_id": org.id,
        "parent_id": org.parent_id,
        "origin_time_h": t_h,
        "origin_tick": sim.tick,
        "origin_x": float(org.x),
        "origin_y": float(org.y),
        "origin_matter": float(org.matter),
        "origin_energy": float(org.energy),
        "origin_light_absorption": float(org.genome[LIGHT_ABS]),
        "population_at_origin": int(pop_at_origin),
        "vent_turnover_count_at_origin": int(getattr(sim.world, "vent_turnover_count_cum", 0)),
        "eligible_primary": bool(t_h <= PRIMARY_COHORT_CUTOFF_H + 1e-9),
        "extinction_time_h": None,
        "max_n": 1,
        "max_frequency": None,
        "first_n_ge_2_h": None,
        "first_n_ge_5_h": None,
        "first_n_ge_10_h": None,
        "first_freq_ge_1pct_h": None,
        "first_freq_ge_5pct_h": None,
        "N_240": None, "N_480": None, "N_960": None,
        "freq_240": None, "freq_480": None, "freq_960": None,
        "assembly_complete_time_h": None,  # G9: photo_structural_n_mol first >= seed target
    }


def _census_and_update(state: dict, sim, t_h: float) -> None:
    orgs = sim.organisms
    total_pop = len(orgs)
    counts: dict[int, int] = {}
    for o in orgs:
        fid = o.photo_founder_id
        if fid is not None:
            counts[fid] = counts.get(fid, 0) + 1
    state["census"].append({"time_h": t_h, "counts": dict(counts), "total_pop": total_pop})

    for fid, rec in state["founders"].items():
        n = counts.get(fid, 0)
        freq = (n / total_pop) if total_pop > 0 else 0.0
        if n > rec["max_n"]:
            rec["max_n"] = n
        if rec["max_frequency"] is None or freq > rec["max_frequency"]:
            rec["max_frequency"] = freq
        if n == 0 and rec["extinction_time_h"] is None:
            rec["extinction_time_h"] = t_h
        if n >= 2 and rec["first_n_ge_2_h"] is None:
            rec["first_n_ge_2_h"] = t_h
        if n >= 5 and rec["first_n_ge_5_h"] is None:
            rec["first_n_ge_5_h"] = t_h
        if n >= 10 and rec["first_n_ge_10_h"] is None:
            rec["first_n_ge_10_h"] = t_h
        if freq >= 0.01 and rec["first_freq_ge_1pct_h"] is None:
            rec["first_freq_ge_1pct_h"] = t_h
        if freq >= 0.05 and rec["first_freq_ge_5pct_h"] is None:
            rec["first_freq_ge_5pct_h"] = t_h
        # +240/+480/+960h readout: 最初にorigin_time+offset以上になった
        # census sampleの値を採用する (document: nearest-at-or-after,
        # CENSUS_INTERVAL_H刻みの丸め誤差を許容する)。
        origin_t = rec["origin_time_h"]
        for offset, key_n, key_f in ((240.0, "N_240", "freq_240"),
                                     (480.0, "N_480", "freq_480"),
                                     (960.0, "N_960", "freq_960")):
            if rec[key_n] is None and t_h >= origin_t + offset - 1e-9:
                rec[key_n] = n
                rec[key_f] = freq

    # G9 apparatus assembly completion: 個体がphoto_n_target_molへ到達した
    # (assembly完了) 最初のcensus時刻を、そのfounder系統の代表値として記録
    # する (系統内の最初に完了した個体を採用 — interpretive judgment call,
    # docs は集計方法を指定していない)。
    from evosim import physiology as _physio
    for o in orgs:
        fid = o.photo_founder_id
        if fid is None or fid not in state["founders"]:
            continue
        rec = state["founders"][fid]
        if rec["assembly_complete_time_h"] is not None:
            continue
        target = _physio.photo_n_target_mol(o, sim.cfg)
        if target <= 0.0 or o.photo_structural_n_mol >= target - 1e-15:
            rec["assembly_complete_time_h"] = t_h


def _degenerate_window_check(state: dict, sim, t_h: float, window_h: float = 24.0) -> None:
    """G13: Exp23 seed23008型 degenerate demography diagnostic。

    ヒューリスティック (interpretive judgment call, docs §13 G13):
    直近window_h時間で
      (a) births==deaths==0 (完全静止) または
      (b) births==deaths>0 かつ deaths_by_cause['starvation']変化が0
          (「死亡0で出生と死亡が完全対称」型の構造的固着)
    のいずれかが継続する場合にflagする。
    """
    if t_h - state["_window_start_h"] < window_h - 1e-9:
        return
    b = state["total_births_cum"] - state["_prev_births_cum"]
    d = state["total_deaths_cum"] - state["_prev_deaths_cum"]
    flagged = (b == 0 and d == 0) or (b == d and b > 0 and sim.deaths_by_cause.get("starvation", 0) == 0)
    if flagged:
        state["degenerate_windows"].append({
            "window_start_h": state["_window_start_h"], "window_end_h": t_h,
            "births": b, "deaths": d,
        })
    state["_prev_births_cum"] = state["total_births_cum"]
    state["_prev_deaths_cum"] = state["total_deaths_cum"]
    state["_window_start_h"] = t_h


def step_segment(sim, state: dict, target_elapsed_h: float) -> None:
    """target_elapsed_hまでsimを進め、founder origin検出・census・
    degenerate診断をstateへ書き込む (checkpoint分割の1segment分)。
    """
    cfg = sim.cfg
    if not state["known_ids"]:
        state["known_ids"] = {o.id: o.photo_founder_id for o in sim.organisms}
    target_steps = int(round(target_elapsed_h * 3600.0 / cfg.dt_seconds))
    current_step = int(round(state["elapsed_h"] * 3600.0 / cfg.dt_seconds))

    # t=0 (fresh run) 用の初期census
    if current_step == 0 and not state["census"]:
        _census_and_update(state, sim, 0.0)
        state["next_census_h"] = CENSUS_INTERVAL_H

    known_ids = state["known_ids"]
    while current_step < target_steps:
        if not sim.organisms:
            break
        births_before = sim.births_cum
        deaths_before = sim.deaths_cum
        sim.step()
        current_step += 1
        t_h = current_step * cfg.dt_seconds / 3600.0

        current_ids = {o.id: o.photo_founder_id for o in sim.organisms}
        new_ids = [oid for oid in current_ids if oid not in known_ids]
        for oid in new_ids:
            fid = current_ids[oid]
            if fid is not None and fid not in state["founders"]:
                org = next(o for o in sim.organisms if o.id == oid)
                _register_founder(state, sim, org, t_h, len(known_ids))
        died_ids = [oid for oid in known_ids if oid not in current_ids]
        known_ids = current_ids

        state["total_births_cum"] += sim.births_cum - births_before
        state["total_deaths_cum"] += sim.deaths_cum - deaths_before

        if t_h >= state["next_census_h"] - 1e-9:
            _census_and_update(state, sim, t_h)
            state["next_census_h"] += CENSUS_INTERVAL_H
        _degenerate_window_check(state, sim, t_h)

        if not sim.organisms:
            # 全滅: 最終censusを打つ
            _census_and_update(state, sim, t_h)
            break

    state["known_ids"] = known_ids
    state["elapsed_h"] = current_step * cfg.dt_seconds / 3600.0


def finalize_origins_table(state: dict) -> list[dict]:
    rows = []
    for fid in sorted(state["founders"]):
        rec = state["founders"][fid]
        survive_960 = None
        if rec["eligible_primary"]:
            n960 = rec["N_960"]
            survive_960 = int(n960 is not None and n960 > 0)
        row = dict(rec)
        row["survive_960"] = survive_960
        rows.append(row)
    return rows


def per_run_summary(state: dict, sim_final_pop: int) -> dict:
    origins = finalize_origins_table(state)
    eligible = [r for r in origins if r["eligible_primary"]]
    survived = [r for r in eligible if r["survive_960"] == 1]
    establishment_rate = (len(survived) / len(eligible)) if eligible else None
    return {
        "seed": state["seed"],
        "flux": state["flux"],
        "duration_h": state["elapsed_h"],
        "total_origins": len(origins),
        "eligible_origins": len(eligible),
        "survived_960_count": len(survived),
        "establishment_rate": establishment_rate,
        "final_population": sim_final_pop,
        "total_births_cum": state["total_births_cum"],
        "total_deaths_cum": state["total_deaths_cum"],
        "degenerate_windows": state["degenerate_windows"],
        "degenerate_flag": bool(state["degenerate_windows"]),
    }


# ---------------------------------------------------------------------------
# Checkpoint I/O
# ---------------------------------------------------------------------------

def save_checkpoint(path: Path, sim, state: dict, cfg_dict: dict) -> None:
    with path.open("wb") as f:
        pickle.dump({"sim": sim, "state": state, "cfg_dict": cfg_dict,
                    "duration_h": DURATION_H}, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_checkpoint(path: Path):
    with path.open("rb") as f:
        data = pickle.load(f)
    return data["sim"], data["state"], data["cfg_dict"]


def write_ledger_check(outdir: Path, sim) -> dict:
    """docs §13 G12: Energy/Matter/C/N/P closed-system checkはpreflightで
    別途行う (formal open runはbackground exchangeありなのでstrict
    conservationではない)。ここではopen-system residual (initial +
    external_in - external_out - current) を記録するだけに留める。
    """
    return {
        "energy_in_cum": float(sim.energy_in_cum),
        "energy_out_cum": float(sim.energy_out_cum),
        "system_energy_now": float(sim.system_energy()),
        "system_matter_now": float(sim.system_matter()),
        "photo_incident_j_cum": float(sim.photo_incident_j_cum),
        "photo_absorbed_j_cum": float(sim.photo_absorbed_j_cum),
        "photo_usable_max_j_cum": float(sim.photo_usable_max_j_cum),
        "photo_used_j_cum": float(sim.photo_used_j_cum),
        "legacy_light_flow_cum": float(sim.flows.get("light", 0.0)),
        "phototrophy_innovation_events": int(sim.phototrophy_innovation_events),
        "phototrophy_loss_events": int(sim.phototrophy_loss_events),
    }


def write_origins_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, choices=SEEDS, required=True)
    p.add_argument("--flux", type=float, choices=FLUX_LEVELS_UMOL_M2_S, required=True)
    p.add_argument("--hours", type=float, default=DURATION_H,
                   help="formal total duration target (do not shorten for runtime)")
    p.add_argument("--segment-hours", type=float, default=None,
                   help="how far to advance in this invocation; default = --hours (single-shot)")
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--checkpoint-in", type=Path, default=None)
    p.add_argument("--checkpoint-out", type=Path, default=None)
    args = p.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    f0, h2_field = load_calibration(args.calibration_dir)

    if args.checkpoint_in is not None and args.checkpoint_in.exists():
        sim, state, cfg_dict = load_checkpoint(args.checkpoint_in)
        cfg = sim.cfg
    else:
        cfg = make_cfg(f0, args.flux)
        validate_effective_config(cfg, args.flux)
        cfg_dict = dataclasses.asdict(cfg)
        (args.outdir / "effective_config.json").write_text(
            json.dumps(cfg_dict, indent=2), encoding="utf-8")
        sim = setup_all_off(cfg, args.seed, h2_field)
        (args.outdir / "initial_genome.json").write_text(json.dumps({
            "gene_names": GENE_NAMES,
            "genome_off": [float(v) for v in sim.organisms[0].genome],
            "fixed_genes": list(cfg.fixed_genes),
        }, indent=2), encoding="utf-8")
        n_total = len(sim.organisms)
        n_on = sum(1 for o in sim.organisms if o.phototrophy_on)
        if not (n_total == 100 and n_on == 0):
            raise RuntimeError(f"G0 violated: n_total={n_total}, n_on={n_on} (expected 100/0)")
        state = new_tracking_state(args.seed, args.flux)

    target_h = min(args.hours, state["elapsed_h"] + (args.segment_hours or args.hours))
    step_segment(sim, state, target_h)

    done = state["elapsed_h"] >= args.hours - 1e-6 or not sim.organisms

    if args.checkpoint_out is not None:
        save_checkpoint(args.checkpoint_out, sim, state, cfg_dict)

    if not done:
        print(json.dumps({"segment_done_h": state["elapsed_h"], "target_h": args.hours,
                          "checkpoint": str(args.checkpoint_out), "finished": False}, indent=2))
        return

    origins = finalize_origins_table(state)
    write_origins_csv(args.outdir / "exp24_origins.csv", origins)
    summary = per_run_summary(state, len(sim.organisms))
    summary["ledger"] = write_ledger_check(args.outdir, sim)
    out = {
        "experiment": "Exp24 phototrophy de novo recurrent-origin establishment assay",
        "environment": ENVIRONMENT,
        "seed": args.seed,
        "flux": args.flux,
        "duration_h": args.hours,
        "duration_target_h": DURATION_H,
        "primary_cohort_cutoff_h": PRIMARY_COHORT_CUTOFF_H,
        "primary_track_window_h": PRIMARY_TRACK_WINDOW_H,
        "f0_mol_s_per_vent": f0,
        "innovation_prob_per_birth": PHOTOTROPH_INNOVATION_PROB,
        "innovation_acceleration_note": (
            "phototrophy_innovation_prob=0.01/birth is a 100x experimental "
            "acceleration over the codebase default (1e-4/birth); it does not "
            "represent a real-world innovation rate (docs/Exp24_実験計画.md §4.1)."),
        "loss_prob_per_birth": PHOTOTROPH_LOSS_PROB,
        "summary": summary,
    }
    (args.outdir / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "summary"} | {
        "total_origins": summary["total_origins"],
        "eligible_origins": summary["eligible_origins"],
        "survived_960_count": summary["survived_960_count"],
        "establishment_rate": summary["establishment_rate"],
        "finished": True,
    }, indent=2))


if __name__ == "__main__":
    main()
