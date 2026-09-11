"""シミュレーション本体 (仕様書 Ver.1.1 §5–8, 11, 13 / V1.9 iLUCA再設計仕様)。

設計原則:
- 適応度は計算しない。生存と繁殖はエネルギー・物質・損傷の帰結。
- 乱数は単一の numpy Generator。個体処理はリスト順で決定的。
- 物質は世界全体で厳密保存。エネルギーは流入・散逸を台帳で追跡。

V1.9: 1-pool Energy + storage_capacity gene、runway homeostasis、
H2 explicit substrate (chemical field置き換え)、structural innovation
(phototrophy)。詳細は docs/V1.9_iLUCA再設計仕様.md。
"""
from __future__ import annotations

import math

import numpy as np

from . import behavior, physiology, stoichiometry
from .config import Config
from .daynight import daylight_factor
from .corpse import Corpse
from .genome import (CHEM_ABS, CORPSE_DIG, LIGHT_ABS, MEMBRANE, NUTRIENT_ABS,
                     PREDATION, REPRO_HORIZON, REPRO_INVEST, STARV_HORIZON,
                     STORAGE_CAP, diagnostic_overrides, fixed_mask_from_names,
                     initial_capability, initial_genome, mutate,
                     structural_mutate)
from .organism import Organism
from .recorder import Recorder
from .stoichiometry import GROWTH_LIMITERS
from .world import VENT_BAND_NAMES, World

NB = len(VENT_BAND_NAMES)  # vent距離帯の本数 (観測専用)

# これ未満の吸収能力は「器官を持たない」とみなす (V1.3以前と同じ閾値)
ABILITY_EPS = 1e-6


class Simulation:
    def __init__(self, cfg: Config, seed: int, run_dir=None):
        self.cfg = cfg
        self.seed = seed
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self.fixed_mask = fixed_mask_from_names(cfg.fixed_genes)
        self.world = World(cfg, self.rng)
        self.tick = 0
        self.next_id = 0

        self.organisms: list[Organism] = []
        self.corpses: list[Corpse] = []
        self.org_hash: dict[tuple[int, int], list[Organism]] = {}
        self.corpse_hash: dict[tuple[int, int], list[Corpse]] = {}

        self.births_cum = 0
        self.deaths_cum = 0
        self.deaths_by_cause = {c: 0 for c in
                                ("starvation", "damage", "predation", "disaster")}

        # エネルギー台帳 (保存則検証用)
        self.energy_in_cum = 0.0        # 光吸収 + H2 source (energy-equivalent)
        self.energy_out_cum = 0.0       # 全散逸 (熱)

        # 資源利用率 (改善方針 Ver.1.2 §5): 経路別の累積獲得量。進化には不使用
        self.flows = {
            "light": 0.0,             # 光から得たエネルギー
            "h2": 0.0,                # H2 substrateから得たusable Energy
            "nutrient": 0.0,          # 無機栄養から得た物質
            "corpse_matter": 0.0,     # 死骸から同化した物質
            "corpse_energy": 0.0,     # 死骸から得たエネルギー
            "predation_energy": 0.0,  # 捕食で得たエネルギー
            "predation_matter": 0.0,  # 捕食で同化した物質
        }
        # V1.9 Energy ledger追加項目 (観測専用)
        self.h2_conversion_loss_cum = 0.0
        self.storage_overflow_cum = 0.0
        self.h2_influx_cum = 0.0   # substrate単位 (energy-equivalentではない)
        self.h2_loss_cum = 0.0     # substrate単位
        # physical_mode: 生物側が実取得したH2量 [mol] の累積 (観測専用)
        self.h2_biological_uptake_mol_cum = 0.0
        # V1.9 structural innovation観測 (観測専用・進化ロジックへ不使用)
        self.phototrophy_innovation_events = 0
        self.phototrophy_loss_events = 0

        # V1.10: C/N/P element ledger (docs/V1.10_CNP資源分解_実装仕様.md §7)。
        # explicit_cnp_resources=Falseでは全て0のまま (未使用)。
        self.c_in_external_cum = 0.0
        self.c_out_external_cum = 0.0
        self.n_in_external_cum = 0.0
        self.n_out_external_cum = 0.0
        self.p_in_external_cum = 0.0
        self.p_out_external_cum = 0.0
        # 生物学的uptake (fieldからbiomassへ; externalではなく内部移転)
        self.c_uptake_cum = 0.0
        self.n_uptake_cum = 0.0
        self.p_uptake_cum = 0.0
        # growth_limiter (§9)。cumulativeカウント (stats.csvへ毎回そのまま書く。
        # 区間rateはbirths_cum等と同様、呼び出し側が差分を取る)。
        self.growth_limiter_cum = {k: 0 for k in GROWTH_LIMITERS}

        # V1.11: 原始phototrophy Energy ledger diagnostics
        # (docs/V1.11_原始Phototrophy_実装仕様_rev2.md §6)。
        self.photo_incident_j_cum = 0.0
        self.photo_absorbed_j_cum = 0.0
        self.photo_usable_max_j_cum = 0.0
        self.photo_used_j_cum = 0.0
        self.photo_unused_j_cum = 0.0
        self.photo_conversion_loss_j_cum = 0.0
        # structural N assembly/release (internal transfer; N ledgerはfixed
        # N field + organism/corpse structural poolの総量で閉じる。§7.3)。
        self.photo_n_assembly_cum = 0.0
        self.photo_n_released_cum = 0.0

        # 世界全体の光供給量/tick (未利用光量の算出用・不変。昼夜cycle適用前のbase値)
        self.light_supply_per_tick = float(self.world.light.sum())
        # V1.8: そのtickのdaylight factor。step()冒頭で一度だけ決め、
        # sensing/light supply/light uptake/recorderが同じ値を共有する。
        # 初期値1.0はrun開始前 (tick=0) の状態で、最初のstep()呼び出しで
        # 実際のfactorへ更新される。
        self.daylight_factor_now = 1.0
        # V1.8: 実効光供給量の積算 (docs/V1.8_一次Energy生態非対称仕様.md §9)。
        # 昼夜導入後は static supply × tick で計算してはいけないため、
        # 毎stepの実効(daylight_factor適用後)供給量を積算する。
        self.light_supply_cum = 0.0
        # 系統別の累積出生数 (系統別統計用)
        self.births_by_lineage: dict[int, int] = {}

        # 一次Energy刺激の選択統計 (V1.5 観測)。stats記録ごとにリセットされる
        # 区間統計で、RNGも個体状態も進化ロジックも一切変えない。
        self.stim_obs = self._new_stim_obs()
        # V1.6 短期記憶のEMA更新率。alpha = 1 - exp(-1/tau)。
        # tick毎に exp を呼ばないよう __init__ で1度だけ求める。
        # tau <= 0 は「記憶しない」= 常に現在値 (alpha = 1)。
        tau = cfg.memory_tau
        self.stim_alpha = 1.0 if tau <= 0.0 else 1.0 - math.exp(-1.0 / tau)

        # 移動量の集計 (V1.2.1 観測)。stats記録ごとにリセットされる区間統計。
        # 読み取り専用であり進化ロジックには一切使わない。
        self._move_sum = 0.0
        self._move_count = 0
        self._move_by_lineage: dict[int, float] = {}
        self._movecnt_by_lineage: dict[int, int] = {}

        self.recorder: Recorder | None = (
            Recorder(run_dir, cfg, seed) if run_dir is not None else None)

        self._spawn_initial()
        # high-Q領域マスクは初期個体群の平均能力を使うので、生成後に作る
        self.hi_q_mask = self._build_hi_q_mask()
        self.initial_system_energy = self.system_energy()
        self.initial_system_matter = self.system_matter()

    def _build_hi_q_mask(self) -> np.ndarray:
        """high-Q領域 (Qが上位25%のセル) のマスク。**観測専用**。

        Exp10 §4/§5 の「high-Q領域滞在率」をPhase AとPhase Bで同じ定義に
        するために置く (`docs/Exp10_実験計画案.md`)。

        定義を再現可能に固定するため、次の2点で「生物不在の世界」を使う:

        - H2は実stockではなく生物不在平衡場 (world.h2, RNG不使用で構築済み)
        - 能力は初期個体群の平均 light/chemical_absorption

        Phase Bは診断表現型を固定するので、この平均は条件の表現型と一致する。
        マスクは初期化時に1度だけ作り、以後変えない。RNGを消費しない。
        """
        cfg = self.cfg
        light = self.world.light
        chem_eq = self.world.h2
        if self.organisms:
            g = np.stack([o.genome for o in self.organisms])
            la = float(g[:, LIGHT_ABS].mean())
            ca = float(g[:, CHEM_ABS].mean())
        else:
            la = ca = 0.0
        if la + ca <= 0.0:
            return np.zeros_like(light, dtype=bool)
        r_l = light / (light + cfg.light_stimulus_half)
        r_c = chem_eq / (chem_eq + cfg.chemical_stimulus_half)
        q = (la * r_l + ca * r_c) / (la + ca)
        return q >= float(np.quantile(q, 0.75))

    @staticmethod
    def _new_stim_obs() -> dict[str, object]:
        """V1.6 temporal sensing の観測。RNGを消費せず行動へ戻さない。

        `walk` はV1.5から引き継ぎ。それ以外はV1.6で入れ替えた
        (一次EnergyのWTAが無くなったので light/chemical選択回数は消える)。
        """
        return {"walk": 0,
                "stim_events": 0,
                "q_sum": 0.0, "q_mem_sum": 0.0,
                "dq_sum": 0.0, "dq_abs_sum": 0.0,
                "dq_light_sum": 0.0, "dq_chem_sum": 0.0,
                "turn_factor_sum": 0.0, "sigma_eff_sum": 0.0,
                "r_light_sum": 0.0, "r_chem_sum": 0.0,
                "dq_pos": 0, "dq_neg": 0, "dq_zero": 0,
                "turn_factor_pos_sum": 0.0, "turn_factor_neg_sum": 0.0,
                # vent距離帯別 (Exp10 §5.4)。index は world.VENT_BAND_NAMES
                "band_n": [0] * NB,
                "band_dq_light": [0.0] * NB,
                "band_dq_chem": [0.0] * NB,
                "band_sigma_eff": [0.0] * NB,
                "band_light_e": [0.0] * NB,
                "band_chem_e": [0.0] * NB}

    # ------------------------------------------------------------------
    # 初期個体群

    def _vent_cells(self) -> list[tuple[int, int]]:
        """H2 vent セルの一覧 (添字順で決定的)。乱数を消費しない。"""
        cells = [(int(ix), int(iy))
                 for ix, iy in np.argwhere(self.world.h2_mask)]
        if not cells:
            raise ValueError(
                "diagnostic_placement='vent' だが h2_mask が空 "
                "(n_vents / vent_radius_cellsを確認すること)")
        return cells

    def _spawn_initial(self) -> None:
        cfg = self.cfg
        # Exp06診断ハーネス (docs/Exp06_実験計画.md §5)。
        # 既定 (placement="random" / overrides無し) では下の分岐に入らず、
        # 乱数消費も含めて通常実行と完全に同一の経路を通る。
        if cfg.diagnostic_placement not in ("random", "vent"):
            raise ValueError(
                f"未知の diagnostic_placement: {cfg.diagnostic_placement!r} "
                "(random | vent)")
        overrides = diagnostic_overrides(cfg)
        vent_cells = (self._vent_cells() if cfg.diagnostic_placement == "vent"
                      else None)

        # V1.9 baseline: capabilityは両方OFF (docs/V1.9_iLUCA再設計仕様.md §2)。
        # diagnostic_force_phototrophyはmechanical sanity専用 (既定False)。
        base_capability = initial_capability()
        if cfg.diagnostic_force_phototrophy:
            base_capability = dict(base_capability)
            base_capability["phototrophy"] = True

        for _ in range(cfg.initial_population):
            capability = dict(base_capability)
            g = initial_genome(self.rng, cfg.initial_jitter_sigma, self.fixed_mask,
                               capability=capability)
            if overrides is not None:
                # 上書きは乱数を消費しない (同一seedで配置・変異系列を変えない)
                for idx, value in overrides:
                    g[idx] = value
            # V1.9 baseline: world uniform random spawn。H2濃度・vent座標は
            # 使わない (docs/V1.9_iLUCA再設計仕様.md §13)。diagnostic_placement
            # ="vent"はExp06互換の診断専用経路として残す。
            if vent_cells is None:
                x = float(self.rng.uniform(0, cfg.world_width))
                y = float(self.rng.uniform(0, cfg.world_height))
            else:
                ix, iy = vent_cells[int(self.rng.integers(0, len(vent_cells)))]
                x = float((ix + self.rng.random()) * cfg.cell_size)
                y = float((iy + self.rng.random()) * cfg.cell_size)
            org = Organism(self.next_id, -1, self.next_id, 0, 0, g,
                           x, y, float(self.rng.uniform(-math.pi, math.pi)),
                           cfg.initial_energy, cfg.initial_matter,
                           phototrophy_on=capability["phototrophy"],
                           predation_on=capability["predation"])
            self.next_id += 1
            self.organisms.append(org)
            if self.recorder:
                self.recorder.birth(0, org)
            self.births_cum += 1
            self.births_by_lineage[org.lineage_id] = (
                self.births_by_lineage.get(org.lineage_id, 0) + 1)
        # 初期個体の身体物質は栄養プール外から与えられたものとして台帳初期化
        # (initial_system_matter に含まれるので保存則は成立する)

    # ------------------------------------------------------------------
    # 集計 (保存則)

    def system_energy(self) -> float:
        """system全体のEnergy。H2はenergy-equivalentで含める
        (docs/V1.9_iLUCA再設計仕様.md §12)。physical_modeでは
        h2_usable_energy_j_per_mol [J/mol] をenergy-equivalent換算に使う
        (docs/V1.9_検証実装仕様_物理スケール版.md §7)。"""
        cfg = self.cfg
        yield_ = cfg.h2_usable_energy_j_per_mol if cfg.physical_mode else cfg.h2_energy_yield
        return (sum(o.energy for o in self.organisms)
                + sum(c.energy for c in self.corpses)
                + self.world.total_h2() * yield_)

    def system_matter(self) -> float:
        return (sum(o.matter for o in self.organisms)
                + sum(c.matter for c in self.corpses)
                + self.world.total_nutrients())

    # --- V1.10: 元素inventory (docs/V1.10_CNP資源分解_実装仕様.md §7) ---
    # system_matter()と異なり、explicit_cnp_resources=Trueでは
    # Organism.matterはC/N/P台帳から独立には保存されない (残り約40%の
    # H/O/S/ash分はimplicit/non-limiting水由来と仮定するため)。
    # 保存則は各元素ごとにここで検証する。

    def _biomass_element_totals(self) -> tuple[float, float, float]:
        total_matter = (sum(o.matter for o in self.organisms)
                        + sum(c.matter for c in self.corpses))
        return stoichiometry.matter_to_element_mol(total_matter, self.cfg)

    def system_carbon(self) -> float:
        c_bio, _, _ = self._biomass_element_totals()
        return self.world.total_dic() + c_bio

    def system_nitrogen(self) -> float:
        _, n_bio, _ = self._biomass_element_totals()
        # V1.11: phototrophy apparatus構造N (organism/corpse) もbiomass N
        # とは別枠のN inventoryなので明示的に加える (rev2 §7.3)。
        photo_n = (sum(o.photo_structural_n_mol for o in self.organisms)
                  + sum(c.photo_structural_n_mol for c in self.corpses))
        return self.world.total_fixed_nitrogen() + n_bio + photo_n

    def system_phosphorus(self) -> float:
        _, _, p_bio = self._biomass_element_totals()
        return self.world.total_phosphate() + p_bio

    # ------------------------------------------------------------------
    # メインループ

    def step(self) -> None:
        cfg = self.cfg
        self.tick += 1

        # 0. V1.8 daylight factor をstep開始time (current tick) から一度だけ
        #    決め、このstep内のsensing/light supply/light uptake/recorderが
        #    同じ値を共有する (途中でtickを進めて別factorを読まない)。
        self.daylight_factor_now = daylight_factor(self.tick, cfg)
        self.light_supply_cum += self.light_supply_per_tick * self.daylight_factor_now

        # 1. 環境更新 (H2湧出はエネルギー流入。energy-equivalentで計上)
        h2_influx, h2_loss = self.world.update()
        h2_yield = cfg.h2_usable_energy_j_per_mol if cfg.physical_mode else cfg.h2_energy_yield
        self.energy_in_cum += h2_influx * h2_yield
        self.energy_out_cum += h2_loss * h2_yield
        self.h2_influx_cum += h2_influx
        self.h2_loss_cum += h2_loss

        # 1.5 V1.10: C/N/P background exchange + 拡散 (H2とは独立メソッド)
        if cfg.explicit_cnp_resources:
            cnp = self.world.update_cnp()
            self.c_in_external_cum += cnp["c_in"]
            self.c_out_external_cum += cnp["c_out"]
            self.n_in_external_cum += cnp["n_in"]
            self.n_out_external_cum += cnp["n_out"]
            self.p_in_external_cum += cnp["p_in"]
            self.p_out_external_cum += cnp["p_out"]

        # 2. 空間ハッシュ (tick開始時の位置スナップショット)。
        #    行動決定はこの時点の刺激場・配置を見る。
        self._build_hashes()

        # 3. 全個体の行動決定と移動 (リスト順で決定的)
        moved: list[tuple[Organism, float]] = []
        for org in self.organisms:
            if not org.alive:
                continue
            org.age += 1
            org.attacked_recently = False
            v = behavior.decide_and_move(org, self)
            moved.append((org, v))
            # 移動量の集計 (V1.2.1 観測)。読み取り専用で、RNGにも
            # 個体状態にも一切フィードバックしない。
            self._move_sum += v
            self._move_count += 1
            self._move_by_lineage[org.lineage_id] = (
                self._move_by_lineage.get(org.lineage_id, 0.0) + v)
            self._movecnt_by_lineage[org.lineage_id] = (
                self._movecnt_by_lineage.get(org.lineage_id, 0) + 1)

        # 4. 移動後の空間ハッシュを再構築 (V1.4)。
        #    以降の吸収・局所相互作用はすべて移動後の位置で判定する。
        self._build_hashes()

        # 4.5 V1.9: そのtickのstarvation stateをtick開始時のenergyから1回だけ
        #     計算し、uptake_factor (吸収) とmetabolic_factor (維持費) の
        #     両方でこの1つの値を共有する (docs/V1.9_iLUCA再設計仕様.md §6)。
        #     未来情報は参照しない。RNGは消費しない。
        for org in self.organisms:
            if org.alive:
                org.starve_state = physiology.starvation_state(org, cfg)

        # 5. 環境フィールドからの吸収 (セル単位の需要比例配分・個体順に非依存)
        self._absorb_fields()

        # 5.5 V1.11: phototrophy apparatus構造Nのassembly (docs/V1.11_原始
        #     Phototrophy_実装仕様_rev2.md §7.3)。maintenance/repairより先に
        #     行い、そのtickのeffective absorptionへ反映する。
        if cfg.physical_light_enabled:
            self._assemble_photo_structural_n()

        # 6. 局所相互作用〜繁殖 (従来どおり個体逐次・リスト順で決定的)
        newborns: list[Organism] = []
        for org, v in moved:
            if not org.alive:
                continue
            self._eat_corpse(org)
            self._predate(org)

            # 生理 (維持コスト・損傷・修復)
            # V1.9/V1.10.1時点と同じ2回separateの += 順を保つ (m_cost+r_cost
            # とまとめて1回で加算すると浮動小数非結合性でenergy_out_cumの
            # 最終bitが変わり、tools/golden.pyのfingerprintが変わってしまう。
            # energy_out_cumはsimulationロジックへ一切フィードバックしない
            # 観測専用台帳だが、golden fingerprintはこの値を直接ハッシュに
            # 含むため、結果不変性検証上は意味のある差になる)。
            m_cost = physiology.maintenance_and_movement(org, cfg, v, org.starve_state)
            r_cost = physiology.repair(org, cfg, org.starve_state)
            self.energy_out_cum += m_cost
            self.energy_out_cum += r_cost

            # V1.11: 光からのmaintenance credit (docs §5)。当tickの
            # maintenance+repair支出を上限にのみ肩代わりし、余剰は次tickへ
            # 繰り越さず散逸する (growth/reproductionへは絶対に使わせない)。
            if cfg.physical_light_enabled and org.phototrophy_on:
                p_inc, p_abs, p_use = physiology.photo_power_chain_w(org, cfg)
                dt = cfg.dt_seconds
                photo_credit_j = p_use * dt
                self.photo_incident_j_cum += p_inc * dt
                self.photo_absorbed_j_cum += p_abs * dt
                self.photo_usable_max_j_cum += photo_credit_j
                self.photo_conversion_loss_j_cum += max(0.0, p_abs - p_use) * dt
                photo_used = min(photo_credit_j, m_cost + r_cost)
                if photo_used > 0.0:
                    org.energy += photo_used
                    self.energy_in_cum += photo_used
                    self.photo_used_j_cum += photo_used
                self.photo_unused_j_cum += photo_credit_j - photo_used

            # 死亡判定
            if org.energy <= 0.0:
                self._kill(org, "starvation")
                continue
            if org.damage >= org.damage_max(cfg.damage_capacity):
                self._kill(org, "predation" if org.attacked_recently else "damage")
                continue

            # 繁殖
            child = self._try_reproduce(org)
            if child is not None:
                newborns.append(child)

        # 7. 死亡個体の除去・新生児の追加
        self.organisms = [o for o in self.organisms if o.alive]
        self.organisms.extend(newborns)

        # 8. 死骸の分解・散逸
        self._decay_corpses()

        # 9. 記録
        if self.recorder:
            if self.tick % cfg.stats_interval == 0:
                self.recorder.stats(self)
            if self.tick % cfg.snapshot_interval == 0:
                self.recorder.snapshot(self)

    # ------------------------------------------------------------------
    # 空間ハッシュ

    def _build_hashes(self) -> None:
        self.org_hash = {}
        for o in self.organisms:
            key = self.world.cell_index(o.x, o.y)
            self.org_hash.setdefault(key, []).append(o)
        self.corpse_hash = {}
        for c in self.corpses:
            key = self.world.cell_index(c.x, c.y)
            self.corpse_hash.setdefault(key, []).append(c)

    # ------------------------------------------------------------------
    # 環境フィールドからの吸収 (V1.4 / V1.9 H2)

    def _absorb_fields(self) -> None:
        """光・H2・無機栄養をセル単位で配分する (V1.4 §4-6 / V1.9 §11)。

        セルごとに全個体の要求量 (demand) を先に求め、供給が足りなければ
        需要比例で縮小する。総取得は必ず ``min(供給, 総需要)`` になり、
        個体リスト順は配分結果に影響しない (V1.3以前の先着biasを廃止)。

        資源間の順序 (光 → H2 → 無機栄養) はV1.3以前と同じ。有効表面積と
        健全度はセル処理の開始時点で一度だけ求め、3資源で共有する。
        """
        cfg = self.cfg
        dc, pf = cfg.damage_capacity, cfg.phi_floor
        for key, orgs in self.org_hash.items():
            phis = [o.phi(dc, pf) for o in orgs]
            areas = [physiology.effective_surface(o.matter) for o in orgs]
            self._absorb_light(orgs, phis, areas, key)
            self._absorb_h2(orgs, phis, areas, key)
            if cfg.explicit_cnp_resources:
                self._grow_cnp(orgs, phis, key)
            else:
                self._absorb_nutrient(orgs, phis, areas, key)

    @staticmethod
    def _demand_scale(demands: list[float], supply: float) -> float:
        """需要比例配分の縮小率。総需要が供給以下なら1.0 (未利用分は残る)。

        合計に ``math.fsum`` を使うので、個体の並び順を変えても縮小率は
        ビット単位で同じになる。
        """
        if supply <= 0.0:
            return 0.0
        total = math.fsum(demands)
        if total <= 0.0:
            return 0.0
        return min(1.0, supply / total)

    def _absorb_light(self, orgs, phis, areas, key) -> None:
        """光: PHOTOTROPHY ON個体だけが変換できる。未利用光は散逸する。

        V1.8: そのtickの実効光は World.light (base/peak habitat field) に
        daylight_factor_now を掛けたもの。night (factor=0) では厳密に
        gain=0。V1.9では局所密度応答 H(I, light_uptake_half) を常時適用し、
        さらにstarvation uptake_factorを掛ける
        (docs/V1.9_iLUCA再設計仕様.md §6.2/§11)。PHOTOTROPHY OFFの個体は
        light_absorption=0が強制されているため、需要は自動的に0になる。
        """
        cfg = self.cfg
        flux = float(self.world.light[key]) * self.daylight_factor_now
        if flux <= 0.0:
            return
        coef = cfg.light_uptake_coef
        cap_base = cfg.energy_capacity_base
        resp = physiology.density_response(flux, cfg.light_uptake_half)
        demands = []
        for o, phi, area in zip(orgs, phis, areas):
            a = o.genome[LIGHT_ABS]
            if a <= ABILITY_EPS:
                demands.append(0.0)
                continue
            uf = physiology.uptake_factor(o.starve_state, cfg)
            raw = coef * a * area * phi * uf * resp
            demands.append(min(raw, max(0.0, physiology.energy_max(o, cfg) - o.energy)))
        scale = self._demand_scale(demands, flux)
        if scale <= 0.0:
            return
        gains = []
        for o, d in zip(orgs, demands):
            if d <= 0.0:
                continue
            gain = d * scale
            o.energy += gain
            gains.append(gain)
        taken = math.fsum(gains)
        self.energy_in_cum += taken
        self.flows["light"] += taken
        self.stim_obs["band_light_e"][int(self.world.vent_band[key])] += taken

    def _absorb_h2(self, orgs, phis, areas, key) -> None:
        """H2: substrateとして吸収し、conversion効率をかけてusable Energyへ
        変換する (docs/V1.9_iLUCA再設計仕様.md §11)。

        H2はEnergyそのものではない:
            free_energy = J(取得substrate) * h2_energy_yield
            usable      = free_energy * h2_conversion_eff
            loss        = free_energy - usable  (energy_outへ)

        stockは必ず実取得substrate量 (J) だけ減らす。局所密度応答
        H(C, h2_uptake_half) とstarvation uptake_factorを需要へ掛ける。
        """
        if self.cfg.physical_mode:
            self._absorb_h2_physical(orgs, phis, key)
            return
        cfg = self.cfg
        stock = float(self.world.h2[key])
        if stock <= 0.0:
            return
        rate = cfg.h2_uptake_coef
        cap_base = cfg.energy_capacity_base
        yield_ = cfg.h2_energy_yield
        eff = cfg.h2_conversion_eff
        resp = physiology.density_response(stock, cfg.h2_uptake_half)
        headroom_divisor = max(yield_ * eff, 1e-12)
        demands = []
        for o, phi, area in zip(orgs, phis, areas):
            a = o.genome[CHEM_ABS]
            if a <= ABILITY_EPS:
                demands.append(0.0)
                continue
            uf = physiology.uptake_factor(o.starve_state, cfg)
            raw = rate * a * area * phi * uf * resp
            headroom = max(0.0, o.energy_max(cap_base) - o.energy)
            demands.append(min(raw, headroom / headroom_divisor))
        scale = self._demand_scale(demands, stock)
        if scale <= 0.0:
            return
        substrate_taken = []
        energy_gains = []
        conv_loss_total = 0.0
        for o, d in zip(orgs, demands):
            if d <= 0.0:
                continue
            j = d * scale  # 実取得substrate量
            free_energy = j * yield_
            usable = free_energy * eff
            loss = free_energy - usable
            o.energy += usable
            substrate_taken.append(j)
            energy_gains.append(usable)
            conv_loss_total += loss
        taken = math.fsum(substrate_taken)
        self.world.h2[key] = max(0.0, stock - taken)
        gained_energy = math.fsum(energy_gains)
        self.energy_out_cum += conv_loss_total
        self.h2_conversion_loss_cum += conv_loss_total
        self.flows["h2"] += gained_energy
        self.stim_obs["band_chem_e"][int(self.world.vent_band[key])] += gained_energy

    def _absorb_h2_physical(self, orgs, phis, key) -> None:
        """physical_mode: Michaelis-Menten H2 uptake (docs §6-7)。

        world.h2[key] はconcentration [mol/m^3]。fair-shareは実amount
        [mol] で行い、取得molだけconcentrationを下げる。usable Energyは
        `mol_taken * h2_usable_energy_j_per_mol` (conversion loss項は
        physical baselineでは使わない。docs §7)。
        """
        cfg = self.cfg
        conc = float(self.world.h2[key])
        if conc <= 0.0:
            return
        voxel_volume = self.world.voxel_volume_m3
        available_mol = conc * voxel_volume
        demands_mol = []
        for o, phi in zip(orgs, phis):
            a = o.genome[CHEM_ABS]
            if a <= ABILITY_EPS:
                demands_mol.append(0.0)
                continue
            uf = physiology.uptake_factor(o.starve_state, cfg)
            rate_mol_s = physiology.physical_h2_uptake_rate_mol_s(
                conc, o.matter, a, uf, cfg) * phi
            raw_mol = rate_mol_s * cfg.dt_seconds
            headroom_j = max(0.0, physiology.energy_max(o, cfg) - o.energy)
            headroom_mol = headroom_j / max(cfg.h2_usable_energy_j_per_mol, 1e-12)
            demands_mol.append(min(raw_mol, headroom_mol))
        scale = self._demand_scale(demands_mol, available_mol)
        if scale <= 0.0:
            return
        taken_mol_list = []
        energy_gains = []
        for o, d in zip(orgs, demands_mol):
            if d <= 0.0:
                continue
            mol_taken = d * scale
            usable = mol_taken * cfg.h2_usable_energy_j_per_mol
            o.energy += usable
            taken_mol_list.append(mol_taken)
            energy_gains.append(usable)
        taken_mol = math.fsum(taken_mol_list)
        self.world.h2[key] = max(0.0, conc - taken_mol / voxel_volume)
        self.h2_biological_uptake_mol_cum += taken_mol
        gained_energy = math.fsum(energy_gains)
        self.flows["h2"] += gained_energy
        self.stim_obs["band_chem_e"][int(self.world.vent_band[key])] += gained_energy

    def _absorb_nutrient(self, orgs, phis, areas, key) -> None:
        """無機栄養 (物質): 吸収には同化エネルギーコストがかかる。

        配分前の要求量を、身体物質の余地と「現在のエネルギーで同化コストを
        払える量」でもcapする。したがって配分後にEnergyが負にならない。
        starvation uptake_factorを需要へ掛ける (docs/V1.9_iLUCA再設計仕様.md §6.2)。
        """
        cfg = self.cfg
        stock = float(self.world.nutrients[key])
        if stock <= 0.0:
            return
        if cfg.physical_mode:
            # docs §9: 0.20 matter unit/h * nutrient_absorption を
            # nutrient-rich条件でのcapとし、実growth energy costで律速する。
            rate = cfg.nutrient_uptake_rate_matter_per_h / 3600.0 * cfg.dt_seconds
            acost = cfg.growth_energy_j_per_kgdw * cfg.matter_unit_to_kgdw
        else:
            rate = cfg.nutrient_uptake
            acost = cfg.matter_absorb_cost
        demands = []
        for o, phi, area in zip(orgs, phis, areas):
            a = o.genome[NUTRIENT_ABS]
            if a <= ABILITY_EPS:
                demands.append(0.0)
                continue
            room = cfg.matter_cap_frac * o.target_size - o.matter
            if room <= 0.0:
                demands.append(0.0)
                continue
            uf = physiology.uptake_factor(o.starve_state, cfg)
            affordable = o.energy / acost
            if cfg.physical_mode:
                raw = rate * a  # matter unit/step、面積項は使わない (質量ベース)
            else:
                raw = rate * a * area * phi * uf
            demands.append(min(raw, room, affordable))
        scale = self._demand_scale(demands, stock)
        if scale <= 0.0:
            return
        gains = []
        for o, d in zip(orgs, demands):
            if d <= 0.0:
                continue
            u = d * scale
            cost = acost * u
            if cost > o.energy:  # 浮動小数の端数対策 (demand段階でcap済み)
                u = o.energy / acost
                cost = o.energy
            o.matter += u
            o.energy -= cost
            self.energy_out_cum += cost
            gains.append(u)
        taken = math.fsum(gains)
        self.world.nutrients[key] = max(0.0, stock - taken)
        self.flows["nutrient"] += taken

    def _grow_cnp(self, orgs: list[Organism], phis: list[float],
                  key: tuple[int, int]) -> None:
        """V1.10: 環境genericMatter吸収の代わりに、固定biomass組成の
        C/N/P台帳でOrganism.matter (dry biomass) 成長を律速する
        (docs/V1.10_CNP資源分解_実装仕様.md §4)。

        各個体の最大growth requestは3つの上限のminで決める (§4.1):

            dm_room    = matter_cap - current_matter
            dm_kinetic = V1.9 growth kinetic ceiling * nutrient_absorption * dt
            dm_energy  = E_growth_available / growth_energy_cost_per_matter

        `dm_kinetic`/`dm_energy` は、Exp15 attempt2 + Exp16で実際に
        validateされたLUCA proxy growth allocation
        (experiments/luca_proxy/run_luca_proxy.py の
        `_absorb_nutrient_luca` / `growth_available_energy_j`) と
        同じ式を再利用する:

            dm_kinetic     = kinetic_rate * nutrient_absorption * phi * uptake_factor
            E_protected    = min(E_max, P_full * max(starvation_horizon, dt))
            E_growth_avail = max(0, energy - E_protected)
            dm_energy      = E_growth_avail / growth_energy_cost_per_matter

        「growthはmaintenance用の現在runwayを侵食しない」という
        maintenance-first allocationをV1.10でも維持する
        (docs/V1.9_LUCA_proxy設計.md §4)。

        cell全体のC/N/P要求量に対しavailable stockから共通scale
        `s=min(1,s_C,s_N,s_P)` を求め、個体のdm_reqへ一律に掛ける
        (順序依存を避ける)。
        """
        cfg = self.cfg
        a_idx = NUTRIENT_ABS
        kinetic_rate = cfg.nutrient_uptake_rate_matter_per_h / 3600.0 * cfg.dt_seconds
        growth_cost_per_matter = cfg.growth_energy_j_per_kgdw * cfg.matter_unit_to_kgdw

        reqs: list[float] = []
        pre_limiters: list[str | None] = []
        e_avail_list: list[float] = []
        for o, phi in zip(orgs, phis):
            a = o.genome[a_idx]
            if a <= ABILITY_EPS:
                reqs.append(0.0)
                pre_limiters.append(None)
                e_avail_list.append(0.0)
                continue
            dm_room = cfg.matter_cap_frac * o.target_size - o.matter
            if dm_room <= 0.0:
                reqs.append(0.0)
                pre_limiters.append("room")
                e_avail_list.append(0.0)
                continue
            uf = physiology.uptake_factor(o.starve_state, cfg)
            dm_kinetic = kinetic_rate * a * phi * uf
            p_full = physiology.full_activity_expenditure_rate(o, cfg)
            horizon_s = max(float(o.genome[STARV_HORIZON]), cfg.dt_seconds)
            e_protected = min(physiology.energy_max(o, cfg), max(0.0, p_full * horizon_s))
            e_growth_available = max(0.0, o.energy - e_protected)
            dm_energy = e_growth_available / max(growth_cost_per_matter, 1e-300)
            limiter, dm_req = min(
                (("room", dm_room), ("kinetic", dm_kinetic), ("energy", dm_energy)),
                key=lambda kv: kv[1])
            reqs.append(max(0.0, dm_req))
            pre_limiters.append(limiter)
            e_avail_list.append(e_growth_available)

        total_dm_req = math.fsum(reqs)
        if total_dm_req <= 0.0:
            for lim in pre_limiters:
                if lim is not None:
                    self.growth_limiter_cum[lim] += 1
            return

        c_per_kgdw = stoichiometry.carbon_mol_per_kgdw(cfg)
        n_per_kgdw = stoichiometry.nitrogen_mol_per_kgdw(cfg)
        p_per_kgdw = stoichiometry.phosphorus_mol_per_kgdw(cfg)
        kgdw_per_matter = cfg.matter_unit_to_kgdw
        kgdw_req_total = total_dm_req * kgdw_per_matter
        c_req_mol = kgdw_req_total * c_per_kgdw
        n_req_mol = kgdw_req_total * n_per_kgdw
        p_req_mol = kgdw_req_total * p_per_kgdw

        voxel_volume = self.world.voxel_volume_m3
        c_avail = max(0.0, float(self.world.dic[key])) * voxel_volume
        n_avail = max(0.0, float(self.world.fixed_nitrogen[key])) * voxel_volume
        p_avail = max(0.0, float(self.world.phosphate[key])) * voxel_volume

        s_c = c_avail / c_req_mol if c_req_mol > 0.0 else 1.0
        s_n = n_avail / n_req_mol if n_req_mol > 0.0 else 1.0
        s_p = p_avail / p_req_mol if p_req_mol > 0.0 else 1.0
        s = max(0.0, min(1.0, s_c, s_n, s_p))

        element_limiter = None
        if s < 1.0:
            element_limiter = min(
                (("carbon", s_c), ("nitrogen", s_n), ("phosphorus", s_p)),
                key=lambda kv: kv[1])[0]

        dms: list[float] = []
        for o, dm_req, pre_lim, e_avail in zip(orgs, reqs, pre_limiters, e_avail_list):
            if pre_lim is None:
                continue
            if dm_req <= 0.0:
                self.growth_limiter_cum[pre_lim] += 1
                continue
            limiter = element_limiter if element_limiter is not None else pre_lim
            self.growth_limiter_cum[limiter] += 1
            dm = dm_req * s
            # protected reserveを浮動小数の端数でも侵食しないための再clamp
            # (run_luca_proxy.py の "re-evaluate immediately before spending"
            # と同じ防御)。
            dm = min(dm, e_avail / max(growth_cost_per_matter, 1e-300))
            if dm <= 0.0:
                continue
            cost = dm * growth_cost_per_matter
            o.matter += dm
            o.energy -= cost
            # V1.9 §4.2と同じ会計原則: system_energy()はbiomass化学potential
            # を計上しないため、合成に使ったEnergyはledger上out (熱扱い)。
            self.energy_out_cum += cost
            dms.append(dm)

        dm_actual = math.fsum(dms)
        if dm_actual <= 0.0:
            return
        kgdw_actual = dm_actual * kgdw_per_matter
        c_used = kgdw_actual * c_per_kgdw
        n_used = kgdw_actual * n_per_kgdw
        p_used = kgdw_actual * p_per_kgdw
        self.world.dic[key] = max(0.0, float(self.world.dic[key]) - c_used / voxel_volume)
        self.world.fixed_nitrogen[key] = max(
            0.0, float(self.world.fixed_nitrogen[key]) - n_used / voxel_volume)
        self.world.phosphate[key] = max(
            0.0, float(self.world.phosphate[key]) - p_used / voxel_volume)
        self.c_uptake_cum += c_used
        self.n_uptake_cum += n_used
        self.p_uptake_cum += p_used
        self.flows["nutrient"] += dm_actual

    def _assemble_photo_structural_n(self) -> None:
        """phototrophy apparatus構造Nのassembly (docs/V1.11_原始Phototrophy_
        実装仕様_rev2.md §7.3)。

        実装簡略化: 仕様は同一cell内での競合配分を明示していないため、ここ
        では個体を順に処理する非競合 (greedy) 方式を取る (既存H2/nutrient
        吸収の需要比例配分より単純)。総量保存 (N ledger closure) は
        fixed_nitrogen fieldからの直接減算/organismへの直接加算で保たれる。
        """
        cfg = self.cfg
        vv = self.world.voxel_volume_m3
        for org in self.organisms:
            if not org.phototrophy_on:
                continue
            target = physiology.photo_n_target_mol(org, cfg)
            need = target - org.photo_structural_n_mol
            if need <= 0.0:
                continue
            key = self.world.cell_index(org.x, org.y)
            avail_mol = max(0.0, float(self.world.fixed_nitrogen[key])) * vv
            take = min(need, avail_mol)
            if take <= 0.0:
                continue
            org.photo_structural_n_mol += take
            self.world.fixed_nitrogen[key] = max(
                0.0, float(self.world.fixed_nitrogen[key]) - take / vv)
            self.photo_n_assembly_cum += take

    def _release_photo_n_to_field(self, x: float, y: float, n_mol: float) -> None:
        """phototrophy構造Nをfixed-N fieldへ戻す (capability loss / death /
        corpse decay時の共通経路。silent lossを禁止する。rev2 §7.3)。"""
        if n_mol <= 0.0:
            return
        key = self.world.cell_index(x, y)
        vv = self.world.voxel_volume_m3
        self.world.fixed_nitrogen[key] = float(self.world.fixed_nitrogen[key]) + n_mol / vv
        self.photo_n_released_cum += n_mol

    def _return_matter_to_field(self, ix: int, iy: int, matter_amount: float) -> None:
        """decay/waste由来のmatterを環境へ戻す共通経路 (V1.9 nutrient /
        V1.10 C/N/P)。corpse decay・predation waste・corpse捕食の排泄は
        すべてここを通す (docs/V1.10_CNP資源分解_実装仕様.md §6)。

        V1.10 (explicit_cnp_resources=True): 固定biomass組成でC/N/Pへ
        戻す (internal transfer。externalledgerには数えない)。
        V1.9 (False): 従来通りworld.nutrientsへ (挙動不変)。
        """
        if matter_amount <= 0.0:
            return
        cfg = self.cfg
        if cfg.explicit_cnp_resources:
            c_mol, n_mol, p_mol = stoichiometry.matter_to_element_mol(matter_amount, cfg)
            vv = self.world.voxel_volume_m3
            self.world.dic[ix, iy] += c_mol / vv
            self.world.fixed_nitrogen[ix, iy] += n_mol / vv
            self.world.phosphate[ix, iy] += p_mol / vv
        else:
            self.world.nutrients[ix, iy] += matter_amount

    def _eat_corpse(self, org: Organism) -> None:
        cfg = self.cfg
        g = org.genome
        if g[CORPSE_DIG] <= 1e-6:
            return
        # 内側ループは1 tickあたり数万回まわるため、属性参照とメソッド呼び出しを
        # ローカルへ引き上げてある。計算式と走査順序は元のまま (結果は同一)。
        rc = cfg.radius_coef
        m = org.matter
        r = rc * math.sqrt(m if m > 1e-9 else 1e-9)
        ox, oy = org.x, org.y
        target = None
        best_d2 = None
        ix, iy = self.world.cell_index(ox, oy)
        chash = self.corpse_hash
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = chash.get((ix + dx, iy + dy))
                if not cell:
                    continue
                for c in cell:
                    cm = c.matter
                    if cm <= 0.0:
                        continue
                    cr = rc * math.sqrt(cm if cm > 1e-9 else 1e-9)
                    d2 = (c.x - ox) ** 2 + (c.y - oy) ** 2
                    if d2 <= (r + cr) ** 2 and (best_d2 is None or d2 < best_d2):
                        target, best_d2 = c, d2
        if target is None:
            return
        phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
        e_max = physiology.energy_max(org, cfg)
        matter_cap = cfg.matter_cap_frac * org.target_size

        bite = min(cfg.corpse_eat_rate * g[CORPSE_DIG] * org.matter * phi, target.matter)
        if bite <= 0.0:
            return
        # 物質: 同化率で取り込み、残りは排泄として栄養フィールドへ (厳密保存)
        assim = min(bite * cfg.assimilation, max(0.0, matter_cap - org.matter))
        waste = bite - assim
        org.matter += assim
        cx, cy = self.world.cell_index(target.x, target.y)
        self._return_matter_to_field(cx, cy, waste)
        # エネルギー: 死骸の残エネルギーを物質比で同時取得
        e_frac = bite / target.matter if target.matter > 0 else 0.0
        e_take = target.energy * e_frac
        e_gain = min(e_take * cfg.assimilation, max(0.0, e_max - org.energy))
        org.energy += e_gain
        self.energy_out_cum += e_take - e_gain
        target.energy -= e_take
        target.matter -= bite
        self.flows["corpse_matter"] += assim
        self.flows["corpse_energy"] += e_gain

    def _predate(self, org: Organism) -> None:
        cfg = self.cfg
        g = org.genome
        if g[PREDATION] <= 1e-6:
            return
        rc = cfg.radius_coef
        m = org.matter
        r = rc * math.sqrt(m if m > 1e-9 else 1e-9)
        ox, oy = org.x, org.y
        ix, iy = self.world.cell_index(ox, oy)
        target = None
        best_d2 = None
        ohash = self.org_hash
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = ohash.get((ix + dx, iy + dy))
                if not cell:
                    continue
                for other in cell:
                    if other is org or not other.alive:
                        continue
                    d2 = (other.x - ox) ** 2 + (other.y - oy) ** 2
                    if best_d2 is not None and d2 >= best_d2:
                        continue
                    om = other.matter
                    orad = rc * math.sqrt(om if om > 1e-9 else 1e-9)
                    if d2 <= (r + orad) ** 2:
                        target, best_d2 = other, d2
        if target is None:
            return
        phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
        attack = cfg.attack_coef * g[PREDATION] * org.matter * phi
        defense = cfg.defense_coef * target.genome[MEMBRANE] * target.matter
        net = attack - defense
        cost = cfg.attack_cost * g[PREDATION] * org.matter
        org.energy -= cost
        self.energy_out_cum += cost
        if net <= 0.0:
            return
        target.damage += net
        target.attacked_recently = True
        e_max = physiology.energy_max(org, cfg)
        matter_cap = cfg.matter_cap_frac * org.target_size

        # エネルギー吸取
        e_take = min(target.energy, cfg.bite_energy * net)
        e_gain = min(e_take * cfg.assimilation, max(0.0, e_max - org.energy))
        target.energy -= e_take
        org.energy += e_gain
        self.energy_out_cum += e_take - e_gain
        # 物質吸取 (残りは排泄 → 栄養フィールド)
        m_take = min(target.matter, cfg.bite_matter * net)
        m_gain = min(m_take * cfg.assimilation, max(0.0, matter_cap - org.matter))
        target.matter -= m_take
        org.matter += m_gain
        self.flows["predation_energy"] += e_gain
        self.flows["predation_matter"] += m_gain
        tx, ty = self.world.cell_index(target.x, target.y)
        self._return_matter_to_field(tx, ty, m_take - m_gain)
        # 咬まれて身体を失った獲物のエネルギー上限超過分は散逸
        overflow = physiology.clamp_energy_to_capacity(target, cfg)
        self.energy_out_cum += overflow
        self.storage_overflow_cum += overflow

    # ------------------------------------------------------------------
    # 死亡・死骸

    def _kill(self, org: Organism, cause: str) -> None:
        org.alive = False
        if org.energy < 0.0:
            # コストは全額散逸として計上済みだが、実在したのは残額のみ。
            # 過剰計上分を台帳から戻す (保存則を厳密に保つ)。
            self.energy_out_cum += org.energy
            org.energy = 0.0
        self.deaths_cum += 1
        self.deaths_by_cause[cause] += 1
        self.corpses.append(Corpse(org.x, org.y, org.matter, org.energy,
                                   photo_structural_n_mol=org.photo_structural_n_mol))
        org.photo_structural_n_mol = 0.0
        if self.recorder:
            self.recorder.death(self.tick, org, cause)

    def _decay_corpses(self) -> None:
        cfg = self.cfg
        survivors = []
        for c in self.corpses:
            ix, iy = self.world.cell_index(c.x, c.y)
            decay_m = c.matter * cfg.corpse_decay
            c.matter -= decay_m
            self._return_matter_to_field(ix, iy, decay_m)
            # V1.11: corpseが保持するphototrophy構造Nもbiomassと同じ割合で
            # decayし、fixed-N fieldへ戻す (silent loss禁止。rev2 §7.3)。
            if c.photo_structural_n_mol > 0.0:
                n_decay = c.photo_structural_n_mol * cfg.corpse_decay
                c.photo_structural_n_mol -= n_decay
                self._release_photo_n_to_field(c.x, c.y, n_decay)
            decay_e = c.energy * cfg.corpse_energy_decay
            c.energy -= decay_e
            self.energy_out_cum += decay_e
            if c.matter < cfg.corpse_min_matter:
                self._return_matter_to_field(ix, iy, c.matter)
                self.energy_out_cum += c.energy
                self._release_photo_n_to_field(c.x, c.y, c.photo_structural_n_mol)
                c.photo_structural_n_mol = 0.0
                continue
            survivors.append(c)
        self.corpses = survivors

    # ------------------------------------------------------------------
    # 繁殖 (無性生殖) — V1.9 runway gate + storage capacity

    def _try_reproduce(self, org: Organism) -> Organism | None:
        """V1.9繁殖手順 (docs/V1.9_iLUCA再設計仕様.md §7.1)。

        1. runway gate (Energy): runway >= genome[reproduction_horizon]
        2. Matter gate: 既存 repro_matter_frac を維持
        3. birth_overheadを支払えるか確認
        4. continuous mutation + capability structural mutationでchild genotype
        5-6. child matter譲渡 (child_matter_frac)
        7-9. child Energy offer (reproduction_investment) → capacity clamp
        10. parent/child双方でcapacity clamp、overflowはheatへ
        """
        cfg = self.cfg

        # 1. runway gate
        r = physiology.runway(org, cfg)
        if r < org.genome[REPRO_HORIZON]:
            return None
        # 2. Matter gate
        if org.matter < cfg.repro_matter_frac * org.target_size:
            return None
        # 3. birth_overheadを支払えるか確認 (支払えないtickは繁殖しない)
        if org.energy < cfg.birth_overhead:
            return None
        org.energy -= cfg.birth_overhead
        self.energy_out_cum += cfg.birth_overhead

        # 4. continuous mutation + capability structural mutation
        child_genome = mutate(org.genome, self.rng,
                              cfg.meta_mutation_sigma, cfg.additive_mutation_frac,
                              self.fixed_mask)
        child_capability, child_genome = structural_mutate(
            org.capability, child_genome, self.rng, cfg)
        if child_capability["phototrophy"] and not org.phototrophy_on:
            self.phototrophy_innovation_events += 1
        elif org.phototrophy_on and not child_capability["phototrophy"]:
            self.phototrophy_loss_events += 1

        # 5-6. 物質譲渡 (親→子; 保存)
        m_child = cfg.child_matter_frac * org.matter
        org.matter -= m_child

        # V1.11: phototrophy構造Nをmatter比率と同じchild_matter_fracで
        # 親から子へ譲渡する (rev2 §7.3)。childがphototrophy capabilityを
        # 失った場合、譲渡分の構造material machineryは維持できないため
        # 局所fixed-N fieldへ戻す (silent loss禁止)。
        n_transfer = org.photo_structural_n_mol * cfg.child_matter_frac
        org.photo_structural_n_mol -= n_transfer
        child_photo_n = n_transfer if child_capability["phototrophy"] else 0.0
        if not child_capability["phototrophy"] and n_transfer > 0.0:
            self._release_photo_n_to_field(org.x, org.y, n_transfer)

        # 7-9. Energy offer → child capacity clamp
        # child_emaxはphysiology.energy_max()経由 (physical_modeではJ、
        # arbitrary modeでは旧arbitrary unit) で求めるため、先にe_child=0の
        # 仮childを作ってからoffer量をclampする。
        e_offer = org.genome[REPRO_INVEST] * org.energy

        ang = float(self.rng.uniform(-math.pi, math.pi))
        dist = org.radius(cfg.radius_coef) * 2.0
        cx = min(max(org.x + math.cos(ang) * dist, 1.0), cfg.world_width - 1.0)
        cy = min(max(org.y + math.sin(ang) * dist, 1.0), cfg.world_height - 1.0)

        child = Organism(self.next_id, org.id, org.lineage_id,
                         org.generation + 1, self.tick, child_genome,
                         cx, cy, ang, 0.0, m_child,
                         phototrophy_on=child_capability["phototrophy"],
                         predation_on=child_capability["predation"],
                         photo_structural_n_mol=child_photo_n)
        child_emax = physiology.energy_max(child, cfg)
        e_child = min(e_offer, child_emax)
        child.energy = e_child
        org.energy -= e_child

        # 10. 親のcapacity clamp (身体縮小でE_maxが下がる → 超過分は散逸)
        p_overflow = physiology.clamp_energy_to_capacity(org, cfg)
        self.energy_out_cum += p_overflow
        self.storage_overflow_cum += p_overflow
        # child capacity clamp (e_child <= child_emaxで既に保証されるが、
        # 浮動小数の端数対策として明示的に確認する)
        c_overflow = physiology.clamp_energy_to_capacity(child, cfg)
        self.energy_out_cum += c_overflow
        self.storage_overflow_cum += c_overflow

        self.next_id += 1
        self.births_cum += 1
        self.births_by_lineage[child.lineage_id] = (
            self.births_by_lineage.get(child.lineage_id, 0) + 1)
        if self.recorder:
            self.recorder.birth(self.tick, child)
        return child

    # ------------------------------------------------------------------

    def close(self) -> None:
        if self.recorder:
            self.recorder.close()
