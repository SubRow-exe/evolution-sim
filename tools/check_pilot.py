"""Exp05 の光場・出力構造チェック (docs/Exp05_実験計画.md §5)。

    uv run python tools/check_pilot.py runs/exp05_pilot --ticks 5000
    uv run python tools/check_pilot.py runs/exp05 --ticks 40000 --seeds 1-20

pilot でも本番でも **実装が仕様どおり動いているか**だけを見る。
暗部無人化・大量死・形質変化などの生物学的結果はここでは判定しない
(正しいモデル帰結を理由に条件を変えないため)。

確認する前提:
- crash / 早期終了なし (全runが指定tickへ到達)
- Control と Treatment の総光供給量が一致する (total_scale=1.0)
- Treatment が 8行明部 / 20行遷移 / 12行完全暗部 で、実効ピークが 1.2*13/9
- Control の光場が V1.1 の式のまま
- snapshot CSV / environment NPZ / 空間指標が期待どおり出力されている
- 同一seedで Control と Treatment の初期個体が一致する (光以外は同一世界)

前提が崩れていれば非ゼロ終了する。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

CONTROL_TOTAL = 1248.0          # 40x40 / light_max=1.2 / light_floor=0.3
TREATMENT_PEAK = 1.2 * 13.0 / 9.0
SPATIAL_COLS = ["pop_north_band", "pop_middle_band", "pop_south_band",
                "frac_north_band", "frac_middle_band", "frac_south_band",
                "mean_local_light", "vent_cell_population", "vent_cell_frac",
                "mean_move_per_org_tick"]
LINEAGE_SPATIAL_COLS = ["occupied_cells", "centroid_x", "centroid_y",
                        "mean_radius_from_centroid", "mean_move_per_org_tick",
                        "mean_local_light", "vent_cell_frac",
                        "mean_chemical_absorption"]


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        mark = "OK  " if ok else "NG  "
        print(f"  {mark}{label}" + (f"   {detail}" if detail else ""))
        if not ok:
            self.fails.append(label + (f" ({detail})" if detail else ""))
        return ok

    def warn(self, label: str) -> None:
        print(f"  警告 {label}")
        self.warns.append(label)


def parse_seeds(spec: str) -> list[int]:
    """"1,2,3" や "1-20" や "1-3,10" を seed のリストに展開する。"""
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def run_dirs(cond: Path) -> list[Path]:
    return sorted(d for d in cond.iterdir() if d.is_dir() and (d / "stats.csv").exists())


def seed_of(run: Path) -> int:
    return int(run.name.split("seed")[-1])


def read_stats(run: Path) -> tuple[list[str], list[list[str]]]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def light_of(run: Path) -> np.ndarray:
    with np.load(run / "environment" / "static.npz") as d:
        return d["light"]


def check_run_outputs(run: Path, ticks: int, rep: Report) -> None:
    """1 run の出力構造を確認する。"""
    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    snap_iv = cfg["snapshot_interval"]
    stats_iv = cfg["stats_interval"]

    header, rows = read_stats(run)
    last_tick = int(rows[-1][0]) if rows else -1
    rep.check(last_tick == ticks, f"{run.name}: 最終tick={last_tick}", f"期待 {ticks}")
    rep.check(int(rows[-1][1]) > 0, f"{run.name}: 最終個体数={rows[-1][1]}", "絶滅していない")
    rep.check(len(rows) == ticks // stats_iv,
              f"{run.name}: stats行数={len(rows)}",
              f"期待 {ticks // stats_iv} (stats_interval={stats_iv})")

    missing = [c for c in SPATIAL_COLS if c not in header]
    rep.check(not missing, f"{run.name}: stats.csv の空間指標列", f"欠損 {missing}")
    idx = {c: header.index(c) for c in SPATIAL_COLS if c in header}
    if idx:
        bands = [sum(int(r[idx[f"pop_{b}_band"]]) for b in ("north", "middle", "south"))
                 == int(r[1]) for r in rows]
        rep.check(all(bands), f"{run.name}: 3帯人口の合計 == population")
        filled = all(r[idx["mean_local_light"]] != "" for r in rows)
        rep.check(filled, f"{run.name}: mean_local_light が全行で埋まっている")

    want_snaps = ticks // snap_iv
    snaps = sorted((run / "snapshots").glob("snap_*.csv"))
    envs = sorted((run / "environment").glob("env_*.npz"))
    rep.check(len(snaps) == want_snaps, f"{run.name}: snapshot {len(snaps)}枚",
              f"期待 {want_snaps} (snapshot_interval={snap_iv})")
    want_ticks = [snap_iv * (i + 1) for i in range(want_snaps)]
    rep.check([int(p.stem.split("_")[1]) for p in snaps] == want_ticks,
              f"{run.name}: snapshot の tick 列")
    rep.check(len(envs) == want_snaps, f"{run.name}: environment NPZ {len(envs)}個",
              f"期待 {want_snaps}")
    rep.check((run / "environment" / "static.npz").exists(),
              f"{run.name}: environment/static.npz")

    with np.load(envs[-1]) as d:
        keys = set(d.files)
    rep.check({"chemical", "nutrients"} <= keys, f"{run.name}: env NPZ のキー",
              f"{sorted(keys)}")

    with open(run / "lineages.csv", encoding="utf-8") as f:
        lin_header = next(csv.reader(f))
    lin_missing = [c for c in LINEAGE_SPATIAL_COLS if c not in lin_header]
    rep.check(not lin_missing, f"{run.name}: lineages.csv の空間指標列",
              f"欠損 {lin_missing}")

    meta = run / "meta.json"
    rep.check(meta.exists(), f"{run.name}: meta.json")


def same_initial_state(c_run: Path, t_run: Path, seed: int) -> bool:
    """同一seedなら光以外の初期世界が完全一致することを、実際に構築して確かめる。

    tick 0 のスナップショットは出力されない (最初の記録は snapshot_interval)
    ため、各runの config.json + seed から初期状態を再構築して比較する。
    """
    from evosim.config import Config
    from evosim.simulation import Simulation

    a = Simulation(Config.from_json(c_run / "config.json"), seed)
    b = Simulation(Config.from_json(t_run / "config.json"), seed)
    if len(a.organisms) != len(b.organisms):
        return False
    for x, y in zip(a.organisms, b.organisms):
        if (x.id, x.x, x.y) != (y.id, y.x, y.y):
            return False
        if not np.array_equal(x.genome, y.genome):
            return False
    return (np.array_equal(a.world.nutrients, b.world.nutrients)
            and np.array_equal(a.world.chemical, b.world.chemical)
            and not np.array_equal(a.world.light, b.world.light))


def check_control_light(light: np.ndarray, rep: Report) -> None:
    """Control 光場が V1.1 の式のままか。"""
    gh = light.shape[1]
    frac = 1.0 - (np.arange(gh) + 0.5) / gh
    expected = np.tile(1.2 * (0.3 + 0.7 * frac), (light.shape[0], 1))
    rep.check(np.allclose(light, expected, rtol=1e-12),
              "Control: V1.1 の vertical 式と一致")
    rep.check(abs(float(light.sum()) - CONTROL_TOTAL) < 1e-9,
              f"Control: 総光量={float(light.sum()):.6f}", f"期待 {CONTROL_TOTAL}")


def check_treatment_light(light: np.ndarray, rep: Report) -> None:
    """Treatment 光場の帯構造・ピーク・総光量。"""
    col = light[0]
    rep.check(np.array_equal(light, np.tile(col, (light.shape[0], 1))),
              "Treatment: 東西方向は一様")
    bright, transition, dark = col[:8], col[8:28], col[28:]
    rep.check(np.allclose(bright, bright[0], rtol=1e-12),
              f"Treatment: 北8行が明部plateau ({float(bright[0]):.6f})")
    rep.check(bool(np.all(np.diff(transition) < 0)),
              "Treatment: 中20行が単調減少の遷移帯")
    rep.check(bool(np.all(dark == 0.0)), "Treatment: 南12行が完全暗部")
    rep.check(bool(np.all(light >= 0.0)), "Treatment: 負の光量なし")
    rep.check(abs(float(light.max()) - TREATMENT_PEAK) < 1e-9,
              f"Treatment: 実効ピーク={float(light.max()):.6f}",
              f"期待 {TREATMENT_PEAK:.6f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp05 pilot の健全性チェック")
    ap.add_argument("pilot_dir", help="条件ディレクトリ (既定 control/ treatment/) を含むディレクトリ")
    ap.add_argument("--ticks", type=int, default=5000)
    ap.add_argument("--seeds", default="1,2,3", help='例: "1,2,3" / "1-20"')
    ap.add_argument("--conditions", default="control,treatment",
                    help="比較する2条件のディレクトリ名 (Control,Treatment の順)")
    args = ap.parse_args()

    base = Path(args.pilot_dir)
    want_seeds = parse_seeds(args.seeds)
    rep = Report()

    names = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if len(names) != 2:
        raise SystemExit(f"--conditions は Control,Treatment の2つ: {names}")
    control_name, treatment_name = names

    conds = {}
    for name in names:
        d = base / name
        if not d.is_dir():
            print(f"NG  {name}/ がない: {d}")
            rep.fails.append(f"{name}/ がない")
            continue
        conds[name] = {seed_of(r): r for r in run_dirs(d)}

    if len(conds) != 2:
        print("\n判定: NG")
        return 1

    for name, runs in conds.items():
        print(f"\n=== {name} ({len(runs)} run) ===")
        rep.check(sorted(runs) == want_seeds, f"{name}: seed {sorted(runs)}",
                  f"期待 {want_seeds}")
        for seed in sorted(runs):
            check_run_outputs(runs[seed], args.ticks, rep)

    print("\n=== 光場 ===")
    c_lights = {s: light_of(r) for s, r in conds[control_name].items()}
    t_lights = {s: light_of(r) for s, r in conds[treatment_name].items()}
    check_control_light(next(iter(c_lights.values())), rep)
    check_treatment_light(next(iter(t_lights.values())), rep)
    rep.check(all(np.array_equal(l, next(iter(c_lights.values()))) for l in c_lights.values())
              and all(np.array_equal(l, next(iter(t_lights.values()))) for l in t_lights.values()),
              "光場が seed に依存しない (静的光場)")
    ct = float(next(iter(c_lights.values())).sum())
    tt = float(next(iter(t_lights.values())).sum())
    rep.check(abs(ct - tt) < 1e-9,
              f"総光供給量の一致: {control_name}={ct:.6f} / {treatment_name}={tt:.6f}",
              "total_scale=1.0")

    print("\n=== 光以外の世界が同一か (同一seed) ===")
    for seed in sorted(set(conds[control_name]) & set(conds[treatment_name])):
        c, t = conds[control_name][seed], conds[treatment_name][seed]
        with np.load(c / "environment" / "static.npz") as d:
            cm_c = d["chem_mask"]
        with np.load(t / "environment" / "static.npz") as d:
            cm_t = d["chem_mask"]
        rep.check(np.array_equal(cm_c, cm_t), f"seed {seed}: chem_mask 一致")
        rep.check(same_initial_state(c, t, seed),
                  f"seed {seed}: tick 0 の初期個体群・栄養場が一致")

    print("\n=== PNG / GIF ===")
    for name, runs in conds.items():
        for seed in sorted(runs):
            out = runs[seed] / "spatial" / "light"
            pngs = sorted(out.glob("frame_*.png")) if out.is_dir() else []
            rep.check(len(pngs) == args.ticks // 1000,
                      f"{name} seed {seed}: PNG {len(pngs)}枚")
            rep.check((out / "light.gif").exists(),
                      f"{name} seed {seed}: light.gif")

    print("\n" + "=" * 60)
    if rep.warns:
        print(f"警告 {len(rep.warns)}件")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)}件")
        for f in rep.fails:
            print(f"  - {f}")
        return 1
    print("判定: OK — 光場と出力構造のチェックは全て通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
