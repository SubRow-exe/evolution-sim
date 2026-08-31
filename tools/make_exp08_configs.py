"""Exp08の条件Configを生成する (docs/Exp08_実験計画.md §4-5)。

    uv run python tools/make_exp08_configs.py          # configs/exp08/ へ書き出す
    uv run python tools/make_exp08_configs.py --check  # 既存ファイルとの一致だけ確認

Phase A (光単独) 6 Config + Phase B (chemical単独) 3 Config = 9 Config。
手書きしないのは「Phase Aで振るのは light_uptake_coef だけ」「Phase Bで振るのは
chem_vent_flux だけ」という事前登録条件を機械的に保証するため。

Phase Aでも `n_vents=4` を維持し `chem_vent_flux=0.0` で光単独にする
(vent生成の乱数消費をPhase Bと一致させるため。`n_vents=0` にはしない)。
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

OUT_DIR = ROOT / "configs" / "exp08"

# 事前登録 (docs/Exp08_実験計画.md §4.2 / §5.1)
LIGHT_COEFS = (1.0, 1.5, 2.0, 3.0, 4.0)   # Phase A L0 で振る唯一の世界パラメータ
L2_COEF = 2.0                             # Phase A L2 は1水準のみ
CHEM_FLUXES = (8.0, 16.0, 24.0)           # Phase B で振る唯一の世界パラメータ

COMMON = dict(
    stats_interval=20,
    snapshot_interval=1000,
)

# Phase A: V1.1互換のvertical光。chemicalは供給0だがvent生成の乱数は維持する。
PHASE_A = dict(
    light_pattern="vertical",
    chem_vent_flux=0.0,
    **COMMON,
)

# Phase B: 光0・vent配置・完成chemical型
PHASE_B = dict(
    light_pattern="uniform",
    light_max=0.0,
    diagnostic_placement="vent",
    fixed_genes=["chemical_absorption"],
    diagnostic_gene_overrides={"chemical_absorption": 2.0},
    **COMMON,
)


def _coef_tag(coef: float) -> str:
    return f"{coef:.1f}".replace(".", "p")


def l0_name(coef: float) -> str:
    return f"exp08_a_l0_coef{_coef_tag(coef)}.json"


def l2_name(coef: float) -> str:
    return f"exp08_a_l2_coef{_coef_tag(coef)}.json"


def flux_name(flux: float) -> str:
    return f"exp08_b_flux{int(flux):02d}_chem.json"


def build_l0(coef: float) -> Config:
    """L0: 通常祖先のまま light_absorption を初期値 (0.3) に固定する。"""
    return Config(light_uptake_coef=coef,
                  fixed_genes=["light_absorption"], **PHASE_A)


def build_l2(coef: float) -> Config:
    """L2: 完成光型 (light_absorption=2.0固定) のpositive control。"""
    return Config(light_uptake_coef=coef,
                  fixed_genes=["light_absorption"],
                  diagnostic_gene_overrides={"light_absorption": 2.0},
                  **PHASE_A)


def build_b(flux: float) -> Config:
    return Config(chem_vent_flux=flux, **PHASE_B)


def cases() -> list[tuple[str, Config]]:
    out = [(l0_name(c), build_l0(c)) for c in LIGHT_COEFS]
    out.append((l2_name(L2_COEF), build_l2(L2_COEF)))
    out.extend((flux_name(f), build_b(f)) for f in CHEM_FLUXES)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp08条件Configの生成")
    ap.add_argument("--check", action="store_true",
                    help="書き出さず、既存ファイルと一致するかだけ確認する")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatched: list[str] = []
    built = cases()
    for name, cfg in built:
        path = OUT_DIR / name
        payload = json.dumps(dataclasses.asdict(cfg), indent=2)
        if args.check:
            if (not path.exists()
                    or path.read_text(encoding="utf-8").strip() != payload.strip()):
                mismatched.append(name)
        else:
            cfg.to_json(path)
            print(f"{path.relative_to(ROOT)}  coef={cfg.light_uptake_coef} "
                  f"light_max={cfg.light_max} flux={cfg.chem_vent_flux} "
                  f"placement={cfg.diagnostic_placement} "
                  f"overrides={cfg.diagnostic_gene_overrides}")

    if args.check:
        if mismatched:
            print("★ 生成結果と一致しないConfig:")
            for name in mismatched:
                print(f"  - {name}")
            print("uv run python tools/make_exp08_configs.py で再生成すること")
            return 1
        print(f"OK — {len(built)} Config すべて生成結果と一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
