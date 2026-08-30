"""データ記録 (仕様書 Ver.1.1 §12)。

events.csv       : 出生・死亡・災害の全イベント (系統樹再構築可能)
stats.csv        : 一定間隔の集計統計 (全遺伝子の平均と分散・資源フロー累積を含む)
lineages.csv     : 系統別統計 (stats間隔ごとの上位系統の人口・出生数・代表遺伝子)
performance.csv  : 計算性能ログ (tick時間・人口・処理速度)
snapshots/       : 全個体スナップショット
config.json      : 全設定
meta.json        : seed / git SHA / 数値実行環境 (再現条件の特定に必須)

再現には seed と Config だけでは足りない。結果は数値実行環境に依存するため
(math.sin/cos/atan2/hypot と pow がOS側の数学ライブラリ実装に依存)、
meta.json に環境を記録して比較実験群の同一性を後から確認できるようにする。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from . import __version__
from .config import Config
from .genome import BODY_SIZE, GENE_NAMES, LIGHT_ABS, MUTATION_RATE, REPRO_INVEST
from .runmeta import run_metadata
from .spatial import (BAND_NAMES, lineage_spatial, population_spatial,
                      save_environment_snapshot, save_static_environment)

TOP_LINEAGES = 8  # lineages.csv に記録する上位系統数

DEATH_CAUSES = ["starvation", "damage", "predation", "disaster"]


class Recorder:
    def __init__(self, run_dir: str | Path, cfg: Config, seed: int):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "snapshots").mkdir(exist_ok=True)
        (self.dir / "environment").mkdir(exist_ok=True)
        self._static_saved = False

        cfg.to_json(self.dir / "config.json")
        meta = run_metadata(seed, __version__)
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
            # 資源利用率 (累積値。区間レートは差分で求める)
            "light_supply_cum", "flow_light_cum", "flow_chemical_cum",
            "flow_nutrient_cum", "flow_corpse_matter_cum", "flow_corpse_energy_cum",
            "flow_predation_energy_cum", "flow_predation_matter_cum",
            # 系統支配度
            "top_lineage_id", "top_lineage_frac",
            # 空間指標 (V1.2.1)。地理帯は Control/Treatment 共通の固定定義
            *[f"pop_{b}_band" for b in BAND_NAMES],
            *[f"frac_{b}_band" for b in BAND_NAMES],
            "mean_local_light", "vent_cell_population", "vent_cell_frac",
            "mean_move_per_org_tick",
            *[f"mean_{n}" for n in GENE_NAMES],
            *[f"var_{n}" for n in GENE_NAMES],
        ]
        self._stats.writerow(header)

        self._lineage_f = open(self.dir / "lineages.csv", "w", newline="", encoding="utf-8")
        self._lineage = csv.writer(self._lineage_f)
        self._lineage.writerow([
            "tick", "lineage_id", "population", "frac", "births_cum",
            "mean_body_size", "mean_light_absorption",
            "mean_reproduction_investment", "mean_mutation_rate",
            # 空間・行動指標 (V1.2.1)
            "occupied_cells", "centroid_x", "centroid_y",
            "mean_radius_from_centroid", "mean_move_per_org_tick",
            "mean_local_light", "vent_cell_frac", "mean_chemical_absorption",
        ])

        self._perf_f = open(self.dir / "performance.csv", "w", newline="", encoding="utf-8")
        self._perf = csv.writer(self._perf_f)
        self._perf.writerow(["tick", "population", "tick_ms", "ticks_per_sec"])

        self._last_stats_tick = -1
        self._last_snap_tick = -1

    # --- イベント ---

    def birth(self, tick: int, org) -> None:
        self._events.writerow(
            [tick, "birth", org.id, org.parent_id, org.lineage_id, org.generation, "", ""])

    def death(self, tick: int, org, cause: str) -> None:
        self._events.writerow(
            [tick, "death", org.id, "", org.lineage_id, "", cause, org.age])

    def disaster(self, tick: int, killed: int) -> None:
        self._events.writerow([tick, "disaster", "", "", "", "", f"killed={killed}", ""])

    # --- 計算性能 ---

    def performance(self, sim, tick_seconds: float) -> None:
        """1 tick の実測時間を記録する。進化ロジックには一切使用しない。"""
        if tick_seconds <= 0.0:
            return
        self._perf.writerow([
            sim.tick,
            len(sim.organisms),
            round(tick_seconds * 1000.0, 6),
            round(1.0 / tick_seconds, 3),
        ])
        if sim.tick % sim.cfg.stats_interval == 0:
            self._perf_f.flush()

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

        # 空間指標 (V1.2.1)。読み取り専用でRNG・個体状態に触れない
        sp_pop = population_spatial(sim)
        mean_move = (round(sim._move_sum / sim._move_count, 6)
                     if sim._move_count else "")

        # 系統別集計 (改善方針 Ver.1.2 §4)
        by_lineage: dict[int, list] = {}
        for o in orgs:
            by_lineage.setdefault(o.lineage_id, []).append(o)
        ranked = sorted(by_lineage.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        if ranked:
            top_id = ranked[0][0]
            top_frac = len(ranked[0][1]) / n
        else:
            top_id, top_frac = -1, 0.0
        for lid, members in ranked[:TOP_LINEAGES]:
            g = np.stack([o.genome for o in members])
            sp = lineage_spatial(sim, members)
            self._lineage.writerow([
                sim.tick, lid, len(members), round(len(members) / n, 6),
                sim.births_by_lineage.get(lid, 0),
                round(float(g[:, BODY_SIZE].mean()), 6),
                round(float(g[:, LIGHT_ABS].mean()), 6),
                round(float(g[:, REPRO_INVEST].mean()), 6),
                round(float(g[:, MUTATION_RATE].mean()), 6),
                sp["occupied_cells"], sp["centroid_x"], sp["centroid_y"],
                sp["mean_radius_from_centroid"], sp["mean_move_per_org_tick"],
                sp["mean_local_light"], sp["vent_cell_frac"],
                sp["mean_chemical_absorption"],
            ])
        self._lineage_f.flush()

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
            round(sim.light_supply_per_tick * sim.tick, 4),
            *[round(sim.flows[k], 4) for k in
              ("light", "chemical", "nutrient", "corpse_matter",
               "corpse_energy", "predation_energy", "predation_matter")],
            top_id, round(top_frac, 6),
            *[sp_pop[f"pop_{b}_band"] for b in BAND_NAMES],
            *[sp_pop[f"frac_{b}_band"] for b in BAND_NAMES],
            sp_pop["mean_local_light"], sp_pop["vent_cell_population"],
            sp_pop["vent_cell_frac"], mean_move,
            *[round(float(v), 6) for v in gmean],
            *[round(float(v), 6) for v in gvar],
        ]
        self._stats.writerow(row)
        self._stats_f.flush()
        self._events_f.flush()  # 中断時にイベントログの末尾が欠けないように
        self._last_stats_tick = sim.tick
        # 移動量は stats 区間ごとの平均にする
        sim._move_sum = 0.0
        sim._move_count = 0
        sim._move_by_lineage.clear()
        sim._movecnt_by_lineage.clear()

    # --- スナップショット ---

    def snapshot(self, sim) -> None:
        self._last_snap_tick = sim.tick

        # 環境スナップショット (V1.2.1)。光場と噴出口配置は不変なので1度だけ、
        # 化学ストックと無機栄養は時間変化するので毎回保存する。
        env = self.dir / "environment"
        if not self._static_saved:
            save_static_environment(env / "static.npz", sim)
            self._static_saved = True
        save_environment_snapshot(env / f"env_{sim.tick:08d}.npz", sim)

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

    def finalize(self, sim) -> None:
        """中断・終了時に、最終時点の統計とスナップショットを確実に残す。"""
        if sim.tick != self._last_stats_tick:
            self.stats(sim)
        if sim.tick != self._last_snap_tick:
            self.snapshot(sim)

    def close(self) -> None:
        self._events_f.close()
        self._stats_f.close()
        self._perf_f.close()
        self._lineage_f.close()
