"""データ記録 (仕様書 Ver.1.1 §12)。

events.csv   : 出生・死亡・災害の全イベント (系統樹再構築可能)
stats.csv    : 一定間隔の集計統計 (全遺伝子の平均と分散を含む)
snapshots/   : 全個体スナップショット
config.json  : 全設定 + seed (完全再現の根拠)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from . import __version__
from .config import Config
from .genome import GENE_NAMES

DEATH_CAUSES = ["starvation", "damage", "predation", "disaster"]


class Recorder:
    def __init__(self, run_dir: str | Path, cfg: Config, seed: int):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "snapshots").mkdir(exist_ok=True)

        cfg.to_json(self.dir / "config.json")
        meta = {"seed": seed, "evosim_version": __version__}
        (self.dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        self._events_f = open(self.dir / "events.csv", "w", newline="", encoding="utf-8")
        self._events = csv.writer(self._events_f)
        self._events.writerow(
            ["tick", "event", "id", "parent_id", "lineage_id", "generation", "cause", "age"])

        self._stats_f = open(self.dir / "stats.csv", "w", newline="", encoding="utf-8")
        self._stats = csv.writer(self._stats_f)
        header = [
            "tick", "population", "births_cum", "deaths_cum",
            *[f"deaths_{c}" for c in DEATH_CAUSES],
            "corpse_count", "corpse_matter", "corpse_energy",
            "total_energy", "total_biomass", "nutrient_total", "chemical_total",
            "mean_age", "max_age", "max_generation", "n_lineages",
            *[f"mean_{n}" for n in GENE_NAMES],
            *[f"var_{n}" for n in GENE_NAMES],
        ]
        self._stats.writerow(header)

    # --- イベント ---

    def birth(self, tick: int, org) -> None:
        self._events.writerow(
            [tick, "birth", org.id, org.parent_id, org.lineage_id, org.generation, "", ""])

    def death(self, tick: int, org, cause: str) -> None:
        self._events.writerow(
            [tick, "death", org.id, "", org.lineage_id, "", cause, org.age])

    def disaster(self, tick: int, killed: int) -> None:
        self._events.writerow([tick, "disaster", "", "", "", "", f"killed={killed}", ""])

    # --- 統計 ---

    def stats(self, sim) -> None:
        orgs = sim.organisms
        n = len(orgs)
        if n > 0:
            genomes = np.stack([o.genome for o in orgs])
            gmean = genomes.mean(axis=0)
            gvar = genomes.var(axis=0)
            ages = np.array([o.age for o in orgs])
            mean_age, max_age = float(ages.mean()), int(ages.max())
            max_gen = max(o.generation for o in orgs)
            n_lin = len({o.lineage_id for o in orgs})
            tot_e = float(sum(o.energy for o in orgs))
            tot_m = float(sum(o.matter for o in orgs))
        else:
            gmean = gvar = np.full(len(GENE_NAMES), np.nan)
            mean_age = max_age = max_gen = n_lin = 0
            tot_e = tot_m = 0.0

        row = [
            sim.tick, n, sim.births_cum, sim.deaths_cum,
            *[sim.deaths_by_cause[c] for c in DEATH_CAUSES],
            len(sim.corpses),
            round(sum(c.matter for c in sim.corpses), 6),
            round(sum(c.energy for c in sim.corpses), 6),
            round(tot_e, 6), round(tot_m, 6),
            round(sim.world.total_nutrients(), 6),
            round(sim.world.total_chemical(), 6),
            round(mean_age, 2), max_age, max_gen, n_lin,
            *[round(float(v), 6) for v in gmean],
            *[round(float(v), 6) for v in gvar],
        ]
        self._stats.writerow(row)
        self._stats_f.flush()

    # --- スナップショット ---

    def snapshot(self, sim) -> None:
        path = self.dir / "snapshots" / f"snap_{sim.tick:08d}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "parent_id", "lineage_id", "generation", "age",
                        "x", "y", "energy", "matter", "damage", *GENE_NAMES])
            for o in sim.organisms:
                w.writerow([o.id, o.parent_id, o.lineage_id, o.generation, o.age,
                            round(o.x, 2), round(o.y, 2),
                            round(o.energy, 4), round(o.matter, 4), round(o.damage, 4),
                            *[round(float(g), 6) for g in o.genome]])

    def close(self) -> None:
        self._events_f.close()
        self._stats_f.close()
