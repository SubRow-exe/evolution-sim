"""環境フィールド (光・無機栄養・化学エネルギー)。仕様書 Ver.1.1 §2 / V1.3。

- 光: フロー型。毎tick供給され、使われなければ消える (熱散逸)。
- 無機栄養: 物質。再生せず、拡散と生体との交換のみ。世界全体で厳密保存。
- 化学 (V1.3): 地質sourceから一定fluxで供給され、局所stockとして滞留し、
  混合・流出・希釈・酸化等で失われる。詳細は
  docs/V1.3_化学資源モデル仕様.md。
"""
from __future__ import annotations

import numpy as np

from .config import Config


def _build_vertical_light(cfg: Config) -> np.ndarray:
    """V1.1 Control の光場。北(y=0)が明るい線形勾配。

    **この式は変更しない。** V1.1 との比較基準そのものであるため。
    """
    gw, gh = cfg.grid_w, cfg.grid_h
    frac = 1.0 - (np.arange(gh) + 0.5) / gh
    col = cfg.light_max * (cfg.light_floor + (1.0 - cfg.light_floor) * frac)
    return np.tile(col, (gw, 1))  # [ix, iy]


def _build_high_contrast_light(cfg: Config) -> np.ndarray:
    """V1.2 Treatment。明部plateau → 線形遷移 → 暗部の3帯。

    形状を作ったあと、**同じConfigの vertical が持つ総光量**へ正規化する。
    これにより「空間偏在」と「総光量」を独立した軸として扱える
    (total_scale=1.0 なら世界全体のエネルギー流入量は Control と同じ)。

    乱数を一切消費しない。同一seedで chem_mask 等の確率生成物を変えないため。
    """
    gw, gh = cfg.grid_w, cfg.grid_h
    b = cfg.light_hc_bright_frac
    t = cfg.light_hc_transition_frac
    f = cfg.light_hc_dark_floor

    u = (np.arange(gh) + 0.5) / gh
    z = np.clip((u - b) / t, 0.0, 1.0)          # 遷移帯内の進行度
    shape = np.where(u < b, 1.0,
                     np.where(u < b + t, 1.0 - (1.0 - f) * z, f))

    raw = cfg.light_max * np.tile(shape, (gw, 1))
    raw_total = float(raw.sum())
    if raw_total <= 0.0:
        raise ValueError("high_contrast_vertical の光場が全てゼロになる")
    target_total = float(_build_vertical_light(cfg).sum()) * cfg.light_hc_total_scale
    return raw * (target_total / raw_total)


def build_light_field(cfg: Config) -> np.ndarray:
    """Config から光場を構築する。乱数は使わない。"""
    p = cfg.light_pattern
    if p == "vertical":
        return _build_vertical_light(cfg)
    if p == "uniform":
        return np.full((cfg.grid_w, cfg.grid_h), cfg.light_max)
    if p == "high_contrast_vertical":
        _validate_high_contrast(cfg)
        return _build_high_contrast_light(cfg)
    raise ValueError(
        f"未知の light_pattern: {p!r} "
        "(vertical | uniform | high_contrast_vertical)")


def _validate_high_contrast(cfg: Config) -> None:
    b, t = cfg.light_hc_bright_frac, cfg.light_hc_transition_frac
    f, s = cfg.light_hc_dark_floor, cfg.light_hc_total_scale
    if not 0.0 <= f < 1.0:
        raise ValueError(f"light_hc_dark_floor は 0 <= f < 1: {f}")
    if not 0.0 < b < 1.0:
        raise ValueError(f"light_hc_bright_frac は 0 < b < 1: {b}")
    if not 0.0 < t <= 1.0:
        raise ValueError(f"light_hc_transition_frac は 0 < t <= 1: {t}")
    if b + t > 1.0:
        raise ValueError(f"bright + transition が1を超える: {b} + {t}")
    if s <= 0.0:
        raise ValueError(f"light_hc_total_scale は正: {s}")


class World:
    def __init__(self, cfg: Config, rng: np.random.Generator):
        self.cfg = cfg
        gw, gh = cfg.grid_w, cfg.grid_h
        # ホットパス用のキャッシュ (Config のプロパティ参照と除算を避ける)
        self._cell_size = cfg.cell_size
        self._ix_max = gw - 1
        self._iy_max = gh - 1

        # 光フラックス (静的な空間分布) [E/tick/セル]。
        # rng より先に構築するが乱数を消費しないため、chem_mask の生成には影響しない。
        self.light = build_light_field(cfg)

        # 無機栄養 (閉じた物質循環の無機物プール)
        self.nutrients = np.full((gw, gh), cfg.nutrient_initial)

        # 化学エネルギー (V1.3): 地質source field と局所stock。
        # vent中心の抽選はV1.2と同じ乱数消費 (1 ventにつき整数2つ) を保つ。
        self.chem_source_flux = np.zeros((gw, gh))
        r = cfg.vent_radius_cells
        for _ in range(cfg.n_vents):
            vx = int(rng.integers(0, gw))
            vy = int(rng.integers(0, gh))
            cells = [(ix, iy)
                     for ix in range(max(0, vx - r), min(gw, vx + r + 1))
                     for iy in range(max(0, vy - r), min(gh, vy + r + 1))
                     if (ix - vx) ** 2 + (iy - vy) ** 2 <= r * r]
            # そのventの総fluxは、端で円盤が欠けても常に chem_vent_flux。
            # 欠けた分は残りのセルへ寄せる (世界総sourceをseedに依存させない)
            share = cfg.chem_vent_flux / len(cells)
            for ix, iy in cells:
                self.chem_source_flux[ix, iy] += share
        self.chem_mask = self.chem_source_flux > 0.0
        # 世界全体の外部chemical供給量/tick (不変)。台帳と検証用
        self.chem_source_total = float(self.chem_source_flux.sum())
        # 初期stockは生物不在の平衡値 = 更新式の不動点。
        # 「開始時だけ大量のstockが置かれている」人工的パルスを避ける
        self.chemical = self.chem_source_flux / cfg.chem_loss_frac

    # --- 座標 → セル ---

    def cell_index(self, x: float, y: float) -> tuple[int, int]:
        """座標 → セル添字。1 tickあたり数千回呼ばれる最ホットパス。

        cfg.grid_w / grid_h は毎回除算を行うプロパティなので __init__ で
        属性に固定してある。除算そのものは逆数乗算に置き換えない
        (x/20.0 と x*0.05 は浮動小数点の結果が一致せず、セル境界で
        添字が1ずれる可能性があるため)。
        """
        cell = self._cell_size
        ix = int(x / cell)
        iy = int(y / cell)
        if ix < 0:
            ix = 0
        elif ix > self._ix_max:
            ix = self._ix_max
        if iy < 0:
            iy = 0
        elif iy > self._iy_max:
            iy = self._iy_max
        return ix, iy

    def cell_center(self, ix: int, iy: int) -> tuple[float, float]:
        c = self.cfg.cell_size
        return (ix + 0.5) * c, (iy + 0.5) * c

    # --- 毎tick更新 ---

    def update(self) -> tuple[float, float]:
        """化学の環境損失+source供給と栄養拡散。

        戻り値: (chemical_influx, chemical_environment_loss) — Energy台帳用。

        V1.3の1 tick (docs/V1.3_化学資源モデル仕様.md §3):

            L  = chem_loss_frac * C      環境損失 (混合/流出/希釈/酸化)
            C1 = C - L
            C2 = C1 + S                  地質source。全量が入る (上限なし)

        `S` は生物の消費にも現在stockにも依存しない。stockが発散しないのは
        損失項があるためで、生物不在なら C* = S / chem_loss_frac へ収束する。
        """
        cfg = self.cfg
        # 化学: 環境損失 → 地質sourceの供給
        c = self.chemical
        loss = cfg.chem_loss_frac * c
        chem_loss = float(loss.sum())
        self.chemical = c - loss + self.chem_source_flux
        chem_influx = self.chem_source_total

        # 栄養: ラプラシアン拡散 (境界は反射 → 総量保存)
        n = self.nutrients
        d = cfg.nutrient_diffusion
        padded = np.pad(n, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * n)
        # edgeパディングにより境界セルの「外側隣接」は自分自身 → 流出ゼロで保存
        self.nutrients = n + d * lap
        return chem_influx, chem_loss

    # --- 集計 (保存則検証・統計用) ---

    def total_nutrients(self) -> float:
        return float(self.nutrients.sum())

    def total_chemical(self) -> float:
        return float(self.chemical.sum())
