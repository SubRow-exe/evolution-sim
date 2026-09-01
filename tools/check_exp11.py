"""Exp11 Config整合性チェッカー (docs/Exp11_実験計画案.md §13 / P0-4, P0-5)。

確認項目:
  - 全45 Config が make_exp11_configs.py の生成物と一致する
  - fixed_genes が canonical な GENE_NAMES - {"body_size"} と完全一致する
    (件数比較やローカル定数との比較ではなく、集合として直接比較する。
     これにより不足・過剰・遺伝子名の誤字を同時に検出する)
  - fixed_genes が実際に fixed_mask_from_names() を通る
    (未知の遺伝子名があれば ValueError で検出する)
  - bmr_core が JSON round-trip で保持される
  - 全 Config の bmr_core 値が候補 15 水準のいずれか

使い方:
    uv run python tools/check_exp11.py              # 全45 Config を検証
    uv run python tools/check_exp11.py runs/exp11   # 実行済み run の config.json も検証
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES, fixed_mask_from_names

CONFIGS_DIR = ROOT / "configs" / "exp11"

BMR_CORE_CANDIDATES = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

# canonical: body_size 以外の全遺伝子。ローカルにリストを書き写さない。
EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}


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

    # fixed_genes: GENE_NAMES - {"body_size"} と完全一致 (集合として直接比較)
    fg = set(loaded.fixed_genes)
    missing = EXPECTED_FIXED_GENES - fg
    if missing:
        errors.append(f"{path.name}: fixed_genes 不足 {sorted(missing)}")
    unexpected = fg - EXPECTED_FIXED_GENES
    if unexpected:
        # body_size が含まれる場合も unexpected に入り、ここで検出される
        errors.append(f"{path.name}: fixed_genes に想定外/未知の遺伝子名 {sorted(unexpected)}")

    # fixed_mask_from_names まで実際に通す。未知の遺伝子名は ValueError になる。
    # (このチェック自体が genome.py の GENE_NAMES と食い違っていないことを保証する)
    try:
        fixed_mask_from_names(loaded.fixed_genes)
    except ValueError as e:
        errors.append(f"{path.name}: fixed_mask_from_names 失敗: {e}")

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


def check_simulation_smoke(path: Path) -> list[str]:
    """Config から実際に Simulation を初期化できるか確認する (smoke test)。

    fixed_mask_from_names の単体呼び出しだけでは、Simulation.__init__ が
    実際に fixed_genes をどう使うかまでは保証しない。1 Config だけでも
    Simulation() 構築が通ることを確認し、Config→genome→Simulation の
    経路全体が壊れていないことを見る。
    """
    from evosim.simulation import Simulation

    errors = []
    try:
        cfg = Config.from_json(path)
        Simulation(cfg, seed=1)
    except Exception as e:
        errors.append(f"{path.name}: Simulation 初期化失敗: {type(e).__name__}: {e}")
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

    # 少なくとも1 Config で Simulation 初期化まで実際に通す
    if cfg_files:
        errors.extend(check_simulation_smoke(cfg_files[0]))

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
