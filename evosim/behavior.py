"""感覚と行動決定 (仕様書 Ver.1.1 §9 / V1.5 異種刺激比較)。

「検出 → 接近、なければランダム探索」のみの意図的に単純なルール。
現在感じる刺激への反射反応だけを扱い、将来のEnergy収益は一切予測しない。

V1.5 (docs/V1.5_異種刺激比較仕様.md):
光はflow (E/tick/cell)、chemicalはstock (E/cell) で単位も範囲も違うため、
raw値の大小で引かれ先を決めるのは混合世界で不適切だった。
一次Energy源同士 (light vs chemical) の比較だけを無次元受容器応答

    response(x, K) = x / (x + K)

へ通し、`ability × response` で1つの候補へ絞る。絞った後で無機栄養・死骸・
捕食と比べる段階は、V1.4と同じ legacy score (`ability × raw値`) を使う。
したがって単独source世界の行動はV1.4と完全に一致する。
"""
from __future__ import annotations

import math

import numpy as np

from .genome import (CHEM_ABS, CORPSE_DIG, LIGHT_ABS, MEMBRANE, MOVE_POWER,
                     NUTRIENT_ABS, PREDATION, SENSORY)

ABILITY_EPS = 1e-3  # これ未満の能力は刺激として無視 (ゼロ能力の空走査を省く)


def response(x: float, half: float) -> float:
    """無次元受容器応答 (V1.5 §3)。0 <= response < 1 で単調増加。

    x=0 → 0 / x=half → 0.5 / x→∞ → 1。raw値が巨大でも無制限に強く感じない。
    未来のEnergy収益ではなく、その瞬間の刺激の強さだけを表す。
    """
    if x <= 0.0:
        return 0.0
    return x / (x + half)


def decide_and_move(org, sim) -> float:
    """1個体の行動決定と移動。戻り値: 実際に移動した速度 [wu/tick]。"""
    cfg = sim.cfg
    world = sim.world
    g = org.genome

    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    e_max = org.energy_max(cfg.energy_capacity)
    matter_cap = cfg.matter_cap_frac * org.target_size

    # 満ち足りていれば待機
    if org.energy >= cfg.satiety_energy_frac * e_max and org.matter >= org.target_size:
        return 0.0

    v_max = cfg.speed_coef * g[MOVE_POWER] / math.sqrt(max(org.matter, 1e-9)) * phi

    # --- 刺激走査 ---
    sense_r = cfg.sense_coef * g[SENSORY]
    best_score = 0.0
    target: tuple[float, float] | None = None
    stay = False  # 現在セルが最良 → 停止して吸収

    ix0, iy0 = world.cell_index(org.x, org.y)
    cr = int(sense_r / cfg.cell_size)
    x_lo, x_hi = max(0, ix0 - cr), min(cfg.grid_w, ix0 + cr + 1)
    y_lo, y_hi = max(0, iy0 - cr), min(cfg.grid_h, iy0 + cr + 1)

    want_energy = org.energy < cfg.satiety_energy_frac * e_max
    want_matter = org.matter < matter_cap

    single_cell = (x_hi - x_lo) == 1 and (y_hi - y_lo) == 1
    best_kind = None

    def _scan(arr) -> tuple[int, float]:
        """走査範囲内の最良セル (flat index, raw値)。V1.4と同一の探索。"""
        if single_cell:
            # 感覚半径がセル1個に収まる場合 (初期個体はこれに該当)。
            # numpy の argmax / flat イテレータは呼び出し overhead が大きいため、
            # 走査対象が1セルのときは直接読む。結果は完全に同一。
            return 0, float(arr[x_lo, y_lo])
        sub = arr[x_lo:x_hi, y_lo:y_hi]
        flat = int(np.argmax(sub))
        return flat, float(sub[flat // sub.shape[1], flat % sub.shape[1]])

    def _is_current(flat: int) -> bool:
        bi, bj = divmod(flat, y_hi - y_lo)
        return (x_lo + bi, y_lo + bj) == (ix0, iy0)

    def _consider(flat: int, score: float, kind: str) -> None:
        """legacy score (ability × raw値) での採用判定。V1.4と同一。"""
        nonlocal best_score, target, stay, best_kind
        if score > best_score:
            bi, bj = divmod(flat, y_hi - y_lo)
            cx, cy = world.cell_center(x_lo + bi, y_lo + bj)
            best_score = score
            best_kind = kind
            if (x_lo + bi, y_lo + bj) == (ix0, iy0):
                stay = True
                target = None
            else:
                stay = False
                target = (cx, cy)

    # 無機栄養 (V1.5では比較則を変更しない。評価順もV1.4と同じ)
    if g[NUTRIENT_ABS] > ABILITY_EPS and want_matter:
        flat, val = _scan(world.nutrients)
        _consider(flat, g[NUTRIENT_ABS] * val, "nutrient")

    # 一次Energy源 (V1.5): light と chemical を独立に抽出し、
    # 無次元受容器応答で1つへ絞ってから legacy score で他刺激と比べる。
    lc = _scan(world.light) if (want_energy and g[LIGHT_ABS] > ABILITY_EPS) else None
    cc = _scan(world.chemical) if (want_energy and g[CHEM_ABS] > ABILITY_EPS) else None
    obs = sim.stim_obs
    energy_kind: str | None = None
    energy_flat = 0
    energy_score = 0.0
    if lc is not None and cc is not None:
        r_l = response(lc[1], cfg.light_stimulus_half)
        r_c = response(cc[1], cfg.chemical_stimulus_half)
        s_l = g[LIGHT_ABS] * r_l
        s_c = g[CHEM_ABS] * r_c
        obs["both_events"] += 1
        obs["light_resp_sum"] += r_l
        obs["chem_resp_sum"] += r_c
        obs["chem_stock_sum"] += cc[1]
        if s_l <= 0.0 and s_c <= 0.0:
            # 両方0: V1.4でも方向付けは起きない (score 0 は best_score を超えない)
            pass
        elif abs(s_l - s_c) <= cfg.stimulus_tie_eps:
            # 同点: source種別で固定優先しない。現在セルが候補ならその場に留まり、
            # どちらも別セルならEnergy源による方向付けをしない (V1.5 §7)。
            obs["tie"] += 1
            cur_l, cur_c = _is_current(lc[0]), _is_current(cc[0])
            if cur_l or cur_c:
                # 向かう先は同じ (現在セル) なので、legacy scoreが大きい方で評価する
                cand = []
                if cur_l:
                    cand.append(("light", lc[0], g[LIGHT_ABS] * lc[1]))
                if cur_c:
                    cand.append(("chemical", cc[0], g[CHEM_ABS] * cc[1]))
                energy_kind, energy_flat, energy_score = max(cand, key=lambda t: t[2])
        elif s_l > s_c:
            energy_kind, energy_flat, energy_score = "light", lc[0], g[LIGHT_ABS] * lc[1]
            obs["light"] += 1
            obs["agree"] += 1
        else:
            energy_kind, energy_flat, energy_score = "chemical", cc[0], g[CHEM_ABS] * cc[1]
            obs["chemical"] += 1
            obs["agree"] += 1
    elif lc is not None:
        energy_kind, energy_flat, energy_score = "light", lc[0], g[LIGHT_ABS] * lc[1]
        if energy_score > 0.0:
            obs["light"] += 1
    elif cc is not None:
        energy_kind, energy_flat, energy_score = "chemical", cc[0], g[CHEM_ABS] * cc[1]
        if energy_score > 0.0:
            obs["chemical"] += 1
    if energy_kind is not None:
        _consider(energy_flat, energy_score, energy_kind)

    # 死骸
    if g[CORPSE_DIG] > ABILITY_EPS:
        for cell in _cells(sim.corpse_hash, x_lo, x_hi, y_lo, y_hi):
            for c in cell:
                if c.matter <= 0.0:
                    continue
                if _dist2(org.x, org.y, c.x, c.y) > sense_r * sense_r:
                    continue
                score = g[CORPSE_DIG] * c.matter
                if score > best_score:
                    best_score = score
                    best_kind = "corpse"
                    target = (c.x, c.y)
                    stay = False

    # 他個体 (捕食対象)。膜を破れる見込みがある相手のみ追跡する。
    if g[PREDATION] > ABILITY_EPS:
        my_attack = cfg.attack_coef * g[PREDATION] * org.matter * phi
        for cell in _cells(sim.org_hash, x_lo, x_hi, y_lo, y_hi):
            for other in cell:
                if other is org or not other.alive:
                    continue
                if _dist2(org.x, org.y, other.x, other.y) > sense_r * sense_r:
                    continue
                defense = cfg.defense_coef * other.genome[MEMBRANE] * other.matter
                if my_attack <= defense:
                    continue
                score = g[PREDATION] * other.matter
                if score > best_score:
                    best_score = score
                    best_kind = "predation"
                    target = (other.x, other.y)
                    stay = False

    # 一次Energy候補が他刺激に負けた回数 (観測専用・V1.5)
    if energy_kind is not None and energy_score > 0.0 and best_kind != energy_kind:
        obs["lost_" + energy_kind] += 1

    # --- 移動 ---
    if stay or v_max <= 0.0:
        return 0.0
    if target is not None:
        dx, dy = target[0] - org.x, target[1] - org.y
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            return 0.0
        org.heading = math.atan2(dy, dx)
        v = min(v_max, dist)
    else:
        # ランダムウォーク
        obs["walk"] += 1
        org.heading += sim.rng.normal(0.0, cfg.wander_turn_sigma)
        v = v_max * cfg.wander_speed_frac

    org.x += math.cos(org.heading) * v
    org.y += math.sin(org.heading) * v
    r = org.radius(cfg.radius_coef)
    org.x = min(max(org.x, r), cfg.world_width - r)
    org.y = min(max(org.y, r), cfg.world_height - r)
    return v


def _cells(hash_map: dict, x_lo: int, x_hi: int, y_lo: int, y_hi: int):
    for ix in range(x_lo, x_hi):
        for iy in range(y_lo, y_hi):
            cell = hash_map.get((ix, iy))
            if cell:
                yield cell


def _dist2(x1: float, y1: float, x2: float, y2: float) -> float:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2
