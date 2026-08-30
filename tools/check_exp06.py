"""Exp06 診断条件の成立チェック (docs/Exp06_実験計画.md §4-5)。

    uv run python tools/check_exp06.py runs/exp06 --seeds 1-10

「結果を解釈する前に、意図した診断条件で走っていたか」だけを確認する。
生存・絶滅・chemical利用といった科学的結果は判定しない (それが観測対象)。

確認する前提:
- 4条件が揃い、条件ごとに期待どおりのseedがある
- 全条件で総光供給 = 0 かつ 累積 light flow = 0 (光0が本当に効いている)
- B/C は全個体が vent セル上から開始している
- A/D は通常のランダム配置と同じ初期位置 (光ありrunと一致)
- C/D は初期個体の chemical_absorption が厳密に 2.0 で、最終snapshotでも 2.0
- A/B は chemical_absorption を固定していない (祖先値から自由に進化できる)
- 同一seedで B/C・A/D の初期位置が一致する (ゲノムだけが違う対応比較)

前提が崩れていれば非ゼロ終了する。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHEM_TARGET = 2.0
ANCESTOR = ("a_ancestor_random", "b_ancestor_vent")
CHEM_ADAPTED = ("c_chem_vent", "d_chem_random")
VENT = ("b_ancestor_vent", "c_chem_vent")
RANDOM = ("a_ancestor_random", "d_chem_random")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        print(f"  {'OK  ' if ok else 'NG  '}{label}" + (f"   {detail}" if detail else ""))
        if not ok:
            self.fails.append(label + (f" ({detail})" if detail else ""))
        return ok


def parse_seeds(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def run_dirs(cond: Path) -> dict[int, Path]:
    return {int(d.name.split("seed")[-1]): d
            for d in sorted(cond.iterdir())
            if d.is_dir() and (d / "stats.csv").exists()}


def read_stats(run: Path) -> tuple[list[str], list[list[str]]]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def snapshots(run: Path) -> list[Path]:
    return sorted((run / "snapshots").glob("snap_*.csv"))


def read_snapshot(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def spawn_positions(run: Path, seed: int) -> list[tuple[float, float]]:
    """config.json + seed から初期配置を再構築する (tick0 snapshotは無いため)。"""
    from evosim.config import Config
    from evosim.simulation import Simulation
    sim = Simulation(Config.from_json(run / "config.json"), seed)
    return [(o.x, o.y) for o in sim.organisms]


def spawn_genomes(run: Path, seed: int) -> np.ndarray:
    from evosim.config import Config
    from evosim.simulation import Simulation
    sim = Simulation(Config.from_json(run / "config.json"), seed)
    return np.stack([o.genome for o in sim.organisms])


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp06 診断条件の成立チェック")
    ap.add_argument("exp_dir", help="条件ディレクトリを含むディレクトリ")
    ap.add_argument("--seeds", default="1-10", help='例: "1-10" / "1,2,3"')
    ap.add_argument("--conditions",
                    default=",".join(ANCESTOR + CHEM_ADAPTED))
    args = ap.parse_args()

    from evosim.genome import CHEM_ABS

    base = Path(args.exp_dir)
    want_seeds = parse_seeds(args.seeds)
    names = [c.strip() for c in args.conditions.split(",") if c.strip()]
    rep = Report()

    conds: dict[str, dict[int, Path]] = {}
    for name in names:
        d = base / name
        if not d.is_dir():
            rep.check(False, f"{name}/ がある", f"{d} が無い")
            continue
        conds[name] = run_dirs(d)

    if len(conds) != len(names):
        print("\n判定: NG")
        return 1

    for name, runs in conds.items():
        print(f"\n=== {name} ({len(runs)} run) ===")
        rep.check(sorted(runs) == want_seeds, f"{name}: seed {sorted(runs)}",
                  f"期待 {want_seeds}")
        for seed in sorted(runs):
            run = runs[seed]
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            header, rows = read_stats(run)
            i_supply = header.index("light_supply_cum")
            i_flow = header.index("flow_light_cum")
            last = rows[-1]

            rep.check(cfg["light_max"] == 0.0, f"{name} s{seed}: light_max=0")
            rep.check(float(last[i_supply]) == 0.0,
                      f"{name} s{seed}: 累積光供給=0", last[i_supply])
            rep.check(float(last[i_flow]) == 0.0,
                      f"{name} s{seed}: 累積 light flow=0", last[i_flow])

            want_placement = "vent" if name in VENT else "random"
            rep.check(cfg["diagnostic_placement"] == want_placement,
                      f"{name} s{seed}: placement={cfg['diagnostic_placement']}",
                      f"期待 {want_placement}")

            if name in CHEM_ADAPTED:
                rep.check(cfg["diagnostic_gene_overrides"].get(
                              "chemical_absorption") == CHEM_TARGET,
                          f"{name} s{seed}: 上書き chemical_absorption=2.0")
                rep.check("chemical_absorption" in cfg["fixed_genes"],
                          f"{name} s{seed}: chemical_absorption を固定")
                g0 = spawn_genomes(run, seed)
                rep.check(bool(np.all(g0[:, CHEM_ABS] == CHEM_TARGET)),
                          f"{name} s{seed}: 初期個体が全て 2.0")
                snaps = snapshots(run)
                if snaps:
                    vals = [float(r["chemical_absorption"])
                            for r in read_snapshot(snaps[-1])]
                    rep.check(all(v == CHEM_TARGET for v in vals),
                              f"{name} s{seed}: 最終snapshotも全て 2.0 "
                              f"({len(vals)} 個体)")
            else:
                rep.check(not cfg["diagnostic_gene_overrides"],
                          f"{name} s{seed}: ゲノム上書きなし")
                rep.check(not cfg["fixed_genes"],
                          f"{name} s{seed}: 固定遺伝子なし")

            if name in VENT:
                from evosim.config import Config
                from evosim.simulation import Simulation
                sim = Simulation(Config.from_json(run / "config.json"), seed)
                on_vent = all(sim.world.chem_mask[sim.world.cell_index(o.x, o.y)]
                              for o in sim.organisms)
                rep.check(on_vent, f"{name} s{seed}: 初期個体が全てventセル上")

    print("\n=== 対応比較 (同一seedで配置が一致するか) ===")
    for a, b in (VENT, RANDOM):
        if a not in conds or b not in conds:
            continue
        for seed in sorted(set(conds[a]) & set(conds[b])):
            rep.check(spawn_positions(conds[a][seed], seed)
                      == spawn_positions(conds[b][seed], seed),
                      f"seed {seed}: {a} と {b} の初期配置が一致")

    print("\n" + "=" * 60)
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)}件")
        for f in rep.fails:
            print(f"  - {f}")
        return 1
    print("判定: OK — Exp06 の診断条件は全て意図どおり")
    return 0


if __name__ == "__main__":
    sys.exit(main())
