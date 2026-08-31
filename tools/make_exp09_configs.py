"""Exp09の条件Configを生成する (docs/Exp09_実験計画.md §7)。

    uv run python tools/make_exp09_configs.py          # configs/exp09/ へ書き出す
    uv run python tools/make_exp09_configs.py --check  # 既存ファイルとの一致だけ確認

Phase B (短時間の混合世界sanity check) の5条件。
手書きしないのは「振るのは光/chemicalの有無と診断表現型だけ」という
事前登録条件を機械的に保証するため。

世界パラメータはV1.4で確定した恒久defaultをそのまま使う
(`light_uptake_coef=2.0` / `chem_vent_flux=16.0` / `chem_uptake=0.5`)。
V1.5の受容器スケール (`light_stimulus_half=1.2` /
`chemical_stimulus_half=12.3` / `stimulus_tie_eps=1e-9`) もdefaultのまま。
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

OUT_DIR = ROOT / "configs" / "exp09"

# 事前登録の診断表現型 (docs/Exp09_実験計画.md §7)
PHENOTYPES = {
    "lightspec": {"light_absorption": 2.0, "chemical_absorption": 0.3},
    "chemspec": {"light_absorption": 0.3, "chemical_absorption": 2.0},
    "generalist": {"light_absorption": 1.0, "chemical_absorption": 1.0},
}
FIXED = ["light_absorption", "chemical_absorption"]

COMMON = dict(
    fixed_genes=FIXED,
    stats_interval=20,
    snapshot_interval=1000,
)

# 条件名 -> (世界設定, 表現型)
CONDITIONS = {
    # 単独source control。V1.5でもV1.4と同じ行動になることを実runでも見る
    "a_light_only_lightspec": (dict(chem_vent_flux=0.0), "lightspec"),
    "b_chem_only_chemspec": (dict(light_pattern="uniform", light_max=0.0,
                                  diagnostic_placement="vent"), "chemspec"),
    # 混合世界 (vertical光 + chemical vent)。配置はrandomで揃える
    "c_mixed_lightspec": ({}, "lightspec"),
    "d_mixed_chemspec": ({}, "chemspec"),
    "e_mixed_generalist": ({}, "generalist"),
}


def config_name(condition: str) -> str:
    return f"exp09_{condition}.json"


def build(condition: str) -> Config:
    world, pheno = CONDITIONS[condition]
    return Config(diagnostic_gene_overrides=dict(PHENOTYPES[pheno]),
                  **COMMON, **world)


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp09条件Configの生成")
    ap.add_argument("--check", action="store_true",
                    help="書き出さず、既存ファイルと一致するかだけ確認する")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatched: list[str] = []
    for condition in CONDITIONS:
        cfg = build(condition)
        path = OUT_DIR / config_name(condition)
        payload = json.dumps(dataclasses.asdict(cfg), indent=2)
        if args.check:
            if (not path.exists()
                    or path.read_text(encoding="utf-8").strip() != payload.strip()):
                mismatched.append(path.name)
        else:
            cfg.to_json(path)
            print(f"{path.relative_to(ROOT)}  light_max={cfg.light_max} "
                  f"flux={cfg.chem_vent_flux} "
                  f"placement={cfg.diagnostic_placement} "
                  f"genes={cfg.diagnostic_gene_overrides}")

    if args.check:
        if mismatched:
            print("★ 生成結果と一致しないConfig:")
            for name in mismatched:
                print(f"  - {name}")
            print("uv run python tools/make_exp09_configs.py で再生成すること")
            return 1
        print(f"OK — {len(CONDITIONS)} Config すべて生成結果と一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
