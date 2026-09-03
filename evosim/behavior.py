"""感覚と行動決定 (仕様書 Ver.1.1 §9 / V1.6 temporal biased random walk)。

現在感じる刺激への反射反応だけを扱い、将来のEnergy収益は一切予測しない。

V1.6 (docs/V1.6_行動則設計案.md):
一次Energy (light / chemical) について、「周囲の最良セルを探して向かう」
winner-take-all を**廃止する**。代わりに現在地で感じる刺激の時間変化だけで
既存random walkの曲がり幅を変える。

    R_light = response(light,     light_stimulus_half)     知覚は双線形補間
    R_chem  = response(chemical,  chemical_stimulus_half)
    Q       = (aL*R_light + aC*R_chem) / (aL + aC)         能力加重平均
    dQ      = Q_now - Q_memory                             EMA との差
    sigma_eff = wander_turn_sigma * 2/(1 + exp(gain * dQ))

dQ > 0 (改善中) なら曲がりにくく、dQ < 0 (悪化中) なら曲がりやすい。
**dQ からどちらへ行くべきかは求めない。** 向きは常にrandom walkのまま。

なぜ知覚を補間するか (docs/V1.6_Exp10_レビュー.md A-2):
field はセル内一定なので、そのまま読むと同じセルに留まる約24 tickの間
dQ が厳密に0になり、時間比較が原理的に働かない。知覚だけ空間連続にする。
吸収・供給・損失はV1.5以前のままセル単位である。

V1.6のスコープは一次Energyのみ (仕様 §2.7)。無機栄養・死骸・捕食の
直接ターゲティングは既知の非対称として当面そのまま残す。
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

    # want_energy はV1.6では使わない。満腹判定は上の早期returnで済んでいる。
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

    # --- 一次Energy (V1.6): temporal sensing ---
    # 候補セルを探さない。現在地の知覚から Q を作り、短期記憶との差 dQ で
    # random walk の曲がり幅だけを変える (仕様 §2.1-2.5)。
    # target は設定しない = 一次EnergyによるWTAターゲティングの廃止。
    obs = sim.stim_obs
    use_light = g[LIGHT_ABS] > ABILITY_EPS
    use_chem = g[CHEM_ABS] > ABILITY_EPS

    # V1.8: light sensingはそのtickの実効光 (base field × daylight_factor)
    # を読む。night (factor=0) では厳密に R_light=0。chemicalはcurrent
    # stockをそのまま読むためnightでも利用可能 (仕様§8)。
    effective_light = (world.sample(world.light, org.x, org.y)
                       * sim.daylight_factor_now)
    r_l = response(effective_light, cfg.light_stimulus_half) if use_light else 0.0
    r_c = (response(world.sample(world.chemical, org.x, org.y),
                    cfg.chemical_stimulus_half) if use_chem else 0.0)

    # 能力加重平均。能力の絶対値ではなく「どちらを重視するか」だけがQを決める
    # (全能力を同率で倍にしてもQは不変。V1.6 §2.3 / レビュー B-1)。
    w_sum = (g[LIGHT_ABS] if use_light else 0.0) + (g[CHEM_ABS] if use_chem else 0.0)
    if w_sum > 0.0:
        w_l = (g[LIGHT_ABS] / w_sum) if use_light else 0.0
        w_c = (g[CHEM_ABS] / w_sum) if use_chem else 0.0
        q_now = w_l * r_l + w_c * r_c
    else:
        w_l = w_c = 0.0
        q_now = 0.0

    if not org.has_stim_memory:
        # 初回は人工的な差分を作らない (仕様 §2.4)
        org.r_light_mem = r_l
        org.r_chem_mem = r_c
        org.has_stim_memory = True
        d_l = d_c = 0.0
    else:
        d_l = w_l * (r_l - org.r_light_mem)
        d_c = w_c * (r_c - org.r_chem_mem)
    delta_q = d_l + d_c
    q_mem = w_l * org.r_light_mem + w_c * org.r_chem_mem

    # EMA更新。alpha = 1 - exp(-1/tau)
    alpha = sim.stim_alpha
    org.r_light_mem += alpha * (r_l - org.r_light_mem)
    org.r_chem_mem += alpha * (r_c - org.r_chem_mem)

    # 曲がり幅の変調係数。dQ>0 で <1 (直進しやすい)、dQ<0 で >1 (曲がりやすい)。
    # 2/(1+exp(z)) は (0, 2) に収まり、gain*dQ が極端でも発散しない。
    z = cfg.response_gain * delta_q
    if z > 700.0:        # exp のオーバーフロー回避。数学的な極限は 0
        turn_factor = 0.0
    elif z < -700.0:
        turn_factor = 2.0
    else:
        turn_factor = 2.0 / (1.0 + math.exp(z))

    # 観測 (RNG非消費・行動へ非フィードバック)
    band = int(world.vent_band[ix0, iy0])
    obs["band_n"][band] += 1
    obs["band_dq_light"][band] += d_l
    obs["band_dq_chem"][band] += d_c
    obs["band_sigma_eff"][band] += cfg.wander_turn_sigma * turn_factor
    obs["stim_events"] += 1
    obs["q_sum"] += q_now
    obs["q_mem_sum"] += q_mem
    obs["dq_sum"] += delta_q
    obs["dq_abs_sum"] += abs(delta_q)
    obs["dq_light_sum"] += d_l
    obs["dq_chem_sum"] += d_c
    obs["turn_factor_sum"] += turn_factor
    obs["sigma_eff_sum"] += cfg.wander_turn_sigma * turn_factor
    obs["r_light_sum"] += r_l
    obs["r_chem_sum"] += r_c
    if delta_q > 0.0:
        obs["dq_pos"] += 1
        obs["turn_factor_pos_sum"] += turn_factor
    elif delta_q < 0.0:
        obs["dq_neg"] += 1
        obs["turn_factor_neg_sum"] += turn_factor
    else:
        obs["dq_zero"] += 1

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
        # V1.6: dQ で曲がり幅を変調した biased random walk。
        # 向きは決めない。sigma_eff を変えるだけ (仕様 §2.5)。
        obs["walk"] += 1
        sigma_eff = cfg.wander_turn_sigma * turn_factor
        if sigma_eff > 0.0:
            org.heading += sim.rng.normal(0.0, sigma_eff)
        else:
            # sigma=0 は rng.normal がRNGを消費するかどうかを実装依存にしない
            # ため明示的に扱う。乱数消費は常に1回で揃える。
            org.heading += sim.rng.normal(0.0, 1.0) * 0.0
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
