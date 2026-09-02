"""Exp12の全71 Config (B1: 7 bmr_core×8 seed分のConfig単位45… 実際はConfig単位は
bmr_core×環境の組で、seedはActions matrixで振る。) を生成する。

Exp11同様、Config自体はbmr_core×環境の組で1ファイル (seedはworkflow matrixが
振る実行時パラメータ)。

    uv run python tools/make_exp12_configs.py          # configs/exp12/ へ書き出す
    uv run python tools/make_exp12_configs.py --check  # 既存ファイルとの一致だけ確認

仕様: docs/Exp12_実験計画確定.md §3-4, §18。

事前登録条件:
  - B1 light-only / lightspec : 7 bmr_core × seed1-8 = 56 run
  - B2 chem-only  / chemspec  : 3 bmr_core × seed1-5 = 15 run
  - 合計 71 run

共通 (§4):
  ticks=50000 (workflow実行時パラメータ。Config自体には含まない)
  initial_population=100 / initial_energy=50 / initial_matter=0.8
  body_size のみ進化 ON、他13遺伝子固定
  memory_tau=10 / response_gain=64
  stats_interval=20 / snapshot_interval=1000 / max_population_halt=10000
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
from tools.exp12_common import (
    B1_BMR_CORE, B2_BMR_CORE, B1_SEEDS, B2_SEEDS, COMMON_CONFIG, TICKS,
    TOTAL_RUNS,
)

OUT_DIR = ROOT / "configs" / "exp12"

# --------------------------------------------------------------------------
# 表現型 (Exp11と同一テンプレート)
# --------------------------------------------------------------------------
PHENOTYPES: dict[str, dict[str, float]] = {
    "lightspec": {"light_absorption": 2.0, "chemical_absorption": 0.3},
    "chemspec": {"light_absorption": 0.3, "chemical_absorption": 2.0},
}

# body_size 以外の13遺伝子を固定するリスト。手書きしない。
FIXED_GENES_NAMES: list[str] = [g for g in GENE_NAMES if g != "body_size"]
assert len(FIXED_GENES_NAMES) == 13, (
    f"body_size 以外の遺伝子数が 13 でない: {len(FIXED_GENES_NAMES)}"
)

# B1: light-only / lightspec (Exp11 B1テンプレート)
B1_WORLD = dict(
    light_pattern="vertical",
    chem_vent_flux=0.0,
    diagnostic_placement="random",
)
# B2: chem-only / chemspec (Exp11 B2テンプレート)
B2_WORLD = dict(
    light_pattern="uniform",
    light_max=0.0,
    chem_vent_flux=16.0,
    diagnostic_placement="vent",
)

ENVIRONMENTS: dict[str, tuple[dict, str]] = {
    "B1_lightonly_lightspec": (B1_WORLD, "lightspec"),
    "B2_chemonly_chemspec": (B2_WORLD, "chemspec"),
}

COMMON = dict(**COMMON_CONFIG, fixed_genes=FIXED_GENES_NAMES)

EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}


def config_name(env: str, core: float) -> str:
    return f"exp12_{env}_bmr{core:.3f}.json"


def build(env: str, core: float) -> Config:
    world_kw, pheno_key = ENVIRONMENTS[env]
    pheno = PHENOTYPES[pheno_key]
    return Config(
        bmr_core=core,
        diagnostic_gene_overrides=dict(pheno),
        **COMMON,
        **world_kw,
    )


def all_configs() -> list[tuple[str, float, Config]]:
    result = []
    for core in B1_BMR_CORE:
        result.append(("B1_lightonly_lightspec", core, build("B1_lightonly_lightspec", core)))
    for core in B2_BMR_CORE:
        result.append(("B2_chemonly_chemspec", core, build("B2_chemonly_chemspec", core)))
    return result


def check_fixed_genes_coverage(cfg: Config) -> list[str]:
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
    ap = argparse.ArgumentParser(description="Exp12 Config (bmr_core×環境) 生成")
    ap.add_argument("--check", action="store_true",
                    help="書き出さず、既存ファイルとの一致と整合性だけ確認")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    configs = all_configs()
    n_configs = len(B1_BMR_CORE) + len(B2_BMR_CORE)
    assert len(configs) == n_configs, f"{n_configs} Config のはずが {len(configs)} 個"

    for env, core, cfg in configs:
        fname = config_name(env, core)
        path = OUT_DIR / fname
        payload = json.dumps(dataclasses.asdict(cfg), indent=2)

        fg_errors = check_fixed_genes_coverage(cfg)
        if fg_errors:
            errors.append(f"{fname}: fixed_genes 不正 {fg_errors}")

        data = json.loads(payload)
        if data["bmr_core"] != core:
            errors.append(f"{fname}: JSON 内 bmr_core={data['bmr_core']} != {core}")

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
    print(f"Exp12 全 {len(configs)} Config (bmr_core×環境) {action}完了 → {OUT_DIR} "
          f"(実行時 seed 展開で total {TOTAL_RUNS} run / ticks={TICKS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
