"""Exp07の条件Configを生成する (docs/Exp07_実験計画.md §3-5)。

    uv run python tools/make_exp07_configs.py          # configs/exp07/ へ書き出す
    uv run python tools/make_exp07_configs.py --check  # 既存ファイルとの一致だけ確認

8 flux × 3条件 = 24 Configを決定的に生成する。手書きしないのは、
「振るのは chem_vent_flux だけ」という事前登録条件を、24ファイルすべてで
機械的に保証するため。生成物はリポジトリへコミットし、runごとの
config.json と合わせて再現性を担保する。
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

OUT_DIR = ROOT / "configs" / "exp07"

# 事前登録: 振る世界パラメータは chem_vent_flux のみ
FLUXES = (4.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0)

# 全条件共通の固定値 (計画 §3)
COMMON = dict(
    light_pattern="uniform",
    light_max=0.0,
    stats_interval=20,
    snapshot_interval=1000,
)

CHEM_ADAPTED = dict(
    fixed_genes=["chemical_absorption"],
    diagnostic_gene_overrides={"chemical_absorption": 2.0},
)

# 条件名 -> 追加設定 (計画 §5)。A (Ancestor/Random) は情報量が低いため省略
CONDITIONS = {
    "b_ancestor_vent": dict(diagnostic_placement="vent"),
    "c_chem_vent": dict(diagnostic_placement="vent", **CHEM_ADAPTED),
    "d_chem_random": dict(diagnostic_placement="random", **CHEM_ADAPTED),
}


def config_name(flux: float, condition: str) -> str:
    return f"exp07_flux{int(flux):02d}_{condition}.json"


def build(flux: float, condition: str) -> Config:
    return Config(chem_vent_flux=flux, **COMMON, **CONDITIONS[condition])


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp07条件Configの生成")
    ap.add_argument("--check", action="store_true",
                    help="書き出さず、既存ファイルと一致するかだけ確認する")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatched: list[str] = []
    for flux in FLUXES:
        for condition in CONDITIONS:
            cfg = build(flux, condition)
            path = OUT_DIR / config_name(flux, condition)
            payload = json.dumps(dataclasses.asdict(cfg), indent=2)
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8").strip() != payload.strip():
                    mismatched.append(path.name)
            else:
                cfg.to_json(path)
                print(f"{path.relative_to(ROOT)}  flux={flux} "
                      f"placement={cfg.diagnostic_placement} "
                      f"overrides={cfg.diagnostic_gene_overrides}")

    if args.check:
        if mismatched:
            print("★ 生成結果と一致しないConfig:")
            for name in mismatched:
                print(f"  - {name}")
            print("uv run python tools/make_exp07_configs.py で再生成すること")
            return 1
        print(f"OK — {len(FLUXES) * len(CONDITIONS)} Config すべて生成結果と一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
