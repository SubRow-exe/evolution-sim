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
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES, fixed_mask_from_names

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

# body_size 以外の 13 遺伝子を固定するリスト (ゲノム名)。
# 手書きしない: canonical な evosim.genome.GENE_NAMES から body_size だけを
# 除外して自動生成する。これにより遺伝子名の不整合 (誤字・数の過不足) が
# 構造的に発生しなくなる。
FIXED_GENES_NAMES: list[str] = [g for g in GENE_NAMES if g != "body_size"]
assert len(FIXED_GENES_NAMES) == 13, (
    f"body_size 以外の遺伝子数が 13 でない: {len(FIXED_GENES_NAMES)}"
)

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


EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}


def check_fixed_genes_coverage(cfg: Config) -> list[str]:
    """fixed_genes が GENE_NAMES - {"body_size"} と完全一致することを確認する。

    件数比較やローカル定数との比較ではなく、canonical な GENE_NAMES 由来の
    集合と直接比較する。不足・過剰・未知の遺伝子名をすべて検出する。

    Returns:
        エラーメッセージのリスト (空 = OK)
    """
    actual = set(cfg.fixed_genes)
    errors = []
    missing = EXPECTED_FIXED_GENES - actual
    if missing:
        errors.append(f"不足: {sorted(missing)}")
    unexpected = actual - EXPECTED_FIXED_GENES
    if unexpected:
        errors.append(f"想定外/未知の遺伝子名: {sorted(unexpected)}")
    return errors


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
        # 1. fixed_genes が GENE_NAMES - {"body_size"} と完全一致するか
        fg_errors = check_fixed_genes_coverage(cfg)
        if fg_errors:
            errors.append(f"{fname}: fixed_genes 不正 {fg_errors}")

        # 2. bmr_core 値の一致
        data = json.loads(payload)
        if data["bmr_core"] != core:
            errors.append(f"{fname}: JSON 内 bmr_core={data['bmr_core']} != {core}")

        # 3. round-trip 確認 (JSON 保存 -> Config.from_json で同じ値へ戻るか)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(payload)
            tmp_path = f.name
        try:
            loaded = Config.from_json(tmp_path)
            if loaded.bmr_core != core:
                errors.append(f"{fname}: round-trip 後 bmr_core={loaded.bmr_core} != {core}")
            fg_rt_errors = check_fixed_genes_coverage(loaded)
            if fg_rt_errors:
                errors.append(f"{fname}: round-trip 後 fixed_genes 不正 {fg_rt_errors}")
            # fixed_mask_from_names まで実際に通す (未知の遺伝子名は ValueError)
            fixed_mask_from_names(loaded.fixed_genes)
        except ValueError as e:
            errors.append(f"{fname}: fixed_mask_from_names 失敗: {e}")
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
