"""Exp10 Phase B 診断条件の成立チェック (docs/Exp10_実験計画案.md §5)。

    uv run python tools/check_exp10.py runs/exp10 --seeds 1-20

「結果を解釈する前に、意図した条件で走っていたか」だけを確認する。
high-Q滞在率や生存率といった科学的結果は判定しない (それが観測対象)。

確認する前提:

- 条件ディレクトリと期待seedが揃っている
- V1.4恒久default (`light_uptake_coef=2.0` / `chem_vent_flux=16.0` /
  `chem_uptake=0.5`) とV1.5受容器スケール (1.2 / 12.3) がdefaultのまま
- 行動則パラメータが事前登録どおり
  (control は `response_gain=0`、treatment はPhase A選定値。
   `memory_tau` は両者で同一)
- source排他: light-only は累積 chemical flow=0、chemical-only は
  光供給・累積 light flow がともに0、mixed は両方>0
- **進化OFF**: 全14遺伝子が fixed_genes に入り、全個体・全期間で分散0
  (診断表現型2遺伝子は事前登録値、残り12遺伝子は INITIAL_GENOME 据え置き)。
  初期・最終snapshotとも全遺伝子が個体間で厳密に一定
- V1.6観測列が欠けていない
- 帯別観測の内訳が全体と整合する

`--cases` を渡すと、そのバッチで走らせるべき条件だけを必須扱いにする
(40 run分割実行での「未実行条件」を run不足と誤検知しない)。渡さなければ
Phase B全10条件を必須扱いにする。

これらは「意図した条件で走ったか」の整合性チェックであり、崩れていれば
非ゼロ終了する (workflow failure に相当)。生存率などの科学的判定はしない。
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

from tools.make_exp10_configs import (CONDITIONS, CONTROL_GAIN,  # noqa: E402
                                      PHENOTYPES, RULES, load_selection)

OBS_COLUMNS = ("sel_walk", "stim_events", "q_mean", "q_mem_mean", "dq_mean",
               "dq_abs_mean", "dq_light_mean", "dq_chem_mean",
               "turn_factor_mean", "sigma_eff_mean",
               "r_light_mean", "r_chem_mean",
               "dq_pos", "dq_neg", "dq_zero")
BANDS = ("d0_1", "d1_2", "d2_4", "d4plus")


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
    ap = argparse.ArgumentParser(description="Exp10 Phase B 診断条件チェック")
    ap.add_argument("exp_dir")
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--cases", default="",
                    help="このバッチで必須の条件 (カンマ区切り。省略で全10条件)")
    args = ap.parse_args()

    base = Path(args.exp_dir)
    want_seeds = parse_seeds(args.seeds)
    sel = load_selection()
    rep = Report()

    names = {f"{c}_{r}": (c, r) for c in CONDITIONS for r in RULES}
    expected = ([c.strip() for c in args.cases.split(",") if c.strip()]
                if args.cases else list(names))
    unknown = [c for c in expected if c not in names]
    if unknown:
        print(f"NG  未知の条件が --cases に含まれる: {unknown}")
        return 1
    conds = sorted(d for d in base.iterdir() if d.is_dir() and d.name in names)
    present = {d.name for d in conds}
    if not conds:
        print(f"NG  {base} に Exp10 の条件ディレクトリが無い")
        return 1

    # このバッチで走らせるべき条件が揃っているか (run不足の検知)。
    # バッチ外の条件は N/A として扱い、存在しなくても失敗にしない。
    for c in expected:
        rep.check(c in present, f"必須条件 {c} が存在する",
                  "このバッチで実行予定の条件が見つからない (run不足)")
    for skipped in sorted(present - set(expected)):
        print(f"  --  {skipped}: このバッチ外 (N/A)。整合性のみ確認する")

    from evosim.config import Config
    from evosim.genome import GENE_NAMES, INITIAL_GENOME  # noqa: E402
    from evosim.simulation import Simulation
    d = Config()

    for cond in conds:
        cname, rule = names[cond.name]
        world, pheno = CONDITIONS[cname]
        want = PHENOTYPES[pheno]
        want_gain = CONTROL_GAIN if rule == "control" else sel["response_gain"]
        runs = run_dirs(cond)
        print(f"\n=== {cond.name} ({len(runs)} run / {pheno} / {rule}) ===")
        rep.check(sorted(runs) == want_seeds,
                  f"{cond.name}: seed {sorted(runs)}", f"期待 {want_seeds}")

        for seed in sorted(runs):
            run = runs[seed]
            tag = f"{cond.name} s{seed}"
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            rows = rows_of(run)
            last = rows[-1]

            # --- 世界default ---
            for key, exp in (("light_uptake_coef", d.light_uptake_coef),
                             ("chem_uptake", d.chem_uptake),
                             ("light_stimulus_half", d.light_stimulus_half),
                             ("chemical_stimulus_half", d.chemical_stimulus_half),
                             ("n_vents", d.n_vents)):
                rep.check(cfg.get(key) == exp, f"{tag}: {key}={cfg.get(key)}",
                          f"期待 {exp}", quiet_ok=True)
            want_flux = world.get("chem_vent_flux", d.chem_vent_flux)
            rep.check(cfg["chem_vent_flux"] == want_flux,
                      f"{tag}: chem_vent_flux={cfg['chem_vent_flux']}",
                      f"期待 {want_flux}", quiet_ok=True)

            # --- 行動則パラメータ ---
            rep.check(cfg["response_gain"] == want_gain,
                      f"{tag}: response_gain={cfg['response_gain']}",
                      f"期待 {want_gain}", quiet_ok=True)
            rep.check(cfg["memory_tau"] == sel["memory_tau"],
                      f"{tag}: memory_tau={cfg['memory_tau']}",
                      f"期待 {sel['memory_tau']}", quiet_ok=True)

            # --- source排他 ---
            light_supply = num(last, "light_supply_cum")
            light_flow = num(last, "flow_light_cum")
            chem_flow = num(last, "flow_chemical_cum")
            if want_flux == 0.0:
                rep.check(chem_flow == 0.0,
                          f"{tag}: light-only で chemical flow=0",
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

            # --- 進化OFF: 全遺伝子が全世代固定 ---
            # 期待する固定値: 表現型2遺伝子は事前登録値、残りは INITIAL_GENOME。
            want_gene = {g: float(INITIAL_GENOME[GENE_NAMES.index(g)])
                         for g in GENE_NAMES}
            want_gene.update(want)
            rep.check(cfg["diagnostic_gene_overrides"] == want,
                      f"{tag}: 表現型 override が {want}", quiet_ok=True)
            rep.check(set(cfg["fixed_genes"]) == set(GENE_NAMES),
                      f"{tag}: 全14遺伝子が固定 (進化OFF)",
                      f"fixed={sorted(cfg['fixed_genes'])}", quiet_ok=True)
            # (a) stats.csv の分散が全遺伝子・全期間で厳密0
            for gene in GENE_NAMES:
                var_max = max(num(r, f"var_{gene}") for r in rows)
                rep.check(var_max == 0.0,
                          f"{tag}: {gene} の分散が全期間0",
                          f"max={var_max}", quiet_ok=True)
            # (b) 初期個体群が全遺伝子で期待値・個体間一定
            sim = Simulation(Config.from_json(run / "config.json"), seed)
            g0 = np.stack([o.genome for o in sim.organisms])
            for gene, val in want_gene.items():
                col = g0[:, GENE_NAMES.index(gene)]
                rep.check(bool(np.all(col == val)),
                          f"{tag}: 初期個体の {gene}={val}",
                          f"実測 min={col.min()} max={col.max()}", quiet_ok=True)
            # (c) 最終snapshotも全遺伝子で期待値・個体間一定
            # 絶滅した run の最終snapshotは個体0で空になる (Exp10では絶滅は
            # 測定結果)。空なら検証対象が無いのでスキップする。
            for gene, val in want_gene.items():
                vals = snapshot_gene(run, gene)
                if vals:
                    rep.check(all(v == val for v in vals),
                              f"{tag}: 最終snapshotも {gene}={val}",
                              f"min={min(vals)} max={max(vals)}", quiet_ok=True)

            # --- 観測列 ---
            missing = [c for c in OBS_COLUMNS if c not in last]
            missing += [f"band_{b}_{k}" for b in BANDS
                        for k in ("n", "dq_light", "dq_chem", "sigma_eff",
                                  "light_e", "chem_e")
                        if f"band_{b}_{k}" not in last]
            rep.check(not missing, f"{tag}: V1.6観測列が揃っている",
                      f"欠け {missing[:5]}", quiet_ok=True)
            if not missing:
                band_n = sum(sum(num(r, f"band_{b}_n") for b in BANDS)
                             for r in rows)
                ev = sum(num(r, "stim_events") for r in rows)
                rep.check(band_n == ev,
                          f"{tag}: 帯別内訳が全体と一致",
                          f"band計={band_n:.0f} events={ev:.0f}", quiet_ok=True)
                # controlでは常にbaseline幅 (turn_factor=1)
                if rule == "control":
                    tf = [num(r, "turn_factor_mean") for r in rows
                          if r.get("turn_factor_mean") not in ("", None)]
                    rep.check(all(abs(v - 1.0) < 1e-9 for v in tf),
                              f"{tag}: control は turn_factor=1 のまま",
                              quiet_ok=True)

        print(f"  (詳細は異常時のみ表示。{cond.name} は {len(runs)} run 分を確認)")

    print("\n" + "=" * 60)
    print(f"確認項目 {rep.checked} 件")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)}件")
        for f in rep.fails[:20]:
            print(f"  - {f}")
        return 1
    print("判定: OK — Exp10 Phase B の診断条件は全て意図どおり")
    return 0


if __name__ == "__main__":
    sys.exit(main())
