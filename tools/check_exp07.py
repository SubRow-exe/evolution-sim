"""Exp07 診断条件の成立チェック (docs/Exp07_実験計画.md §3-5)。

    uv run python tools/check_exp07.py runs/exp07 --seeds 1-10

「結果を解釈する前に、意図した診断条件で走っていたか」だけを確認する。
生存・絶滅・chemical利用といった科学的結果は判定しない (それが観測対象)。

確認する前提:
- 条件ディレクトリが `flux<NN>_<条件>` の形で揃い、期待どおりのseedがある
- 全条件で総光供給 = 0 かつ 累積 light flow = 0
- Config の chem_vent_flux がディレクトリ名のfluxと一致する
- **実効source == 公称source**: `sum(chem_source_flux) == n_vents * chem_vent_flux`
  (V1.3でcapacity clippingを廃止した主目的。seed依存の損失が無いこと)
- 初期stockが無生物平衡 `chem_source_flux / chem_loss_frac` である
- vent条件 (B/C) は全個体が chem_mask セル上から開始している
- chem-adapted条件 (C/D) は初期・最終snapshotとも chemical_absorption が厳密に 2.0
- 同一flux・同一seedで B と C の初期配置が一致する (ゲノムだけが違う対応比較)

前提が崩れていれば非ゼロ終了する。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHEM_TARGET = 2.0
VENT_CONDITIONS = ("b_ancestor_vent", "c_chem_vent")
CHEM_ADAPTED = ("c_chem_vent", "d_chem_random")
DIR_RE = re.compile(r"^flux(\d+)_(.+)$")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checked = 0

    def check(self, ok: bool, label: str, detail: str = "", quiet_ok: bool = False) -> bool:
        self.checked += 1
        if not ok:
            print(f"  NG  {label}" + (f"   {detail}" if detail else ""))
            self.fails.append(label + (f" ({detail})" if detail else ""))
        elif not quiet_ok:
            print(f"  OK  {label}" + (f"   {detail}" if detail else ""))
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


def last_stats_row(run: Path) -> tuple[list[str], list[str]]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[-1]


def snapshots(run: Path) -> list[Path]:
    return sorted((run / "snapshots").glob("snap_*.csv"))


def build_world(run: Path, seed: int):
    from evosim.config import Config
    from evosim.simulation import Simulation
    return Simulation(Config.from_json(run / "config.json"), seed)


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp07 診断条件の成立チェック")
    ap.add_argument("exp_dir", help="flux<NN>_<条件>/ を含むディレクトリ")
    ap.add_argument("--seeds", default="1-10", help='例: "1-10" / "1"')
    args = ap.parse_args()

    base = Path(args.exp_dir)
    want_seeds = parse_seeds(args.seeds)
    rep = Report()

    conds = sorted(d for d in base.iterdir() if d.is_dir() and DIR_RE.match(d.name))
    if not conds:
        print(f"NG  {base} に flux<NN>_<条件>/ が無い")
        return 1

    placements: dict[tuple[int, str, int], list[tuple[float, float]]] = {}

    for cond in conds:
        m = DIR_RE.match(cond.name)
        flux, name = int(m.group(1)), m.group(2)
        runs = run_dirs(cond)
        print(f"\n=== {cond.name} ({len(runs)} run) ===")
        rep.check(sorted(runs) == want_seeds, f"{cond.name}: seed {sorted(runs)}",
                  f"期待 {want_seeds}")

        for seed in sorted(runs):
            run = runs[seed]
            tag = f"{cond.name} s{seed}"
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            header, last = last_stats_row(run)

            # --- 光0 ---
            rep.check(cfg["light_max"] == 0.0, f"{tag}: light_max=0", quiet_ok=True)
            for col in ("light_supply_cum", "flow_light_cum"):
                rep.check(float(last[header.index(col)]) == 0.0,
                          f"{tag}: 累積{col}=0", last[header.index(col)],
                          quiet_ok=True)

            # --- flux ---
            rep.check(cfg["chem_vent_flux"] == float(flux),
                      f"{tag}: chem_vent_flux={cfg['chem_vent_flux']}",
                      f"期待 {flux}", quiet_ok=True)

            # --- 条件 ---
            want_placement = "vent" if name in VENT_CONDITIONS else "random"
            rep.check(cfg["diagnostic_placement"] == want_placement,
                      f"{tag}: placement={cfg['diagnostic_placement']}",
                      f"期待 {want_placement}", quiet_ok=True)
            if name in CHEM_ADAPTED:
                rep.check(cfg["diagnostic_gene_overrides"].get(
                              "chemical_absorption") == CHEM_TARGET
                          and "chemical_absorption" in cfg["fixed_genes"],
                          f"{tag}: chemical_absorption=2.0 固定", quiet_ok=True)
            else:
                rep.check(not cfg["diagnostic_gene_overrides"] and not cfg["fixed_genes"],
                          f"{tag}: ゲノム上書き・固定なし", quiet_ok=True)

            # --- source field と初期stock (V1.3の核) ---
            sim = build_world(run, seed)
            w = sim.world
            nominal = cfg["n_vents"] * cfg["chem_vent_flux"]
            rep.check(abs(w.chem_source_total - nominal) < 1e-9,
                      f"{tag}: 実効source={w.chem_source_total:.6f}",
                      f"公称 {nominal}", quiet_ok=True)
            eq = w.chem_source_flux / cfg["chem_loss_frac"]
            rep.check(bool(np.allclose(w.chemical, eq, rtol=1e-12)),
                      f"{tag}: 初期stockが無生物平衡", quiet_ok=True)

            from evosim.genome import CHEM_ABS
            if name in CHEM_ADAPTED:
                g0 = np.stack([o.genome for o in sim.organisms])
                rep.check(bool(np.all(g0[:, CHEM_ABS] == CHEM_TARGET)),
                          f"{tag}: 初期個体が全て 2.0", quiet_ok=True)
                snaps = snapshots(run)
                if snaps:
                    with open(snaps[-1], encoding="utf-8") as f:
                        vals = [float(r["chemical_absorption"])
                                for r in csv.DictReader(f)]
                    rep.check(all(v == CHEM_TARGET for v in vals),
                              f"{tag}: 最終snapshotも全て 2.0 ({len(vals)} 個体)",
                              quiet_ok=True)
            if name in VENT_CONDITIONS:
                on_vent = all(w.chem_mask[w.cell_index(o.x, o.y)]
                              for o in sim.organisms)
                rep.check(on_vent, f"{tag}: 初期個体が全てventセル上", quiet_ok=True)

            placements[(flux, name, seed)] = [(o.x, o.y) for o in sim.organisms]

        print(f"  (各runの詳細チェックは異常時のみ表示。{cond.name} は "
              f"{len(runs)} run 分を確認)")

    print("\n=== 対応比較 (同一flux・同一seedで B と C の初期配置が一致するか) ===")
    fluxes = sorted({f for f, _, _ in placements})
    for flux in fluxes:
        bad = [seed for seed in want_seeds
               if (flux, "b_ancestor_vent", seed) in placements
               and (flux, "c_chem_vent", seed) in placements
               and placements[(flux, "b_ancestor_vent", seed)]
               != placements[(flux, "c_chem_vent", seed)]]
        rep.check(not bad, f"flux {flux}: B と C の初期配置が全seedで一致",
                  f"不一致 seed {bad}" if bad else "")

    print("\n" + "=" * 60)
    print(f"確認項目 {rep.checked} 件")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)}件")
        for f in rep.fails[:20]:
            print(f"  - {f}")
        return 1
    print("判定: OK — Exp07 の診断条件は全て意図どおり")
    return 0


if __name__ == "__main__":
    sys.exit(main())
