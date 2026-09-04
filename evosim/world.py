"""環境フィールド (光・無機栄養・H2 substrate)。仕様書 Ver.1.1 §2 / V1.9。

- 光: フロー型。毎tick供給され、使われなければ消える (熱散逸)。
- 無機栄養: 物質。再生せず、拡散と生体との交換のみ。世界全体で厳密保存。
- H2 (V1.9, docs/V1.9_iLUCA再設計仕様.md §8-10): 地質sourceから一定fluxで
  供給される局所stock。V1.8以前の`chemical` fieldをH2-like substrateの
  意味へ置き換え、環境損失・source供給に加えて明示的な4近傍拡散を持つ
  (source周辺にhalo/勾配を作る)。H2はEnergyそのものではなくsubstrateで
  あり、individual側のuptake/conversionを経て初めてusable Energyになる
  (evosim/simulation.py の _absorb_h2 / evosim/physiology.py)。
"""
from __future__ import annotations

import math

import numpy as np

from .config import Config

# vent距離帯の境界 [cell] (観測専用)。band = digitize(距離, これ)
#   band 0: 0-1 / 1: 1-2 / 2: 2-4 / 3: 4+
VENT_BAND_EDGES = (1.0, 2.0, 4.0)
VENT_BAND_NAMES = ("d0_1", "d1_2", "d2_4", "d4plus")


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


def _place_vents(cfg: Config, rng: np.random.Generator) -> list[tuple[int, int]]:
    """H2 vent中心をworld端からr以上内側・source disk非重複で配置する。

    候補集合を決定的な順序 (行優先のセル添字順) で構築し、その中から
    rngで選ぶ。選んだ中心とdisk (半径r) が重ならない候補だけを残しながら
    繰り返す。配置不可能ならValueError (docs/V1.9_iLUCA再設計仕様.md §9)。
    """
    gw, gh, r = cfg.grid_w, cfg.grid_h, cfg.vent_radius_cells
    lo_x, hi_x = r, gw - r - 1
    lo_y, hi_y = r, gh - r - 1
    if lo_x > hi_x or lo_y > hi_y:
        raise ValueError(
            f"vent_radius_cells={r} がworld ({gw}x{gh}) に対して大きすぎます。")
    candidates = [(vx, vy) for vx in range(lo_x, hi_x + 1) for vy in range(lo_y, hi_y + 1)]
    remaining = candidates
    centers: list[tuple[int, int]] = []
    min_sep2 = (2 * r) ** 2  # disk (半径r) が重ならないためには中心間距離 > 2r
    for _ in range(cfg.n_vents):
        if not remaining:
            raise ValueError(
                f"n_vents={cfg.n_vents} 個のvent中心をsource disk非重複で "
                "配置できません (world/vent_radius_cellsを確認)。")
        idx = int(rng.integers(0, len(remaining)))
        cx, cy = remaining[idx]
        centers.append((cx, cy))
        remaining = [p for p in remaining if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 > min_sep2]
    return centers


def _diffuse_h2(h2: np.ndarray, loss_frac: float, diffusion: float,
                source_flux: np.ndarray) -> np.ndarray:
    """H2の1 tick分の update: 環境損失 -> source供給 -> 4近傍拡散。

    拡散はreflecting boundary (edge padding) で総量を保存する
    (docs/V1.9_iLUCA再設計仕様.md §10.1)。
    """
    loss = loss_frac * h2
    h2_after_loss = h2 - loss
    h2_with_source = h2_after_loss + source_flux
    padded = np.pad(h2_with_source, 1, mode="edge")
    lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
           + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * h2_with_source)
    return h2_with_source + diffusion * lap


_H2_WARMUP_ITERS = 3000  # 生物不在の定常場へ収束させる固定反復数 (RNG不使用)


def _equilibrium_h2(source_flux: np.ndarray, loss_frac: float,
                    diffusion: float) -> np.ndarray:
    """生物不在でのH2定常場をdeterministicなfixed-point iterationで求める。

    開始時だけ大量のstockが置かれる人工的パルスを避ける
    (docs/V1.9_iLUCA再設計仕様.md §10.2)。RNGは一切消費しない。
    """
    h2 = np.zeros_like(source_flux)
    for _ in range(_H2_WARMUP_ITERS):
        h2 = _diffuse_h2(h2, loss_frac, diffusion, source_flux)
    return h2


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

        # H2 substrate (V1.9): 地質source field と局所stock。
        # vent中心はworld端からr以上内側・source disk非重複という制約の下、
        # 決定的な候補順序からrngで選ぶ (docs/V1.9_iLUCA再設計仕様.md §9)。
        self.vent_centers: list[tuple[int, int]] = _place_vents(cfg, rng)
        r = cfg.vent_radius_cells
        self.h2_source_flux = np.zeros((gw, gh))
        for vx, vy in self.vent_centers:
            cells = [(ix, iy)
                     for ix in range(vx - r, vx + r + 1)
                     for iy in range(vy - r, vy + r + 1)
                     if (ix - vx) ** 2 + (iy - vy) ** 2 <= r * r]
            # vent中心はedgeからr以上内側なので円盤は常に欠けず、
            # 全ventで同じセル数・同じ総flux (等flux) が保証される。
            share = cfg.h2_vent_flux / len(cells)
            for ix, iy in cells:
                self.h2_source_flux[ix, iy] += share
        self.h2_mask = self.h2_source_flux > 0.0
        # vent中心からの距離帯 (観測専用・静的)。Exp10 §5.4 の層別集計に使う。
        #   0: 0-1 cell / 1: 1-2 / 2: 2-4 / 3: 4+ (ventが無ければ全て3)
        self.vent_band = np.full((gw, gh), len(VENT_BAND_EDGES), dtype=np.int8)
        if self.vent_centers:
            ii, jj = np.meshgrid(np.arange(gw), np.arange(gh), indexing="ij")
            d = np.full((gw, gh), np.inf)
            for vx, vy in self.vent_centers:
                d = np.minimum(d, np.hypot(ii - vx, jj - vy))
            self.vent_band = np.digitize(d, VENT_BAND_EDGES).astype(np.int8)
        # 世界全体の外部H2供給量/tick (不変)。台帳と検証用
        self.h2_source_total = float(self.h2_source_flux.sum())
        # 初期stockはdeterministicなfixed-point iterationで求める
        # (生物不在・RNG不使用。docs/V1.9_iLUCA再設計仕様.md §10.2)。
        self.h2 = _equilibrium_h2(self.h2_source_flux, cfg.h2_loss_frac, cfg.h2_diffusion)

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

    # --- 知覚 (V1.6) ---

    def sample(self, arr: np.ndarray, x: float, y: float) -> float:
        """連続座標 (x, y) における field 値を双線形補間で返す (V1.6 §2.1)。

        **知覚専用**である。吸収・供給・損失はV1.5以前のままセル単位で行う。

        なぜ必要か (docs/V1.6_Exp10_レビュー.md A-2):
        field はセル内一定 (piecewise constant) なので、そのまま読むと
        同じセルに留まる約24 tickの間 `Q_now - Q_memory` が厳密に0になり、
        時間比較による走性が原理的に働かない。知覚だけを空間連続にする。

        補間はセル**中心**を格子点とする。したがってセル中心では元の
        field値と厳密に一致する。world端では最外セルの値へ clamp するので
        境界でも連続で、外挿はしない。
        """
        c = self._cell_size
        fx = x / c - 0.5
        fy = y / c - 0.5
        i0 = math.floor(fx)
        j0 = math.floor(fy)
        tx = fx - i0
        ty = fy - j0
        # 端は最外セルへ clamp。i0 == i1 になると tx が効かず値が一定になる
        i0c = 0 if i0 < 0 else (self._ix_max if i0 > self._ix_max else i0)
        i1c = 0 if i0 + 1 < 0 else (self._ix_max if i0 + 1 > self._ix_max else i0 + 1)
        j0c = 0 if j0 < 0 else (self._iy_max if j0 > self._iy_max else j0)
        j1c = 0 if j0 + 1 < 0 else (self._iy_max if j0 + 1 > self._iy_max else j0 + 1)
        v00 = arr[i0c, j0c]
        v10 = arr[i1c, j0c]
        v01 = arr[i0c, j1c]
        v11 = arr[i1c, j1c]
        return float((v00 * (1.0 - tx) + v10 * tx) * (1.0 - ty)
                     + (v01 * (1.0 - tx) + v11 * tx) * ty)

    def vent_distance_cells(self, x: float, y: float) -> float:
        """最寄りvent中心までの距離 [cell]。観測専用 (Exp10の距離帯別集計)。

        ventが1つも無い世界では inf を返す。
        """
        if not self.vent_centers:
            return float("inf")
        c = self.cfg.cell_size
        best = float("inf")
        for vx, vy in self.vent_centers:
            cx, cy = (vx + 0.5) * c, (vy + 0.5) * c
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 < best:
                best = d2
        return math.sqrt(best) / c

    # --- 毎tick更新 ---

    def update(self) -> tuple[float, float]:
        """H2の環境損失+source供給+拡散と栄養拡散。

        戻り値: (h2_influx, h2_environment_loss) — Energy台帳用
        (H2はenergy-equivalentで換算する。evosim/simulation.py)。

        V1.9の1 tick (docs/V1.9_iLUCA再設計仕様.md §10.1):

            1. environmental loss   L  = h2_loss_frac * C
            2. source influx        C2 = (C - L) + S
            3. 4-neighbor拡散 (reflecting boundary、総量保存)

        `S` は生物の消費にも現在stockにも依存しない。損失項があるため
        stockは発散せず、生物不在なら定常場 (_equilibrium_h2) へ収束する。
        """
        cfg = self.cfg
        h2_before = self.h2
        h2_loss = float((cfg.h2_loss_frac * h2_before).sum())
        h2_influx = self.h2_source_total
        self.h2 = _diffuse_h2(h2_before, cfg.h2_loss_frac, cfg.h2_diffusion,
                              self.h2_source_flux)

        # 栄養: ラプラシアン拡散 (境界は反射 → 総量保存)
        n = self.nutrients
        d = cfg.nutrient_diffusion
        padded = np.pad(n, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * n)
        # edgeパディングにより境界セルの「外側隣接」は自分自身 → 流出ゼロで保存
        self.nutrients = n + d * lap
        return h2_influx, h2_loss

    # --- 集計 (保存則検証・統計用) ---

    def total_nutrients(self) -> float:
        return float(self.nutrients.sum())

    def total_h2(self) -> float:
        return float(self.h2.sum())
