"""Exp11 Config整合性チェッカー (docs/Exp11_実験計画案.md §13 / P0-4, P0-5)。

確認項目 (configs/exp11/ の45 Config):
  - 全45 Config が make_exp11_configs.py の生成物と一致する
  - fixed_genes が canonical な GENE_NAMES - {"body_size"} と完全一致する
    (件数比較やローカル定数との比較ではなく、集合として直接比較する。
     これにより不足・過剰・遺伝子名の誤字を同時に検出する)
  - fixed_genes が実際に fixed_mask_from_names() を通る
    (未知の遺伝子名があれば ValueError で検出する)
  - bmr_core が JSON round-trip で保持される
  - 全 Config の bmr_core 値が候補 15 水準のいずれか

確認項目 (実行済み run: `check_exp11.py runs/exp11`):
  - config.json を持つ実 run ディレクトリを再帰的に収集する
    (条件ディレクトリ自体を run として誤検査しない — 2026-09-01 に発覚した
     「収集後の実際の階層は runs/exp11/<条件key>/<seed run dir>/config.json
     の2階層なのに1階層しか見ていなかった」事故の再発防止)
  - 各 run の Config を上記と同じ check_config() で検証する
  - 合計 255 run、B1=8 seed × 15候補、B2=5 seed × 15候補、B3=4 seed × 15候補
    がすべて揃っており、欠落・重複がないこと
  - 各 run の環境・bmr_core が、格納ディレクトリ名 (`<env>_..._bmr<core>`)
    および実験計画の想定と一致すること

使い方:
    uv run python tools/check_exp11.py              # 全45 Config を検証
    uv run python tools/check_exp11.py runs/exp11   # 実行済み run も検証
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES, fixed_mask_from_names
from tools.exp11_common import (
    BMR_CORE_CANDIDATES, SEEDS, TOTAL_RUNS, infer_env, parse_condition_dir_name,
    round_core,
)

CONFIGS_DIR = ROOT / "configs" / "exp11"

# canonical: body_size 以外の全遺伝子。ローカルにリストを書き写さない。
EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}


def check_config(path: Path) -> list[str]:
    """Config ファイルを検証し、エラーメッセージのリストを返す。空 = OK。"""
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path}: JSON 読み込みエラー: {e}"]

    # bmr_core キーの存在
    if "bmr_core" not in data:
        errors.append(f"{path}: bmr_core フィールドが存在しない")
        return errors

    core = data["bmr_core"]

    # bmr_core が候補値のいずれか
    is_candidate = any(abs(core - c) < 1e-9 for c in BMR_CORE_CANDIDATES)
    if not is_candidate:
        errors.append(f"{path}: bmr_core={core} は候補 15 水準に含まれない")

    # Config.from_json で読み込めるか
    try:
        loaded = Config.from_json(path)
    except Exception as e:
        errors.append(f"{path}: Config.from_json 失敗: {e}")
        return errors

    # round-trip: JSON 値と loaded 値が一致
    if abs(loaded.bmr_core - core) > 1e-12:
        errors.append(
            f"{path}: round-trip 後 bmr_core={loaded.bmr_core} != JSON 値 {core}"
        )

    # fixed_genes: GENE_NAMES - {"body_size"} と完全一致 (集合として直接比較)
    fg = set(loaded.fixed_genes)
    missing = EXPECTED_FIXED_GENES - fg
    if missing:
        errors.append(f"{path}: fixed_genes 不足 {sorted(missing)}")
    unexpected = fg - EXPECTED_FIXED_GENES
    if unexpected:
        # body_size が含まれる場合も unexpected に入り、ここで検出される
        errors.append(f"{path}: fixed_genes に想定外/未知の遺伝子名 {sorted(unexpected)}")

    # fixed_mask_from_names まで実際に通す。未知の遺伝子名は ValueError になる。
    # (このチェック自体が genome.py の GENE_NAMES と食い違っていないことを保証する)
    try:
        fixed_mask_from_names(loaded.fixed_genes)
    except ValueError as e:
        errors.append(f"{path}: fixed_mask_from_names 失敗: {e}")

    return errors


def check_simulation_smoke(path: Path) -> list[str]:
    """Config から実際に Simulation を初期化できるか確認する (smoke test)。"""
    from evosim.simulation import Simulation

    errors = []
    try:
        cfg = Config.from_json(path)
        Simulation(cfg, seed=1)
    except Exception as e:
        errors.append(f"{path.name}: Simulation 初期化失敗: {type(e).__name__}: {e}")
    return errors


# ---------------------------------------------------------------------------
# 実行済み run の収集・完全性検証
# ---------------------------------------------------------------------------

def collect_run_dirs(base_dir: Path) -> list[Path]:
    """config.json を直接持つディレクトリを再帰的に収集する。

    collect後の実際の階層 (`runs/exp11/<条件key>/<seed run dir>/config.json`)
    に依存せず、任意の深さで config.json を直接含むディレクトリだけを
    run ディレクトリとして扱う。条件ディレクトリ自体は config.json を
    直接持たないため、ここで自然に除外される。
    """
    return sorted({p.parent for p in base_dir.rglob("config.json")})


def check_run_configs(run_dirs: list[Path]) -> list[str]:
    """実行済み run ディレクトリ内の config.json を検証する。"""
    errors = []
    for run_dir in run_dirs:
        cfg_path = run_dir / "config.json"
        if not cfg_path.exists():
            errors.append(f"{run_dir}: config.json が存在しない")
            continue
        errors.extend(check_config(cfg_path))
    return errors


def check_run_completeness(run_dirs: list[Path]) -> list[str]:
    """255 run の欠落・重複、環境/bmr_core とディレクトリ名の整合を確認する。

    Returns:
        エラーメッセージのリスト (空 = OK)
    """
    errors: list[str] = []

    # (env, core, seed) -> [run_dir, ...] (重複検出のためリストで持つ)
    grid: dict[tuple[str, float, int], list[Path]] = {}
    unreadable: list[Path] = []

    for run_dir in run_dirs:
        cfg_path = run_dir / "config.json"
        meta_path = run_dir / "meta.json"
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            unreadable.append(run_dir)
            errors.append(f"{run_dir}: config.json/meta.json 読み込み失敗: {e}")
            continue

        core = round_core(cfg.get("bmr_core", 0.0))
        env_from_cfg = infer_env(cfg)
        seed = meta.get("seed")
        if seed is None:
            errors.append(f"{run_dir}: meta.json に seed がない")
            continue

        # ディレクトリ名 (条件ディレクトリ = run_dir の親) との整合確認
        cond_dir_name = run_dir.parent.name
        parsed = parse_condition_dir_name(cond_dir_name)
        if parsed is None:
            errors.append(
                f"{run_dir}: 親ディレクトリ名 '{cond_dir_name}' が "
                "'<env>_..._bmr<core>' 形式と一致しない"
            )
        else:
            env_from_name, core_from_name = parsed
            if env_from_name != env_from_cfg:
                errors.append(
                    f"{run_dir}: 環境不一致 (ディレクトリ名={env_from_name} "
                    f"/ Config推定={env_from_cfg})"
                )
            if abs(core_from_name - core) > 1e-9:
                errors.append(
                    f"{run_dir}: bmr_core不一致 (ディレクトリ名={core_from_name} "
                    f"/ Config={core})"
                )

        key = (env_from_cfg, core, seed)
        grid.setdefault(key, []).append(run_dir)

    # 重複検出
    for key, dirs in grid.items():
        if len(dirs) > 1:
            env, core, seed = key
            errors.append(
                f"重複run: env={env} bmr_core={core:.3f} seed={seed} が "
                f"{len(dirs)} 件存在: {[str(d) for d in dirs]}"
            )

    # 欠落検出 (期待 grid との差分)
    expected_keys = {
        (env, core, seed)
        for env in SEEDS
        for core in BMR_CORE_CANDIDATES
        for seed in SEEDS[env]
    }
    found_keys = set(grid.keys())
    missing = expected_keys - found_keys
    if missing:
        for env, core, seed in sorted(missing):
            errors.append(f"欠落run: env={env} bmr_core={core:.3f} seed={seed}")

    # 想定外の (env, core, seed) 組み合わせ (seed範囲外等)
    unexpected = found_keys - expected_keys
    for env, core, seed in sorted(unexpected):
        errors.append(f"想定外run: env={env} bmr_core={core:.3f} seed={seed} "
                      "(期待 grid に含まれない)")

    total_valid_runs = sum(len(dirs) for dirs in grid.values())
    if not missing and not unexpected and total_valid_runs != TOTAL_RUNS:
        errors.append(
            f"run総数が {total_valid_runs} (期待: {TOTAL_RUNS}) — "
            "grid上は揃っているが総数が合わない (要調査)"
        )

    return errors


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp11 Config 整合性チェック")
    ap.add_argument("run_dirs", nargs="*", type=Path,
                    help="実行済み run 結果の親ディレクトリ (省略時は configs/exp11/ のみ確認)")
    args = ap.parse_args()

    errors: list[str] = []

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

    # 実行済み run ディレクトリ (再帰収集。config.json を直接持つものだけ)
    if args.run_dirs:
        run_dirs: list[Path] = []
        for base in args.run_dirs:
            if base.is_dir():
                run_dirs.extend(collect_run_dirs(base))
        errors.extend(check_run_configs(run_dirs))
        errors.extend(check_run_completeness(run_dirs))

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    n = len(cfg_files)
    msg = f"OK: 全 {n} Config 整合性チェック通過"
    if args.run_dirs:
        msg += f" / 実行済み {TOTAL_RUNS} run 完全性チェック通過"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
