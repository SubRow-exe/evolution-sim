"""Exp10 Phase A — V1.6 temporal biased random walk の軽量診断arena。

    uv run python tools/arena_exp10.py --out runs/exp10_phaseA
    uv run python tools/arena_exp10.py --quick        # 動作確認用の小規模

`docs/Exp10_実験計画案.md` §4 の「移動専用診断環境」。

通常の生態simulationではない。死亡・繁殖・吸収・生理を**すべて止め**、
行動則だけを走らせる。production worldへ診断専用の特殊環境を恒久追加しない
ためでもある (計画 §4 / レビュー C-1)。

呼ぶのは実装そのものの `behavior.decide_and_move` なので、
ここで測るのは本番と同じ行動コードである。

## 環境 (§4.1)

値は「セル添字が増える向き」で定義する。世界のy=0は北 (上)。

    K0 uniform      light一定 / chemical一定        偽bias検出
    K1 light-Y      lightのみ +Y方向へ増加
    K2 chemical-X   chemicalのみ +X方向へ増加
    K3 orthogonal   lightは +Y、chemicalは +X       直交
    K4 conflict     lightは +Y、chemicalは -Y       逆向き

chemicalの振れ幅は `chemical_stimulus_half` の2倍 (24.6) までとする。
中央で応答0.5になり、受容器の効く範囲を素通りしないため。
本番世界のstock水準とは別物であり、Phase Bで実世界の水準を見る。

## high-Q領域の定義

計画に定義が無いので、ここで固定して事前登録扱いにする。

> その表現型のQを全セルで計算し、**上位25%のセル**をhigh-Q領域とする。

面積で定義するので、環境ごと表現型ごとに「同じ広さの当たり領域」になり、
条件間で滞在率を直接比較できる。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from evosim import behavior
from evosim.config import Config
from evosim.genome import (CHEM_ABS, LIGHT_ABS, MOVE_EFF, MOVE_POWER, N_GENES,
                           SENSORY)
from evosim.organism import Organism
from evosim.simulation import Simulation

# 診断表現型 (Exp09と同一。計画 §4.2)
PHENOTYPES = {
    "lightspec": (2.0, 0.3),
    "chemspec": (0.3, 2.0),
    "generalist": (1.0, 1.0),
}
ENVIRONMENTS = ("K0_uniform", "K1_light_Y", "K2_chem_X",
                "K3_orthogonal", "K4_conflict")

# 計画 §4.3 のパラメータ候補
MEMORY_TAUS = (3.0, 10.0, 30.0)
RESPONSE_GAINS = (4.0, 16.0, 64.0, 256.0)
CONTROL_GAIN = 0.0        # pure random walk control

LIGHT_MAX = 1.2           # 本番世界の最大セル光量に合わせる
CHEM_MAX = 24.6           # chemical_stimulus_half の2倍


def build_fields(env: str, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """(light, chemical) を返す。どちらも [ix, iy]。"""
    gw, gh = cfg.grid_w, cfg.grid_h
    ramp_y = np.tile(np.linspace(0.0, 1.0, gh), (gw, 1))          # +Y で増加
    ramp_x = np.tile(np.linspace(0.0, 1.0, gw), (gh, 1)).T        # +X で増加
    half = np.full((gw, gh), 0.5)
    if env == "K0_uniform":
        return LIGHT_MAX * half, CHEM_MAX * half
    if env == "K1_light_Y":
        return LIGHT_MAX * ramp_y, np.zeros((gw, gh))
    if env == "K2_chem_X":
        return np.zeros((gw, gh)), CHEM_MAX * ramp_x
    if env == "K3_orthogonal":
        return LIGHT_MAX * ramp_y, CHEM_MAX * ramp_x
    if env == "K4_conflict":
        return LIGHT_MAX * ramp_y, CHEM_MAX * (1.0 - ramp_y)
    raise ValueError(env)


def q_field(light: np.ndarray, chem: np.ndarray, la: float, ca: float,
            cfg: Config) -> np.ndarray:
    """各セルのQ (能力加重平均)。high-Q領域の判定に使う。"""
    r_l = light / (light + cfg.light_stimulus_half)
    r_c = chem / (chem + cfg.chemical_stimulus_half)
    w = la + ca
    return (la * r_l + ca * r_c) / w


def make_arena(env: str, pheno: str, seed: int, n_org: int,
               memory_tau: float, response_gain: float) -> Simulation:
    la, ca = PHENOTYPES[pheno]
    cfg = Config(initial_population=0, light_pattern="uniform", light_max=0.0,
                 chem_vent_flux=0.0, nutrient_initial=0.0,
                 memory_tau=memory_tau, response_gain=response_gain,
                 stats_interval=0, snapshot_interval=0)
    sim = Simulation(cfg, seed)
    light, chem = build_fields(env, cfg)
    sim.world.light = light
    sim.world.chemical = chem
    sim.world.nutrients = np.zeros_like(light)

    # 個体を一様ランダムに配置する。位置と初期headingのみ乱数を使う。
    rng = sim.rng
    g = np.zeros(N_GENES)
    g[0] = 1.0                # body_size
    g[MOVE_POWER] = 0.5       # Exp09の実現値中央付近
    g[MOVE_EFF] = 1.0
    g[SENSORY] = 0.4          # 一次Energyでは使われない。実現値を入れておく
    g[LIGHT_ABS] = la
    g[CHEM_ABS] = ca
    for i in range(n_org):
        x = float(rng.uniform(0.0, cfg.world_width))
        y = float(rng.uniform(0.0, cfg.world_height))
        h = float(rng.uniform(-math.pi, math.pi))
        o = Organism(i, -1, i, 0, 0, g.copy(), x, y, h, 0.0, 1.0)
        # 生理を止めるので、満腹stopに掛からない一定Energyを与え続ける
        o.energy = 0.5 * o.energy_max(cfg.energy_capacity)
        sim.organisms.append(o)
    sim.next_id = n_org
    sim._build_hashes()
    return sim


def run_arena(env: str, pheno: str, seed: int, memory_tau: float,
              response_gain: float, ticks: int, n_org: int,
              track_out: Path | None = None, track_n: int = 12,
              track_every: int = 10) -> dict:
    la, ca = PHENOTYPES[pheno]
    sim = make_arena(env, pheno, seed, n_org, memory_tau, response_gain)
    cfg = sim.cfg
    qf = q_field(sim.world.light, sim.world.chemical, la, ca, cfg)
    hi_thresh = float(np.quantile(qf, 0.75))    # 上位25%のセル
    e_sat = cfg.satiety_energy_frac

    x0 = np.array([o.x for o in sim.organisms])
    y0 = np.array([o.y for o in sim.organisms])

    hi_ticks = 0
    total_ticks = 0
    path_len = 0.0
    # 図用の軌跡 (観測専用。RNGも行動も変えない)
    tracks: list[list[tuple[float, float]]] = (
        [[] for _ in range(min(track_n, n_org))] if track_out else [])
    acc = {k: 0.0 for k in ("q", "dq", "dq_abs", "dq_light", "dq_chem",
                            "turn_factor", "sigma_eff", "r_light", "r_chem")}
    n_ev = 0
    dq_pos = dq_neg = dq_zero = 0

    for _t in range(ticks):
        sim.stim_obs = sim._new_stim_obs()
        for o in sim.organisms:
            px, py = o.x, o.y
            # Energyを一定に保ち、満腹stop・生理を発生させない
            o.energy = 0.5 * o.energy_max(cfg.energy_capacity)
            behavior.decide_and_move(o, sim)
            path_len += math.hypot(o.x - px, o.y - py)
            ix, iy = sim.world.cell_index(o.x, o.y)
            if qf[ix, iy] >= hi_thresh:
                hi_ticks += 1
            total_ticks += 1
        obs = sim.stim_obs
        n_ev += obs["stim_events"]
        acc["q"] += obs["q_sum"]
        acc["dq"] += obs["dq_sum"]
        acc["dq_abs"] += obs["dq_abs_sum"]
        acc["dq_light"] += obs["dq_light_sum"]
        acc["dq_chem"] += obs["dq_chem_sum"]
        acc["turn_factor"] += obs["turn_factor_sum"]
        acc["sigma_eff"] += obs["sigma_eff_sum"]
        acc["r_light"] += obs["r_light_sum"]
        acc["r_chem"] += obs["r_chem_sum"]
        dq_pos += obs["dq_pos"]
        dq_neg += obs["dq_neg"]
        dq_zero += obs["dq_zero"]
        if tracks and (_t % track_every == 0):
            for k in range(len(tracks)):
                o = sim.organisms[k]
                tracks[k].append((o.x, o.y))

    x1 = np.array([o.x for o in sim.organisms])
    y1 = np.array([o.y for o in sim.organisms])
    net = np.hypot(x1 - x0, y1 - y0)

    row = {
        "env": env, "phenotype": pheno, "seed": seed,
        "memory_tau": memory_tau, "response_gain": response_gain,
        "ticks": ticks, "n_org": n_org,
        "hi_q_frac": hi_ticks / total_ticks if total_ticks else float("nan"),
        "drift_x": float((x1 - x0).mean()) / cfg.cell_size,
        "drift_y": float((y1 - y0).mean()) / cfg.cell_size,
        "net_disp_mean": float(net.mean()) / cfg.cell_size,
        "path_len_mean": path_len / len(sim.organisms) / cfg.cell_size,
        "straightness": (float(net.mean()) /
                         (path_len / len(sim.organisms))) if path_len else 0.0,
        "dq_pos": dq_pos, "dq_neg": dq_neg, "dq_zero": dq_zero,
    }
    for k, v in acc.items():
        row[k + "_mean"] = v / n_ev if n_ev else float("nan")
    if track_out:
        track_out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            track_out,
            tracks=np.array(tracks, dtype=float),
            final_x=x1, final_y=y1, start_x=x0, start_y=y0,
            q_field=qf, hi_thresh=hi_thresh,
            light=sim.world.light, chemical=sim.world.chemical,
            cell_size=cfg.cell_size)
    return row


def _job(job: tuple) -> dict:
    return run_arena(*job)


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp10 Phase A 診断arena")
    ap.add_argument("--out", default="runs/exp10_phaseA")
    ap.add_argument("--ticks", type=int, default=2000)
    ap.add_argument("--n-org", type=int, default=100)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--quick", action="store_true",
                    help="小規模スモーク (1環境 × 1表現型 × 2組 × 2 seed)")
    ap.add_argument("--envs", default="", help="カンマ区切りで環境を絞る")
    ap.add_argument("--workers", type=int, default=1, help="並列実行数 (run間のみ)")
    args = ap.parse_args()

    envs = ([e for e in args.envs.split(",") if e] if args.envs
            else list(ENVIRONMENTS))
    phenos = list(PHENOTYPES)
    combos = [(t, g) for t in MEMORY_TAUS for g in RESPONSE_GAINS]
    # gain=0 の random control は tau に依存しないので1組だけ
    combos.append((MEMORY_TAUS[0], CONTROL_GAIN))
    seeds = list(range(1, args.seeds + 1))

    if args.quick:
        envs = envs[:1]
        phenos = phenos[:1]
        combos = [(10.0, 64.0), (10.0, CONTROL_GAIN)]
        seeds = [1, 2]
        args.ticks = min(args.ticks, 300)
        args.n_org = min(args.n_org, 40)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    total = len(envs) * len(phenos) * len(combos) * len(seeds)
    print(f"Exp10 Phase A: {total:,} run "
          f"({len(envs)}環境 × {len(phenos)}表現型 × {len(combos)}組 × "
          f"{len(seeds)} seed) / {args.ticks:,} tick / {args.n_org} 個体")

    jobs = [(env, pheno, seed, tau, gain, args.ticks, args.n_org)
            for env in envs for pheno in phenos
            for tau, gain in combos for seed in seeds]
    t0 = time.time()
    rows: list[dict] = []
    if args.workers > 1:
        # run同士は完全に独立 (個体間相互作用も共有状態も無い) ので、
        # 並列化しても各runの結果は逐次実行と1 bitも変わらない。
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for i, row in enumerate(ex.map(_job, jobs, chunksize=4), 1):
                rows.append(row)
                if i % 100 == 0 or i == total:
                    el = time.time() - t0
                    print(f"  {i:,}/{total:,} ({el:.0f}s, "
                          f"残り約{el / i * (total - i):.0f}s)", flush=True)
    else:
        for i, job in enumerate(jobs, 1):
            rows.append(_job(job))
            if i % 100 == 0 or i == total:
                el = time.time() - t0
                print(f"  {i:,}/{total:,} ({el:.0f}s, "
                      f"残り約{el / i * (total - i):.0f}s)", flush=True)

    path = out / "phaseA.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = {
        "ticks": args.ticks, "n_org": args.n_org, "seeds": seeds,
        "environments": envs, "phenotypes": phenos,
        "memory_taus": list(MEMORY_TAUS), "response_gains": list(RESPONSE_GAINS),
        "control_gain": CONTROL_GAIN,
        "light_max": LIGHT_MAX, "chem_max": CHEM_MAX,
        "hi_q_definition": "その表現型のQ上位25%のセル",
        "elapsed_s": round(time.time() - t0, 1),
        "workers": args.workers,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    print(f"\n{len(rows):,} run -> {path}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
