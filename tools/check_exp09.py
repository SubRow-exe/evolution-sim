"""Exp09 診断条件の成立チェック (docs/Exp09_実験計画.md §10)。

    uv run python tools/check_exp09.py runs/exp09 --seeds 1-5

「結果を解釈する前に、意図した条件で走っていたか」だけを確認する。
選択率・vent滞在率といった科学的結果は判定しない (それが観測対象)。

確認する前提:

- 条件ディレクトリと期待seedが揃っている
- V1.4恒久default (`light_uptake_coef=2.0` / `chem_vent_flux=16.0` /
  `chem_uptake=0.5`) とV1.5受容器スケール (1.2 / 12.3 / 1e-9) がdefaultのまま
- source排他: light-only は累積 chemical flow=0、chemical-only は
  光供給・累積 light flow がともに0、mixed は両方>0
- 診断表現型の `light_absorption` / `chemical_absorption` が初期・最終snapshot
  とも厳密に事前登録値で、全期間で分散0
- **無次元scoreの順位と実際のsource選択が全区間で一致** (`sel_agree` ==
  `sel_light` + `sel_chemical`)。交差点式と実装がずれていれば落ちる
- 観測列が欠けていない

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

from tools.make_exp09_configs import CONDITIONS, PHENOTYPES  # noqa: E402

OBS_COLUMNS = ("sel_light", "sel_chemical", "sel_tie", "sel_walk",
               "sel_both_events", "sel_agree", "sel_lost_light",
               "sel_lost_chemical", "sel_light_resp_mean",
               "sel_chem_resp_mean", "sel_chem_stock_mean")


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


def run_dirs(cond: Path) -> dict[int, Path]:
    return {int(d.name.split("seed")[-1]): d
            for d in sorted(cond.iterdir())
            if d.is_dir() and (d / "stats.csv").exists()}


def rows_of(run: Path) -> list[dict]:
    with open(run / "stats.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def snapshot_gene(run: Path, gene: str) -> list[float] | None:
    snaps = sorted((run / "snapshots").glob("snap_*.csv"))
    if not snaps:
        return None
    with open(snaps[-1], encoding="utf-8") as f:
        return [float(r[gene]) for r in csv.DictReader(f)]


def num(row: dict, key: str) -> float:
    v = row.get(key, "")
    return float(v) if v not in ("", None) else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp09 診断条件の成立チェック")
    ap.add_argument("exp_dir", help="条件ディレクトリを含むディレクトリ")
    ap.add_argument("--seeds", default="1-5", help='例: "1-5" / "1"')
    args = ap.parse_args()

    base = Path(args.exp_dir)
    want_seeds = parse_seeds(args.seeds)
    rep = Report()

    conds = sorted(d for d in base.iterdir()
                   if d.is_dir() and d.name in CONDITIONS)
    if not conds:
        print(f"NG  {base} に Exp09 の条件ディレクトリが無い")
        return 1

    from evosim.config import Config
    from evosim.genome import CHEM_ABS, LIGHT_ABS
    from evosim.simulation import Simulation
    d = Config()   # V1.5 default (比較の基準)

    for cond in conds:
        world, pheno = CONDITIONS[cond.name]
        want = PHENOTYPES[pheno]
        runs = run_dirs(cond)
        print(f"\n=== {cond.name} ({len(runs)} run / {pheno}) ===")
        rep.check(sorted(runs) == want_seeds, f"{cond.name}: seed {sorted(runs)}",
                  f"期待 {want_seeds}")

        for seed in sorted(runs):
            run = runs[seed]
            tag = f"{cond.name} s{seed}"
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            rows = rows_of(run)
            last = rows[-1]

            # --- 世界default (V1.4確定値 / V1.5受容器スケール) ---
            for key, exp in (("light_uptake_coef", d.light_uptake_coef),
                             ("chem_uptake", d.chem_uptake),
                             ("light_stimulus_half", d.light_stimulus_half),
                             ("chemical_stimulus_half", d.chemical_stimulus_half),
                             ("stimulus_tie_eps", d.stimulus_tie_eps),
                             ("n_vents", d.n_vents)):
                rep.check(cfg.get(key) == exp, f"{tag}: {key}={cfg.get(key)}",
                          f"期待 {exp}", quiet_ok=True)
            want_flux = world.get("chem_vent_flux", d.chem_vent_flux)
            rep.check(cfg["chem_vent_flux"] == want_flux,
                      f"{tag}: chem_vent_flux={cfg['chem_vent_flux']}",
                      f"期待 {want_flux}", quiet_ok=True)

            # --- source排他 ---
            light_supply = num(last, "light_supply_cum")
            light_flow = num(last, "flow_light_cum")
            chem_flow = num(last, "flow_chemical_cum")
            if want_flux == 0.0:
                rep.check(chem_flow == 0.0, f"{tag}: light-only で chemical flow=0",
                          str(chem_flow), quiet_ok=True)
                rep.check(light_supply > 0.0, f"{tag}: 光が供給されている",
                          quiet_ok=True)
            elif cfg["light_max"] == 0.0:
                rep.check(light_supply == 0.0 and light_flow == 0.0,
                          f"{tag}: chemical-only で光0", quiet_ok=True)
            else:
                rep.check(light_supply > 0.0 and want_flux > 0.0,
                          f"{tag}: mixed で光もchemicalも供給されている",
                          quiet_ok=True)

            # --- 診断表現型の固定 ---
            rep.check(cfg["diagnostic_gene_overrides"] == want
                      and set(cfg["fixed_genes"]) == set(want),
                      f"{tag}: 表現型 {want} を固定", quiet_ok=True)
            for gene in want:
                var_max = max(num(r, f"var_{gene}") for r in rows)
                rep.check(var_max == 0.0, f"{tag}: {gene} の分散が全期間0",
                          f"max={var_max}", quiet_ok=True)
            sim = Simulation(Config.from_json(run / "config.json"), seed)
            g0 = np.stack([o.genome for o in sim.organisms])
            rep.check(bool(np.all(g0[:, LIGHT_ABS] == want["light_absorption"]))
                      and bool(np.all(g0[:, CHEM_ABS] == want["chemical_absorption"])),
                      f"{tag}: 初期個体が事前登録の表現型", quiet_ok=True)
            for gene, val in want.items():
                vals = snapshot_gene(run, gene)
                if vals is not None:
                    rep.check(all(v == val for v in vals),
                              f"{tag}: 最終snapshotも {gene}={val} ({len(vals)} 個体)",
                              quiet_ok=True)
            if world.get("diagnostic_placement") == "vent":
                w = sim.world
                rep.check(all(w.chem_mask[w.cell_index(o.x, o.y)]
                              for o in sim.organisms),
                          f"{tag}: 初期個体が全てventセル上", quiet_ok=True)

            # --- 観測列と score順位の一致 ---
            missing = [c for c in OBS_COLUMNS if c not in last]
            rep.check(not missing, f"{tag}: V1.5観測列が揃っている",
                      f"欠け {missing}", quiet_ok=True)
            if not missing:
                agree = sum(num(r, "sel_agree") for r in rows)
                picks = sum(num(r, "sel_light") + num(r, "sel_chemical")
                            for r in rows)
                rep.check(agree == picks,
                          f"{tag}: score順位と実選択が全区間で一致",
                          f"agree={agree:.0f} picks={picks:.0f}", quiet_ok=True)

        print(f"  (各runの詳細チェックは異常時のみ表示。{cond.name} は "
              f"{len(runs)} run 分を確認)")

    print("\n" + "=" * 60)
    print(f"確認項目 {rep.checked} 件")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)}件")
        for f in rep.fails[:20]:
            print(f"  - {f}")
        return 1
    print("判定: OK — Exp09 の診断条件は全て意図どおり")
    return 0


if __name__ == "__main__":
    sys.exit(main())
