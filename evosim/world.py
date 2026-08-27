"""環境フィールド (光・無機栄養・化学エネルギー)。仕様書 Ver.1.1 §2。

- 光: フロー型。毎tick供給され、使われなければ消える (熱散逸)。
- 無機栄養: 物質。再生せず、拡散と生体との交換のみ。世界全体で厳密保存。
- 化学: ストック型エネルギー。噴出口セルのみロジスティック回復 (外部流入)。
"""
from __future__ import annotations

import numpy as np

from .config import Config


class World:
    def __init__(self, cfg: Config, rng: np.random.Generator):
        self.cfg = cfg
        gw, gh = cfg.grid_w, cfg.grid_h

        # 光フラックス (静的な空間勾配) [E/tick/セル]
        if cfg.light_pattern == "vertical":
            frac = 1.0 - (np.arange(gh) + 0.5) / gh  # 北(y=0)が明るい
            col = cfg.light_max * (cfg.light_floor + (1.0 - cfg.light_floor) * frac)
            self.light = np.tile(col, (gw, 1))  # [ix, iy]
        else:
            self.light = np.full((gw, gh), cfg.light_max)

        # 無機栄養 (閉じた物質循環の無機物プール)
        self.nutrients = np.full((gw, gh), cfg.nutrient_initial)

        # 化学エネルギー: 噴出口マスクとストック
        self.chem_mask = np.zeros((gw, gh), dtype=bool)
        for _ in range(cfg.n_vents):
            vx = int(rng.integers(0, gw))
            vy = int(rng.integers(0, gh))
            r = cfg.vent_radius_cells
            for ix in range(max(0, vx - r), min(gw, vx + r + 1)):
                for iy in range(max(0, vy - r), min(gh, vy + r + 1)):
                    if (ix - vx) ** 2 + (iy - vy) ** 2 <= r * r:
                        self.chem_mask[ix, iy] = True
        self.chemical = np.where(self.chem_mask, cfg.chem_capacity * 0.5, 0.0)

    # --- 座標 → セル ---

    def cell_index(self, x: float, y: float) -> tuple[int, int]:
        cfg = self.cfg
        ix = min(cfg.grid_w - 1, max(0, int(x / cfg.cell_size)))
        iy = min(cfg.grid_h - 1, max(0, int(y / cfg.cell_size)))
        return ix, iy

    def cell_center(self, ix: int, iy: int) -> tuple[float, float]:
        c = self.cfg.cell_size
        return (ix + 0.5) * c, (iy + 0.5) * c

    # --- 毎tick更新 ---

    def update(self) -> float:
        """化学回復と栄養拡散。戻り値: 化学エネルギー流入量 (台帳用)。"""
        cfg = self.cfg
        # 化学: ロジスティック回復 (噴出口セルのみ)。下限から回復可能にする。
        c = self.chemical
        base = np.where(self.chem_mask, np.maximum(c, cfg.chem_min_stock), 0.0)
        growth = cfg.chem_regen * base * (1.0 - base / cfg.chem_capacity)
        growth = np.where(self.chem_mask, np.maximum(growth, 0.0), 0.0)
        chem_influx = float(growth.sum())
        self.chemical = c + growth

        # 栄養: ラプラシアン拡散 (境界は反射 → 総量保存)
        n = self.nutrients
        d = cfg.nutrient_diffusion
        padded = np.pad(n, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * n)
        # edgeパディングにより境界セルの「外側隣接」は自分自身 → 流出ゼロで保存
        self.nutrients = n + d * lap
        return chem_influx

    # --- 集計 (保存則検証・統計用) ---

    def total_nutrients(self) -> float:
        return float(self.nutrients.sum())

    def total_chemical(self) -> float:
        return float(self.chemical.sum())
