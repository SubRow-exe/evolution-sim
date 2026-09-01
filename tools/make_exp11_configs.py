"""Exp11の全45 Config (15 bmr_core × 3環境) を生成する。

    uv run python tools/make_exp11_configs.py          # configs/exp11/ へ書き出す
    uv run python tools/make_exp11_configs.py --check  # 既存ファイルとの一致だけ確認

仕様: docs/Exp11_実験計画案.md §4–8。

事前登録条件:
  - B1 light-only / lightspec : 15 × seed1-8  = 120 run
  - B2 chem-only  / chemspec  : 15 × seed1-5  =  75 run
  - B3 mixed      / generalist: 15 × seed1-4  =  60 run
  - 合計 255 run

共通 (仕様 §4):
  ticks=10000 / initial_population=100 / initial_energy=50 / initial_matter=0.8
  body_size のみ進化 ON、他 13 遺伝子固定
  memory_tau=10 / response_gain=64
  stats_interval=20 / snapshot_interval=1000 / max_population_halt=10000

各 Config に bmr_core を含め、JSON round-trip で消えないことを保証する。
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
from evosim.genome import (
    BODY_SIZE, CHEM_ABS, CORPSE_DIG, DAMAGE_RES, LIGHT_ABS,
    MEMBRANE, MOVE_EFF, NUTRIENT_ABS, PREDATION, REPAIR, SENSORY,
)

OUT_DIR = ROOT / "configs" / "exp11"

# --------------------------------------------------------------------------
# Exp11 候補 15 水準 (docs/Exp11_実験計画案.md §2)
# --------------------------------------------------------------------------
BMR_CORE_CANDIDATES = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

# --------------------------------------------------------------------------
# 表現型 (固定遺伝子値)
# body_size のみ進化 ON → fixed_genes に含めない
# --------------------------------------------------------------------------
PHENOTYPES: dict[str, dict[str, float]] = {
    "lightspec": {
        "light_absorption": 2.0,
        "chemical_absorption": 0.3,
    },
    "chemspec": {
        "light_absorption": 0.3,
        "chemical_absorption": 2.0,
    },
    "generalist": {
        "light_absorption": 1.0,
        "chemical_absorption": 1.0,
    },
}

# body_size 以外の 13 遺伝子を固定するリスト (ゲノム名)
# body_size (BODY_SIZE) は除く
FIXED_GENES_NAMES: list[str] = [
    "light_absorption",
    "chemical_absorption",
    "nutrient_absorption",
    "corpse_digestion",
    "predation",
    "membrane",
    "damage_resistance",
    "move_efficiency",
    "repair",
    "sensory_range",
]
# genome.py のキー名に合わせる (診断 gene override と fixed_genes は文字列)

# --------------------------------------------------------------------------
# 環境条件ごとの世界設定
# --------------------------------------------------------------------------
# B1: light-only / lightspec
B1_WORLD = dict(
    light_pattern="vertical",   # 標準光場
    chem_vent_flux=0.0,          # chemical off
    diagnostic_placement="random",
)

# B2: chem-only / chemspec
B2_WORLD = dict(
    light_pattern="uniform",
    light_max=0.0,               # light off
    chem_vent_flux=16.0,
    diagnostic_placement="vent",
)

# B3: mixed / generalist
B3_WORLD = dict(
    light_pattern="vertical",
    chem_vent_flux=16.0,
    diagnostic_placement="random",
)

ENVIRONMENTS: dict[str, tuple[dict, str]] = {
    "B1_lightonly_lightspec": (B1_WORLD, "lightspec"),
    "B2_chemonly_chemspec": (B2_WORLD, "chemspec"),
    "B3_mixed_generalist": (B3_WORLD, "generalist"),
}

# 共通パラメータ (ticks は Config フィールドではなく Actions workflow で指定)
COMMON = dict(
    initial_population=100,
    initial_energy=50.0,
    initial_matter=0.8,
    memory_tau=10.0,
    response_gain=64.0,
    stats_interval=20,
    snapshot_interval=1000,
    max_population_halt=10000,
    fixed_genes=FIXED_GENES_NAMES,
)

# ticks は workflow で指定する実行時パラメータ
EXP11_TICKS = 10000


def config_name(env: str, core: float) -> str:
    return f"exp11_{env}_bmr{core:.3f}.json"


def build(env: str, core: float) -> Config:
    world_kw, pheno_key = ENVIRONMENTS[env]
    pheno = PHENOTYPES[pheno_key]
    cfg = Config(
        bmr_core=core,
        diagnostic_gene_overrides=dict(pheno),
        **COMMON,
        **world_kw,
    )
    return cfg


def all_configs() -> list[tuple[str, float, Config]]:
    result = []
    for env in ENVIRONMENTS:
        for core in BMR_CORE_CANDIDATES:
            result.append((env, core, build(env, core)))
    return result


def check_fixed_genes_coverage(cfg: Config) -> list[str]:
    """body_size 以外の 13 遺伝子が全て fixed_genes に含まれることを確認する。

    Returns:
        不足している遺伝子名のリスト (空 = OK)
    """
    missing = []
    for name in FIXED_GENES_NAMES:
        if name not in cfg.fixed_genes:
            missing.append(name)
    # body_size が fixed_genes に入っていたら誤り
    if "body_size" in cfg.fixed_genes:
        missing.append("ERROR: body_size が fixed_genes に含まれている")
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp11 全45 Config 生成")
    ap.add_argument("--check", action="store_true",
                    help="書き出さず、既存ファイルとの一致と整合性だけ確認")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    configs = all_configs()
    assert len(configs) == 45, f"45 Config のはずが {len(configs)} 個"

    for env, core, cfg in configs:
        fname = config_name(env, core)
        path = OUT_DIR / fname
        payload = json.dumps(dataclasses.asdict(cfg), indent=2)

        # ----- 整合性チェック -----
        # 1. fixed_genes coverage
        missing = check_fixed_genes_coverage(cfg)
        if missing:
            errors.append(f"{fname}: fixed_genes 不足 {missing}")

        # 2. bmr_core 値の一致
        data = json.loads(payload)
        if data["bmr_core"] != core:
            errors.append(f"{fname}: JSON 内 bmr_core={data['bmr_core']} != {core}")

        # 3. round-trip 確認
        loaded = Config.from_json_str(payload) if hasattr(Config, "from_json_str") else None
        # from_json は Path 経由なので tmp で検証
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(payload)
            tmp_path = f.name
        try:
            loaded = Config.from_json(tmp_path)
            if loaded.bmr_core != core:
                errors.append(f"{fname}: round-trip 後 bmr_core={loaded.bmr_core} != {core}")
        finally:
            os.unlink(tmp_path)

        if args.check:
            if not path.exists():
                errors.append(f"{fname}: ファイルが存在しない")
            elif path.read_text(encoding="utf-8").strip() != payload.strip():
                errors.append(f"{fname}: 内容が一致しない")
        else:
            path.write_text(payload, encoding="utf-8")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    action = "確認" if args.check else "生成"
    print(f"Exp11 全 {len(configs)} Config {action}完了 → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
