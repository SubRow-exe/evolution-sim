"""Exp10 Phase B の条件Configを生成する (docs/Exp10_実験計画案.md §5)。

    uv run python tools/make_exp10_configs.py                 # 生成
    uv run python tools/make_exp10_configs.py --check         # 一致確認のみ

Phase Aで選ばれた**1候補だけ**をfull simulationへ持ち込む (計画 §5)。
その候補は `tools/summarize_exp10.py --write-selection` が事前登録規則
(§4.7: 最小response_gain → 同gainなら最短memory_tau) で機械的に決めた
`phaseA_selection.json` から読む。ここで手で選ばない。

条件 (§5.2) — 世界と表現型はExp09と同じにして連続性を保つ:

    B1 light-only  / light specialist
    B2 chem-only   / chemical specialist
    B3 mixed       / light specialist
    B4 mixed       / chemical specialist
    B5 mixed       / generalist

行動則 (§5.1):

    control   response_gain = 0   (pure random walk)
    treatment Phase A選定値

振ってよいのは「光/chemicalの有無」「診断表現型」「行動則パラメータ」だけ。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES

OUT_DIR = ROOT / "configs" / "exp10"
SELECTION = ROOT / "configs" / "exp10" / "phaseA_selection.json"

# 診断表現型 (Exp09 / Phase A と同一)
PHENOTYPES = {
    "lightspec": {"light_absorption": 2.0, "chemical_absorption": 0.3},
    "chemspec": {"light_absorption": 0.3, "chemical_absorption": 2.0},
    "generalist": {"light_absorption": 1.0, "chemical_absorption": 1.0},
}

# 進化OFF: Phase Bは「行動則の軸だけ」を control/treatment で振る診断であり、
# 表現型は全世代固定でなければならない (Issue #41 「Phase B 正式再トライアル方針」)。
# 旧実装は light/chemical の2吸収能力しか固定しておらず、body_size 等の
# 残り12遺伝子が自由進化していた (中間報告の個体数20倍・小型化はその帰結)。
# 全14遺伝子を固定して、当初事前登録どおりの「進化OFF・固定表現型」へ戻す。
# diagnostic_gene_overrides は表現型2遺伝子だけ初期値を上書きし、残りは
# INITIAL_GENOME のまま据え置く (固定遺伝子は初期ばらつきも変異も受けない)。
FIXED = list(GENE_NAMES)

COMMON = dict(
    fixed_genes=FIXED,
    stats_interval=20,
    snapshot_interval=2000,
)

# 条件名 -> (世界設定, 表現型)
CONDITIONS = {
    "b1_light_only_lightspec": (dict(chem_vent_flux=0.0), "lightspec"),
    "b2_chem_only_chemspec": (dict(light_pattern="uniform", light_max=0.0,
                                   diagnostic_placement="vent"), "chemspec"),
    "b3_mixed_lightspec": ({}, "lightspec"),
    "b4_mixed_chemspec": ({}, "chemspec"),
    "b5_mixed_generalist": ({}, "generalist"),
}
RULES = ("control", "treatment")
CONTROL_GAIN = 0.0


def load_selection() -> dict:
    if not SELECTION.exists():
        raise SystemExit(
            f"{SELECTION.relative_to(ROOT)} が無い。\n"
            "先に Phase A を走らせ、\n"
            "  uv run python tools/summarize_exp10.py <phaseA> --write-selection\n"
            "で選定結果を作り、configs/exp10/ へ置くこと (計画 §5)。")
    return json.loads(SELECTION.read_text(encoding="utf-8"))


def config_name(condition: str, rule: str) -> str:
    return f"exp10_{condition}_{rule}.json"


def build(condition: str, rule: str, sel: dict) -> Config:
    world, pheno = CONDITIONS[condition]
    if rule == "control":
        beh = dict(response_gain=CONTROL_GAIN, memory_tau=sel["memory_tau"])
    else:
        beh = dict(response_gain=sel["response_gain"],
                   memory_tau=sel["memory_tau"])
    return Config(diagnostic_gene_overrides=dict(PHENOTYPES[pheno]),
                  **COMMON, **beh, **world)


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp10 Phase B条件Configの生成")
    ap.add_argument("--check", action="store_true",
                    help="書き出さず、既存ファイルと一致するかだけ確認する")
    args = ap.parse_args()

    sel = load_selection()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatched: list[str] = []
    for condition in CONDITIONS:
        for rule in RULES:
            cfg = build(condition, rule, sel)
            path = OUT_DIR / config_name(condition, rule)
            payload = json.dumps(dataclasses.asdict(cfg), indent=2)
            if args.check:
                if (not path.exists()
                        or path.read_text(encoding="utf-8").strip()
                        != payload.strip()):
                    mismatched.append(path.name)
            else:
                cfg.to_json(path)
                print(f"{path.relative_to(ROOT)}  light_max={cfg.light_max} "
                      f"flux={cfg.chem_vent_flux} "
                      f"gain={cfg.response_gain} tau={cfg.memory_tau} "
                      f"genes={cfg.diagnostic_gene_overrides}")

    if args.check:
        if mismatched:
            print("★ 生成結果と一致しないConfig:")
            for name in mismatched:
                print(f"  - {name}")
            print("uv run python tools/make_exp10_configs.py で再生成すること")
            return 1
        print(f"OK — {len(CONDITIONS) * len(RULES)} Config すべて生成結果と一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
