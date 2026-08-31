"""Exp08 診断条件の成立チェック (docs/Exp08_実験計画.md §4-5, §9)。

    uv run python tools/check_exp08.py runs/exp08 --seeds 1-10

「結果を解釈する前に、意図した条件で走っていたか」だけを確認する。
生存・絶滅・人口といった科学的結果は判定しない (それが観測対象)。

確認する前提:

Phase A (光単独 / `a_l0_coef*` `a_l2_coef*`)
- `light_pattern=vertical` (V1.1互換) で `light_max` がdefaultのまま
- `chem_vent_flux=0.0` かつ `n_vents=4` (Phase Bと乱数消費を揃えるため)
- 累積 chemical flow = 0 (chemicalが実質存在しない)
- Config の `light_uptake_coef` がディレクトリ名の係数と一致する
- `light_absorption` が固定されている (L0=0.3 / L2=2.0)。初期個体と
  最終snapshotの両方で厳密一致・分散0

Phase B (chemical単独 / `b_flux*_chem`)
- 総光供給 = 0 かつ 累積 light flow = 0
- Config の `chem_vent_flux` がディレクトリ名のfluxと一致する
- 実効source == 公称source (`sum(chem_source_flux) == n_vents * chem_vent_flux`)
- 初期stockが無生物平衡 `chem_source_flux / chem_loss_frac`
- 全個体が chem_mask セル上から開始している
- `chemical_absorption` が初期・最終snapshotとも厳密に 2.0

共通
- 期待どおりのseedが揃っている
- 全runが同一世界バージョン (V1.4吸収則) のConfig項目を持つ

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
L2_TARGET = 2.0
L0_TARGET = 0.3
A_RE = re.compile(r"^a_(l0|l2)_coef(\d+p\d+)$")
B_RE = re.compile(r"^b_flux(\d+)_chem$")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checked = 0

    def check(self, ok: bool, label: str, detail: str = "",
              quiet_ok: bool = False) -> bool:
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


def coef_from_tag(tag: str) -> float:
    return float(tag.replace("p", "."))


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


def snapshot_gene(run: Path, gene: str) -> list[float] | None:
    snaps = snapshots(run)
    if not snaps:
        return None
    with open(snaps[-1], encoding="utf-8") as f:
        return [float(r[gene]) for r in csv.DictReader(f)]


def check_phase_a(rep: Report, tag: str, kind: str, coef: float,
                  run: Path, seed: int, cfg: dict,
                  header: list[str], last: list[str]) -> None:
    from evosim.genome import LIGHT_ABS

    rep.check(cfg["light_pattern"] == "vertical",
              f"{tag}: light_pattern={cfg['light_pattern']}", "期待 vertical",
              quiet_ok=True)
    rep.check(cfg["light_uptake_coef"] == coef,
              f"{tag}: light_uptake_coef={cfg['light_uptake_coef']}",
              f"期待 {coef}", quiet_ok=True)
    rep.check(cfg["chem_vent_flux"] == 0.0,
              f"{tag}: chem_vent_flux=0", quiet_ok=True)
    rep.check(cfg["n_vents"] == 4,
              f"{tag}: n_vents=4 (乱数消費をPhase Bと揃える)", quiet_ok=True)
    rep.check(float(last[header.index("flow_chemical_cum")]) == 0.0,
              f"{tag}: 累積 flow_chemical_cum=0", quiet_ok=True)
    rep.check(float(last[header.index("light_supply_cum")]) > 0.0,
              f"{tag}: 光が供給されている", quiet_ok=True)

    target = L2_TARGET if kind == "l2" else L0_TARGET
    rep.check("light_absorption" in cfg["fixed_genes"],
              f"{tag}: light_absorption が fixed_genes にある", quiet_ok=True)
    if kind == "l2":
        rep.check(cfg["diagnostic_gene_overrides"].get("light_absorption")
                  == L2_TARGET,
                  f"{tag}: light_absorption=2.0 上書き", quiet_ok=True)
    else:
        rep.check(not cfg["diagnostic_gene_overrides"],
                  f"{tag}: ゲノム上書きなし (祖先の初期値のまま)", quiet_ok=True)

    sim = build_world(run, seed)
    g0 = np.stack([o.genome for o in sim.organisms])
    rep.check(bool(np.all(g0[:, LIGHT_ABS] == target)),
              f"{tag}: 初期個体の light_absorption が全て {target}", quiet_ok=True)
    vals = snapshot_gene(run, "light_absorption")
    if vals is not None:
        rep.check(all(v == target for v in vals),
                  f"{tag}: 最終snapshotも全て {target} ({len(vals)} 個体)",
                  quiet_ok=True)


def check_phase_b(rep: Report, tag: str, flux: int, run: Path, seed: int,
                  cfg: dict, header: list[str], last: list[str]) -> None:
    from evosim.genome import CHEM_ABS

    rep.check(cfg["light_max"] == 0.0, f"{tag}: light_max=0", quiet_ok=True)
    for col in ("light_supply_cum", "flow_light_cum"):
        rep.check(float(last[header.index(col)]) == 0.0,
                  f"{tag}: 累積{col}=0", last[header.index(col)], quiet_ok=True)
    rep.check(cfg["chem_vent_flux"] == float(flux),
              f"{tag}: chem_vent_flux={cfg['chem_vent_flux']}", f"期待 {flux}",
              quiet_ok=True)
    rep.check(cfg["chem_uptake"] == 0.5,
              f"{tag}: chem_uptake=0.5 固定", quiet_ok=True)
    rep.check(cfg["diagnostic_placement"] == "vent",
              f"{tag}: placement=vent", quiet_ok=True)
    rep.check(cfg["diagnostic_gene_overrides"].get("chemical_absorption")
              == CHEM_TARGET and "chemical_absorption" in cfg["fixed_genes"],
              f"{tag}: chemical_absorption=2.0 固定", quiet_ok=True)

    sim = build_world(run, seed)
    w = sim.world
    nominal = cfg["n_vents"] * cfg["chem_vent_flux"]
    rep.check(abs(w.chem_source_total - nominal) < 1e-9,
              f"{tag}: 実効source={w.chem_source_total:.6f}", f"公称 {nominal}",
              quiet_ok=True)
    eq = w.chem_source_flux / cfg["chem_loss_frac"]
    rep.check(bool(np.allclose(w.chemical, eq, rtol=1e-12)),
              f"{tag}: 初期stockが無生物平衡", quiet_ok=True)
    g0 = np.stack([o.genome for o in sim.organisms])
    rep.check(bool(np.all(g0[:, CHEM_ABS] == CHEM_TARGET)),
              f"{tag}: 初期個体が全て 2.0", quiet_ok=True)
    rep.check(all(w.chem_mask[w.cell_index(o.x, o.y)] for o in sim.organisms),
              f"{tag}: 初期個体が全てventセル上", quiet_ok=True)
    vals = snapshot_gene(run, "chemical_absorption")
    if vals is not None:
        rep.check(all(v == CHEM_TARGET for v in vals),
                  f"{tag}: 最終snapshotも全て 2.0 ({len(vals)} 個体)",
                  quiet_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp08 診断条件の成立チェック")
    ap.add_argument("exp_dir", help="a_l0_coef*/ a_l2_coef*/ b_flux*_chem/ を含むディレクトリ")
    ap.add_argument("--seeds", default="1-10", help='例: "1-10" / "1"')
    args = ap.parse_args()

    base = Path(args.exp_dir)
    want_seeds = parse_seeds(args.seeds)
    rep = Report()

    conds = sorted(d for d in base.iterdir()
                   if d.is_dir() and (A_RE.match(d.name) or B_RE.match(d.name)))
    if not conds:
        print(f"NG  {base} に Exp08 の条件ディレクトリが無い")
        return 1

    for cond in conds:
        runs = run_dirs(cond)
        print(f"\n=== {cond.name} ({len(runs)} run) ===")
        rep.check(sorted(runs) == want_seeds, f"{cond.name}: seed {sorted(runs)}",
                  f"期待 {want_seeds}")

        for seed in sorted(runs):
            run = runs[seed]
            tag = f"{cond.name} s{seed}"
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            header, last = last_stats_row(run)
            rep.check("light_uptake_coef" in cfg,
                      f"{tag}: V1.4 Config (light_uptake_coef を持つ)",
                      quiet_ok=True)

            ma = A_RE.match(cond.name)
            if ma:
                check_phase_a(rep, tag, ma.group(1), coef_from_tag(ma.group(2)),
                              run, seed, cfg, header, last)
            else:
                flux = int(B_RE.match(cond.name).group(1))
                check_phase_b(rep, tag, flux, run, seed, cfg, header, last)

        print(f"  (各runの詳細チェックは異常時のみ表示。{cond.name} は "
              f"{len(runs)} run 分を確認)")

    print("\n" + "=" * 60)
    print(f"確認項目 {rep.checked} 件")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)}件")
        for f in rep.fails[:20]:
            print(f"  - {f}")
        return 1
    print("判定: OK — Exp08 の診断条件は全て意図どおり")
    return 0


if __name__ == "__main__":
    sys.exit(main())
