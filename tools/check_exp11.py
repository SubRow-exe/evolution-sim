"""Exp11 Config整合性チェッカー (docs/Exp11_実験計画案.md §13 / P0-4, P0-5)。

確認項目:
  - 全45 Config が make_exp11_configs.py の生成物と一致する
  - body_size 以外の 13 遺伝子が fixed_genes に含まれる
  - body_size が fixed_genes に含まれない
  - bmr_core が JSON round-trip で保持される
  - 全 Config の bmr_core 値が候補 15 水準のいずれか

使い方:
    uv run python tools/check_exp11.py              # 全45 Config を検証
    uv run python tools/check_exp11.py runs/exp11   # 実行済み run の config.json も検証
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config

CONFIGS_DIR = ROOT / "configs" / "exp11"

BMR_CORE_CANDIDATES = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

FIXED_GENES_REQUIRED = [
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


def check_config(path: Path) -> list[str]:
    """Config ファイルを検証し、エラーメッセージのリストを返す。空 = OK。"""
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path.name}: JSON 読み込みエラー: {e}"]

    # bmr_core キーの存在
    if "bmr_core" not in data:
        errors.append(f"{path.name}: bmr_core フィールドが存在しない")
        return errors

    core = data["bmr_core"]

    # bmr_core が候補値のいずれか
    is_candidate = any(abs(core - c) < 1e-9 for c in BMR_CORE_CANDIDATES)
    if not is_candidate:
        errors.append(f"{path.name}: bmr_core={core} は候補 15 水準に含まれない")

    # Config.from_json で読み込めるか
    try:
        loaded = Config.from_json(path)
    except Exception as e:
        errors.append(f"{path.name}: Config.from_json 失敗: {e}")
        return errors

    # round-trip: JSON 値と loaded 値が一致
    if abs(loaded.bmr_core - core) > 1e-12:
        errors.append(
            f"{path.name}: round-trip 後 bmr_core={loaded.bmr_core} != JSON 値 {core}"
        )

    # fixed_genes: 必須 13 遺伝子がすべて含まれる
    fg = loaded.fixed_genes
    for gene in FIXED_GENES_REQUIRED:
        if gene not in fg:
            errors.append(f"{path.name}: {gene} が fixed_genes に含まれていない")

    # body_size が fixed_genes に含まれていない
    if "body_size" in fg:
        errors.append(f"{path.name}: body_size が fixed_genes に含まれている (進化 OFF になる)")

    return errors


def check_run_configs(run_dirs: list[Path]) -> list[str]:
    """実行済み run ディレクトリ内の config.json を検証する。"""
    errors = []
    for run_dir in run_dirs:
        cfg_path = run_dir / "config.json"
        if not cfg_path.exists():
            errors.append(f"{run_dir}: config.json が存在しない")
            continue
        errs = check_config(cfg_path)
        errors.extend(errs)
    return errors


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp11 Config 整合性チェック")
    ap.add_argument("run_dirs", nargs="*", type=Path,
                    help="実行済み run ディレクトリ (省略時は configs/exp11/ のみ確認)")
    args = ap.parse_args()

    errors = []

    # configs/exp11/ の全45 Config を検証
    cfg_files = sorted(CONFIGS_DIR.glob("exp11_*.json"))
    if not cfg_files:
        errors.append(f"configs/exp11/ に exp11_*.json が存在しない。"
                      "make_exp11_configs.py を先に実行してください")
    elif len(cfg_files) != 45:
        errors.append(f"Config 数が {len(cfg_files)} (期待: 45)")

    for path in cfg_files:
        errors.extend(check_config(path))

    # 実行済み run ディレクトリ
    if args.run_dirs:
        run_dirs = []
        for d in args.run_dirs:
            if d.is_dir():
                # 直下の run ディレクトリ (子ディレクトリが run)
                children = [c for c in d.iterdir() if c.is_dir()]
                if children:
                    run_dirs.extend(children)
                else:
                    run_dirs.append(d)
        errors.extend(check_run_configs(run_dirs))

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    n = len(cfg_files)
    print(f"OK: 全 {n} Config 整合性チェック通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
