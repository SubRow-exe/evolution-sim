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


# --- physical_mode: H2 concentration field [mol/m^3] ------------------
#
# docs/V1.9_検証実装仕様_物理スケール版.md §5-6。
# source cell は Dirichlet 境界 (常に h2_source_concentration_molm3 へ
# 復元) として扱い、拡散は生物のdtとは別にsubcycleする
# (CFL alpha = D*dt_sub/dx^2 <= h2_subcycle_alpha_max)。
# 「exchange」sink dC/dt = -C/tau は化学分解ではなく、未解決の背景
# 混合/移流損失を粗視化した項。


def _cfl_subcycle_params(D: float, dt: float, dx: float,
                         alpha_max: float) -> tuple[int, float, float]:
    """CFL条件 alpha=D*dt_sub/dx^2 <= alpha_max を満たすsubstep数を求める
    共通helper (H2 / V1.10 C/N/Pで共有。docs/V1.9_検証実装仕様_物理スケール版.md §5,
    docs/V1.10_CNP資源分解_実装仕様.md §5)。"""
    n_sub = max(1, math.ceil(D * dt / (alpha_max * dx * dx)))
    dt_sub = dt / n_sub
    alpha = D * dt_sub / (dx * dx)
    return n_sub, dt_sub, alpha


def _h2_subcycle_params(cfg: Config) -> tuple[int, float, float]:
    return _cfl_subcycle_params(cfg.h2_diffusion_m2s, cfg.dt_seconds,
                                cfg.cell_size, cfg.h2_subcycle_alpha_max)


def _diffuse_h2_physical(h2: np.ndarray, cfg: Config,
                         source_mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    """H2濃度場の1 step分 (dt_seconds) の更新。

    1 stepをCFL条件を満たすsubstep数へ分割し、各substepで
    (1) source cellをDirichlet復元 (2) exchange sink (3) 4近傍拡散、の順に適用する。
    戻り値: (新しい濃度場, source復元量[mol], exchange loss量[mol])。
    """
    n_sub, dt_sub, alpha = _h2_subcycle_params(cfg)
    voxel_volume = cfg.cell_size * cfg.cell_size * cfg.effective_depth_m
    tau = cfg.h2_exchange_tau_s
    c_source = cfg.h2_source_concentration_molm3
    c = h2
    source_in_mol = 0.0
    exchange_loss_mol = 0.0
    for _ in range(n_sub):
        if np.any(source_mask):
            deficit = c_source - c[source_mask]
            source_in_mol += float(deficit.sum()) * voxel_volume
            c = c.copy()
            c[source_mask] = c_source
        loss = c * (dt_sub / tau)
        exchange_loss_mol += float(loss.sum()) * voxel_volume
        c = c - loss
        padded = np.pad(c, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * c)
        c = c + alpha * lap
    return c, source_in_mol, exchange_loss_mol


_H2_WARMUP_ITERS_PHYSICAL = 3000  # 物理modeの定常場warm-up反復数 (RNG不使用)


def _equilibrium_h2_physical(cfg: Config, source_mask: np.ndarray,
                             shape: tuple[int, int]) -> np.ndarray:
    """物理modeでの生物不在H2定常場をdeterministicに求める。RNGは使わない。"""
    h2 = np.zeros(shape)
    for _ in range(_H2_WARMUP_ITERS_PHYSICAL):
        h2, _, _ = _diffuse_h2_physical(h2, cfg, source_mask)
    return h2


# --- V1.10.1: dynamic hydrothermal vent (docs/V1.10.1_動的熱水噴出口_実装方針.md) ---
#
# h2_source_mode="dirichlet" (既定) では上記の既存コードのみを使い、以下は
# 一切呼ばれない。"flux"のときだけ、source cellを固定mol/s供給の
# finite-flux vent (1 vent = 1 cell) として扱う。vent位置はharnessが
# `World.configure_flux_vents()` で明示的に与える (Exp15/16/17の
# `set_sources()` patternを踏襲)。

# turnover scheduleは決定的にrun開始時へ一括precomputeする (docs §6)。
# 200 events * 48h ≈ 400日分の余裕を持たせ、formal Exp18 (最長20日) を
# 十分カバーする。
_TURNOVER_SCHEDULE_EVENTS = 200


def _diffuse_h2_flux_physical(
    h2: np.ndarray, cfg: Config, positions: list[tuple[int, int]],
    flux_per_vent: np.ndarray,
) -> tuple[np.ndarray, float, float]:
    """finite-flux H2 sourceの1 step分 (dt_seconds) の更新。

    1 stepをCFL条件を満たすsubstep数へ分割し、各substepで
    (1) source injection (2) exchange sink (3) 4近傍拡散、の順に適用する
    (docs §2)。Dirichlet復元と異なり供給量はsource cellの現在濃度に
    依存しない (生物消費に応じてsourceが自動増量しない、が意図した差)。
    濃度上限はclampしない。戻り値: (新しい濃度場, source注入量[mol],
    exchange loss量[mol])。
    """
    n_sub, dt_sub, alpha = _h2_subcycle_params(cfg)
    voxel_volume = cfg.cell_size * cfg.cell_size * cfg.effective_depth_m
    tau = cfg.h2_exchange_tau_s
    c = h2
    source_in_mol = 0.0
    exchange_loss_mol = 0.0
    has_vents = len(positions) > 0
    if has_vents:
        idx_x = np.fromiter((p[0] for p in positions), dtype=int, count=len(positions))
        idx_y = np.fromiter((p[1] for p in positions), dtype=int, count=len(positions))
    for _ in range(n_sub):
        if has_vents:
            delta_n_mol = flux_per_vent * dt_sub
            c = c.copy()
            c[idx_x, idx_y] = c[idx_x, idx_y] + delta_n_mol / voxel_volume
            source_in_mol += float(delta_n_mol.sum())
        loss = c * (dt_sub / tau)
        exchange_loss_mol += float(loss.sum()) * voxel_volume
        c = c - loss
        padded = np.pad(c, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * c)
        c = c + alpha * lap
    return c, source_in_mol, exchange_loss_mol


def _vent_flux_schedule(cfg: Config, t: float, n_vents: int) -> np.ndarray:
    """時刻tにおける各vent slotの供給flux [mol/s] (docs §5)。

    `h2_vent_temporal_enabled=False` なら全vent常時 `h2_vent_flux_mol_s`。
    Trueなら"paired_staggered": slot 0,1が周期前半、slot 2,3が後半でON
    (n_vents=4前提、Config.__post_init__で検証済み)。ON中は
    `h2_vent_on_flux_multiplier`倍、OFF中は0。duty_fraction=0.5・
    on_flux_multiplier=2.0のformal設定では常に2 ventがONで瞬間総fluxが
    static controlと一致する (docs §5)。
    """
    base = cfg.h2_vent_flux_mol_s
    flux = np.full(n_vents, base, dtype=float)
    if not cfg.h2_vent_temporal_enabled:
        return flux
    period = cfg.h2_vent_cycle_period_s
    half = period * cfg.h2_vent_duty_fraction
    phase = t % period
    first_half_active = phase < half
    on_value = base * cfg.h2_vent_on_flux_multiplier
    for i in range(n_vents):
        in_first_group = i in (0, 1)
        active = in_first_group == first_half_active
        flux[i] = on_value if active else 0.0
    return flux


def _pick_relocation_position(
    env_rng: np.random.Generator, gw: int, gh: int,
    keep_positions: list[tuple[int, int]], min_separation_cells: int,
) -> tuple[int, int]:
    """turnoverで別セルへrelocateする新しいvent位置を1つ選ぶ (docs §6)。

    候補は決定的な順序 (行優先) で構築し、world端から1 cell以上内側、かつ
    残っている他ventとの距離が `min_separation_cells` を超えるものだけを
    残す。その中からenvironment RNGで一様に選ぶ (`_place_vents`と同じ
    決定的候補+RNG選択pattern)。
    """
    min_sep2 = min_separation_cells * min_separation_cells
    candidates = [
        (x, y) for x in range(1, gw - 1) for y in range(1, gh - 1)
        if all((x - ox) ** 2 + (y - oy) ** 2 > min_sep2 for ox, oy in keep_positions)
    ]
    if not candidates:
        raise ValueError(
            "turnover: h2_vent_min_separation_cells / world sizeに対して "
            "relocation候補セルがありません。")
    idx = int(env_rng.integers(0, len(candidates)))
    return candidates[idx]


def _precompute_turnover_schedule(
    cfg: Config, env_rng: np.random.Generator,
    initial_positions: list[tuple[int, int]],
) -> list[dict]:
    """turnover eventを`_TURNOVER_SCHEDULE_EVENTS`件、run開始時に一括生成する。

    各eventは {event_index, time_s, slot, position}。同一seed/configで
    完全再現可能 (env_rngだけを消費し、organism側RNG列には触れない)。
    turnover対象slotはindex順にrotationする (docs §6)。
    """
    positions = list(initial_positions)
    n = len(positions)
    count = cfg.h2_vent_turnover_count
    interval = cfg.h2_vent_turnover_interval_s
    events: list[dict] = []
    next_slot = 0
    for event_index in range(1, _TURNOVER_SCHEDULE_EVENTS + 1):
        t = event_index * interval
        retiring = [(next_slot + k) % n for k in range(count)]
        for slot in retiring:
            keep = [p for i, p in enumerate(positions) if i != slot]
            new_pos = _pick_relocation_position(
                env_rng, cfg.grid_w, cfg.grid_h, keep, cfg.h2_vent_min_separation_cells)
            positions[slot] = new_pos
            events.append({"event_index": event_index, "time_s": t,
                          "slot": slot, "position": new_pos})
        next_slot = (next_slot + count) % n
    return events


# --- V1.10: C/N/P resource fields (docs/V1.10_CNP資源分解_実装仕様.md §5) ---
#
# H2と異なり、C/N/PはDirichlet source cellを持たない。world全体が
# uniform background reservoir (海水由来) とtimescale tauで交換する
# (dC/dt=(background-C)/tau)。生物不在の定常場は解析的にbackground濃度
# そのものなので、H2のようなwarm-up反復は不要 (乱数も使わない)。


def _diffuse_cnp_field_physical(c: np.ndarray, cfg: Config, D: float, tau: float,
                                background: float) -> tuple[np.ndarray, float, float]:
    """C/N/P 1資源場の1 step分 (dt_seconds) の更新。

    1 stepをCFL条件を満たすsubstep数へ分割し、各substepで
    (1) background exchange (2) 4近傍拡散、の順に適用する。
    `cfg.cnp_background_exchange_enabled=False` ならexchangeをskipし
    (closed-system mechanical test用)、拡散だけで総量厳密保存になる。
    戻り値: (新しい濃度場, exchange流入量[mol], exchange流出量[mol])。
    """
    n_sub, dt_sub, alpha = _cfl_subcycle_params(
        D, cfg.dt_seconds, cfg.cell_size, cfg.cnp_subcycle_alpha_max)
    voxel_volume = cfg.cell_size * cfg.cell_size * cfg.effective_depth_m
    exchange_in_mol = 0.0
    exchange_out_mol = 0.0
    for _ in range(n_sub):
        if cfg.cnp_background_exchange_enabled and tau > 0.0:
            delta = (background - c) * (dt_sub / tau)
            pos = delta[delta > 0.0]
            neg = delta[delta < 0.0]
            exchange_in_mol += float(pos.sum()) * voxel_volume
            exchange_out_mol += float(-neg.sum()) * voxel_volume
            c = c + delta
        padded = np.pad(c, 1, mode="edge")
        lap = (padded[:-2, 1:-1] + padded[2:, 1:-1]
               + padded[1:-1, :-2] + padded[1:-1, 2:] - 4.0 * c)
        c = c + alpha * lap
    return c, exchange_in_mol, exchange_out_mol


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
        # voxel体積 [m^3] (physical_modeのH2 concentration<->amount変換用)。
        self.voxel_volume_m3 = cfg.cell_size * cfg.cell_size * cfg.effective_depth_m
        # V1.10.1: dynamic vent state (docs/V1.10.1_動的熱水噴出口_実装方針.md)。
        # h2_source_mode="dirichlet" (既定) では以下を一切使わない。
        self.vent_slot_positions: list[tuple[int, int]] = []
        self._turnover_events: list[dict] = []
        self._turnover_applied_idx = 0
        self.vent_turnover_count_cum = 0
        self._elapsed_s = 0.0
        self.h2_source_mode = cfg.h2_source_mode

        if cfg.physical_mode and cfg.h2_source_mode == "flux":
            # finite-flux mode: legacy disk-based Dirichlet warm-upは行わない
            # (docs §3: 旧13-cell disk sourceをformal V1.10.1へ混ぜない)。
            # 初期fieldはゼロで構築し、harnessが`configure_flux_vents()`
            # (vent位置決定) と、必要ならt=0 common field (docs §7) を
            # `world.h2 = ...` で明示的に設定する。
            self.h2 = np.zeros((gw, gh))
            # organism RNG列を消費しない独立streamからenvironment RNGを作る
            # (docs §6: RNG isolation)。SeedSequence.spawn()はrngが既に
            # 消費した乱数個数と無関係に、そのrngの root seed からの
            # 決定的な子streamを返す。
            env_seed_seq = rng.bit_generator.seed_seq.spawn(1)[0]
            self.env_rng = np.random.Generator(np.random.PCG64(env_seed_seq))
        elif cfg.physical_mode:
            # physical_mode: h2はconcentration場 [mol/m^3]。source cellは
            # Dirichlet境界 (docs/V1.9_検証実装仕様_物理スケール版.md §5-6)。
            self.h2 = _equilibrium_h2_physical(cfg, self.h2_mask, (gw, gh))
        else:
            # 初期stockはdeterministicなfixed-point iterationで求める
            # (生物不在・RNG不使用。docs/V1.9_iLUCA再設計仕様.md §10.2)。
            self.h2 = _equilibrium_h2(self.h2_source_flux, cfg.h2_loss_frac, cfg.h2_diffusion)

        # --- V1.10: C/N/P resource fields (docs/V1.10_CNP資源分解_実装仕様.md §1/5) ---
        # explicit_cnp_resources=Falseでは一切生成しない (既存V1.9経路に
        # 影響を与えない)。Dirichlet sourceを持たないため、生物不在の定常場は
        # 解析的にbackground濃度そのもの (RNG不使用・warm-up不要)。
        if cfg.explicit_cnp_resources:
            self.dic = np.full((gw, gh), cfg.dic_background_molm3)
            self.fixed_nitrogen = np.full((gw, gh), cfg.fixed_n_background_molm3)
            self.phosphate = np.full((gw, gh), cfg.phosphate_background_molm3)

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

    # --- V1.10.1: dynamic vent geometry (docs/V1.10.1_動的熱水噴出口_実装方針.md) ---

    def configure_flux_vents(self, positions: list[tuple[int, int]]) -> None:
        """finite-flux vent位置を設定する (h2_source_mode="flux"専用)。

        Exp15/16/17の`set_sources()`と同じ「World構築後にharnessが明示的に
        geometryを与える」patternを踏襲する。`h2_vent_turnover_enabled`なら
        ここでturnover scheduleを一括precomputeする (docs §6: 同一seed/
        configで完全再現、environment RNGだけを消費)。観測用の
        `vent_centers`/`h2_mask`/`vent_band`もこの時点の位置で更新する。
        """
        cfg = self.cfg
        if cfg.h2_source_mode != "flux":
            raise ValueError("configure_flux_vents() は h2_source_mode='flux' 専用です。")
        positions = [(int(x), int(y)) for x, y in positions]
        if len(positions) != cfg.n_vents:
            raise ValueError(
                f"positions数 ({len(positions)}) が n_vents ({cfg.n_vents}) と一致しません。")
        self.vent_slot_positions = positions
        self._initial_vent_positions = tuple(positions)
        self._turnover_applied_idx = 0
        self.vent_turnover_count_cum = 0
        if cfg.h2_vent_turnover_enabled:
            self._turnover_events = _precompute_turnover_schedule(
                cfg, self.env_rng, positions)
        else:
            self._turnover_events = []
        self._refresh_vent_observation_fields()

    def _refresh_vent_observation_fields(self) -> None:
        """現在のvent_slot_positionsから観測用field (vent_centers/h2_mask/
        vent_band/h2_source_total) を再構築する。turnoverでvent位置が
        変わった時だけ呼ぶ (毎step呼ぶには重すぎる粗視化)。"""
        gw, gh = self.cfg.grid_w, self.cfg.grid_h
        positions = self.vent_slot_positions
        self.vent_centers = list(positions)
        mask = np.zeros((gw, gh), dtype=bool)
        for ix, iy in positions:
            mask[ix, iy] = True
        self.h2_mask = mask
        self.vent_band = np.full((gw, gh), len(VENT_BAND_EDGES), dtype=np.int8)
        if positions:
            ii, jj = np.meshgrid(np.arange(gw), np.arange(gh), indexing="ij")
            d = np.full((gw, gh), np.inf)
            for vx, vy in positions:
                d = np.minimum(d, np.hypot(ii - vx, jj - vy))
            self.vent_band = np.digitize(d, VENT_BAND_EDGES).astype(np.int8)
        # flux modeの"nominal" total (temporal ON/OFFは考慮しないbaseline)。
        # 瞬間値は vent_state() で得る。
        self.h2_source_total = float(self.cfg.h2_vent_flux_mol_s * len(positions))

    def _apply_turnover_up_to(self, t: float) -> None:
        """時刻tまでに発生したturnover eventを適用し、vent位置を更新する。"""
        events = self._turnover_events
        idx = self._turnover_applied_idx
        changed = False
        while idx < len(events) and events[idx]["time_s"] <= t:
            ev = events[idx]
            self.vent_slot_positions[ev["slot"]] = ev["position"]
            self.vent_turnover_count_cum += 1
            idx += 1
            changed = True
        self._turnover_applied_idx = idx
        if changed:
            self._refresh_vent_observation_fields()

    def current_vent_flux_mol_s(self, t: float | None = None) -> np.ndarray:
        """時刻tでの各vent slotの供給flux [mol/s] (docs §5)。"""
        if t is None:
            t = self._elapsed_s
        return _vent_flux_schedule(self.cfg, t, len(self.vent_slot_positions))

    def vent_state(self, t: float | None = None) -> dict:
        """V1.10.1観測: vent state (docs §9)。h2_source_mode="flux"専用。"""
        if t is None:
            t = self._elapsed_s
        flux = self.current_vent_flux_mol_s(t)
        return {
            "active_vent_count": int((flux > 0.0).sum()),
            "vent_positions": [list(p) for p in self.vent_slot_positions],
            "per_vent_flux_mol_s": flux.tolist(),
            "world_source_flux_mol_s": float(flux.sum()),
            "vent_turnover_count_cum": self.vent_turnover_count_cum,
        }

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
        self._elapsed_s += cfg.dt_seconds
        if cfg.physical_mode and cfg.h2_source_mode == "flux":
            # V1.10.1: finite-flux vent (docs/V1.10.1_動的熱水噴出口_実装方針.md §2/5/6)。
            # turnoverはstep粒度で適用 (48hは十分dt=10sより粗いため、
            # substep単位では追跡しない)。
            if cfg.h2_vent_turnover_enabled:
                self._apply_turnover_up_to(self._elapsed_s)
            flux_per_vent = self.current_vent_flux_mol_s(self._elapsed_s)
            self.h2, h2_influx, h2_loss = _diffuse_h2_flux_physical(
                h2_before, cfg, self.vent_slot_positions, flux_per_vent)
        elif cfg.physical_mode:
            self.h2, h2_influx, h2_loss = _diffuse_h2_physical(
                h2_before, cfg, self.h2_mask)
        else:
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

    def update_cnp(self) -> dict[str, float]:
        """V1.10: C/N/P 3 fieldのbackground exchange + 拡散 (1 dt_seconds分)。

        H2と分離した独立メソッドにする理由: `update()` の戻り値型
        (h2_influx, h2_loss) を変えると既存呼び出し・testに影響するため。
        `cfg.explicit_cnp_resources=True` のときだけ呼ばれる想定
        (docs/V1.10_CNP資源分解_実装仕様.md §5)。
        """
        cfg = self.cfg
        self.dic, c_in, c_out = _diffuse_cnp_field_physical(
            self.dic, cfg, cfg.d_dic_m2s, cfg.cnp_exchange_tau_s, cfg.dic_background_molm3)
        self.fixed_nitrogen, n_in, n_out = _diffuse_cnp_field_physical(
            self.fixed_nitrogen, cfg, cfg.d_fixed_n_m2s, cfg.cnp_exchange_tau_s,
            cfg.fixed_n_background_molm3)
        self.phosphate, p_in, p_out = _diffuse_cnp_field_physical(
            self.phosphate, cfg, cfg.d_phosphate_m2s, cfg.cnp_exchange_tau_s,
            cfg.phosphate_background_molm3)
        return {"c_in": c_in, "c_out": c_out, "n_in": n_in, "n_out": n_out,
               "p_in": p_in, "p_out": p_out}

    # --- 集計 (保存則検証・統計用) ---

    def total_nutrients(self) -> float:
        return float(self.nutrients.sum())

    def total_h2(self) -> float:
        """総H2量。physical_modeではh2はconcentration [mol/m^3] なので
        voxel体積を掛けてamount [mol] へ変換する。"""
        if self.cfg.physical_mode:
            return float(self.h2.sum()) * self.voxel_volume_m3
        return float(self.h2.sum())

    def total_dic(self) -> float:
        """総DIC量 [mol]。concentration場にvoxel体積を掛けて変換する。"""
        return float(self.dic.sum()) * self.voxel_volume_m3

    def total_fixed_nitrogen(self) -> float:
        return float(self.fixed_nitrogen.sum()) * self.voxel_volume_m3

    def total_phosphate(self) -> float:
        return float(self.phosphate.sum()) * self.voxel_volume_m3
