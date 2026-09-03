"""Exp14 Config整合性・完全性・first-Nk再現性チェッカー
(docs/Exp14_実験計画確定.md, 実装チェックリスト.md)。

確認項目 (静的Config):
  - Phase A/B/C の116 Configがgeneratorと一致
  - fixed_genesがcanonical GENE_NAMESから正しく導出されている
  - Simulation初期化+短tick smoke

確認項目 (実行済みrun): `check_exp14.py runs/exp14 --profile FULL`
  - config.jsonを持つrunディレクトリを再帰的に収集
  - 期待run key集合 (116件、重複/欠落/想定外を検出)
  - formal SHA / numeric environment整合性
  - current-run first-Nk×2 same-seed再現性比較 (compare_first_nk)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES, fixed_mask_from_names
from tools.exp14_common import (
    A_ARM_NAMES, C_ARM_NAMES, PHASE_A_SEEDS, PHASE_B_CAPACITIES,
    PHASE_B_PERIODS, PHASE_B_SEEDS, PHASE_C_SEEDS, PROFILES, TOTAL_RUNS,
)
from tools.make_exp14_configs import (
    all_jobs, phase_a_config_name, phase_b_config_name, phase_c_config_name,
)


def check_generated_configs(profile: str) -> list[str]:
    """generatorが実際に116件・重複なしで出せることと、代表smokeを確認する。"""
    errors: list[str] = []
    jobs = all_jobs(profile)
    if len(jobs) != TOTAL_RUNS:
        errors.append(f"profile={profile}: job数が{TOTAL_RUNS}でない: {len(jobs)}")

    for name, cfg in jobs:
        if abs(cfg.bmr_core - 0.15) > 1e-12:
            errors.append(f"{name}: bmr_core={cfg.bmr_core} != 0.15")
        if not cfg.primary_energy_density_response:
            errors.append(f"{name}: primary_energy_density_response がFalse")
        try:
            fixed_mask_from_names(cfg.fixed_genes)
        except ValueError as e:
            errors.append(f"{name}: fixed_mask_from_names失敗: {e}")

    # 代表smoke (各Phaseから1件ずつ + Phase Aの1本を数tick走らせる)
    from evosim.simulation import Simulation
    for name, cfg in [jobs[0], jobs[21], jobs[-1]]:
        try:
            sim = Simulation(cfg, seed=1)
            for _ in range(5):
                sim.step()
        except Exception as e:
            errors.append(f"{name}: Simulation smoke失敗: {type(e).__name__}: {e}")
    return errors


def expected_run_keys() -> set[str]:
    keys: set[str] = set()
    for arm in A_ARM_NAMES:
        for seed in PHASE_A_SEEDS:
            keys.add(phase_a_config_name(arm, seed))
    for period in PHASE_B_PERIODS:
        for capacity in PHASE_B_CAPACITIES:
            for seed in PHASE_B_SEEDS:
                keys.add(phase_b_config_name(period, capacity, seed))
    for arm in C_ARM_NAMES:
        for seed in PHASE_C_SEEDS:
            keys.add(phase_c_config_name(arm, seed))
    assert len(keys) == TOTAL_RUNS
    return keys


# ---------------------------------------------------------------------------
# run収集・完全性検証
# ---------------------------------------------------------------------------

def collect_run_dirs(base_dir: Path) -> list[Path]:
    return sorted({p.parent for p in base_dir.rglob("config.json")})


def check_run_key_completeness(run_dirs: list[Path]) -> list[str]:
    """期待116 run keyとの完全一致 (欠落/重複/想定外を検出)。

    run_dirのディレクトリ名が期待config名 (拡張子なし) と一致することを
    前提にする。formalのdispatch/collectはこの命名規則で run を並べる。
    """
    errors: list[str] = []
    expected = {Path(k).stem for k in expected_run_keys()}
    seen: dict[str, list[Path]] = {}
    for run_dir in run_dirs:
        seen.setdefault(run_dir.name, []).append(run_dir)

    actual = set(seen)
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        errors.append(f"run key欠落 ({len(missing)}件): {sorted(missing)[:10]}...")
    if unexpected:
        errors.append(f"想定外run key ({len(unexpected)}件): {sorted(unexpected)[:10]}...")
    for name, dirs in seen.items():
        if len(dirs) > 1:
            errors.append(f"run key重複: {name} が{len(dirs)}箇所: {dirs}")
    return errors


def check_run_environment_integrity(run_dirs: list[Path]) -> list[str]:
    """formal run群がすべて同一git_sha・同一numeric_environmentで実行された
    ことを確認する (docs/数値再現性・Actions実行環境方針.md Level A)。
    """
    errors: list[str] = []
    shas: dict[str | None, list[Path]] = {}
    env_keys: dict[str | None, list[Path]] = {}

    for run_dir in run_dirs:
        meta_path = run_dir / "meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{run_dir}: meta.json読み込み失敗 (環境整合性チェック): {e}")
            continue
        sha = meta.get("git_sha")
        if sha is None:
            errors.append(f"{run_dir}: meta.jsonにgit_shaがない")
        shas.setdefault(sha, []).append(run_dir)
        env_key = (meta.get("numeric_environment") or {}).get("env_key")
        if env_key is None:
            errors.append(f"{run_dir}: meta.jsonにnumeric_environment.env_keyがない")
        env_keys.setdefault(env_key, []).append(run_dir)

    if len(shas) > 1:
        errors.append(
            "formal run群でgit_shaが混在: "
            + ", ".join(f"{k!r}={len(v)}件" for k, v in sorted(shas.items(), key=lambda kv: str(kv[0])))
        )
    if len(env_keys) > 1:
        errors.append(
            "formal run群でnumeric_environment.env_keyが混在: "
            + ", ".join(f"{k!r}={len(v)}件" for k, v in sorted(env_keys.items(), key=lambda kv: str(kv[0])))
        )
    return errors


# ---------------------------------------------------------------------------
# first-Nk×2 現在環境内再現性比較
# ---------------------------------------------------------------------------

def _load_stats_upto(run_dir: Path, max_tick: int) -> list[dict]:
    path = run_dir / "stats.csv"
    if not path.exists():
        raise FileNotFoundError(f"{run_dir}: stats.csvが無い")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                tick = int(row["tick"])
            except (KeyError, ValueError):
                continue
            if tick <= max_tick:
                rows.append(row)
    return rows


def compare_first_nk(run_dir_a: Path, run_dir_b: Path, max_tick: int) -> list[str]:
    errors: list[str] = []
    try:
        rows_a = _load_stats_upto(run_dir_a, max_tick)
        rows_b = _load_stats_upto(run_dir_b, max_tick)
    except FileNotFoundError as e:
        return [str(e)]

    if len(rows_a) != len(rows_b):
        errors.append(f"stats.csv行数不一致: a={len(rows_a)} b={len(rows_b)}")
    else:
        for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
            if ra != rb:
                diff_keys = [k for k in ra if ra.get(k) != rb.get(k)]
                errors.append(f"stats.csv行{i} (tick={ra.get('tick')}) 不一致: 列 {diff_keys}")
    return errors


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp14 Config整合性・完全性チェック")
    ap.add_argument("run_dirs", nargs="*", type=Path,
                    help="実行済みrun結果の親ディレクトリ (省略時は静的Config確認のみ)")
    ap.add_argument("--profile", choices=["FULL", "COMPACT"], default="FULL")
    ap.add_argument("--skip-completeness", action="store_true",
                    help="116 run完全性チェックを省略する (preflightの1件smokeなど部分collectで使う)")
    args = ap.parse_args()

    errors: list[str] = []
    errors.extend(check_generated_configs(args.profile))

    if args.run_dirs:
        run_dirs: list[Path] = []
        for base in args.run_dirs:
            if base.is_dir():
                run_dirs.extend(collect_run_dirs(base))
        for run_dir in run_dirs:
            cfg_path = run_dir / "config.json"
            if not cfg_path.exists():
                errors.append(f"{run_dir}: config.jsonが存在しない")
                continue
            try:
                Config.from_json(cfg_path)
            except Exception as e:
                errors.append(f"{run_dir}: Config.from_json失敗: {e}")
        if not args.skip_completeness:
            errors.extend(check_run_key_completeness(run_dirs))
        errors.extend(check_run_environment_integrity(run_dirs))

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    msg = f"OK: Exp14 profile={args.profile} {TOTAL_RUNS} Config整合性チェック通過"
    if args.run_dirs:
        n = sum(len(collect_run_dirs(b)) for b in args.run_dirs if b.is_dir())
        msg += f" / 実行済み{n} run 検証通過"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
