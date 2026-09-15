"""Exp21 の A0_STATIC 対照が検出力を持つかを、出生数・死亡数から確認する。

`docs/Exp21_結果考察.md` §3 は A0 の long-horizon 割合を median 50.0% と報告した。
これが「差が出なかった」のか「頻度が原理的に動けなかった」のかは、
lineage別の出生・死亡数を見れば区別できる。

Exp21 harness (`run_exp21.run_one`) をそのまま呼び、最終行の
{lineage}_births_cum / {lineage}_deaths_cum を取り出す。

所要時間の目安: A0 / A2 各 1 seed で合計約 28 分 (A0 は個体数が伸びるため重い)。

シミュレーション実験ではなく既存 harness の再実行による診断。正式実験ではない。
考察の正本: docs/Exp21_Exp22_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../exp21_control_power.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for _p in (ROOT,
           ROOT / "experiments" / "exp21_starvation_horizon_competition",
           ROOT / "experiments" / "exp18_v1101_dynamic_vent"):
    sys.path.insert(0, str(_p))

import exp18_core            # noqa: E402
import run_exp21 as exp21    # noqa: E402

SEED = 21001
HOURS = 120.0
INITIAL_PER_LINEAGE = 50


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    h2_field = exp18_core.common_initial_h2_field(f0r)

    for environment in ("A0_STATIC", "A2_DYNAMIC_VENT"):
        cfg = exp21.make_cfg(f0r["f0_mol_s"], environment)
        started = time.time()
        rows, _summary = exp21.run_one(cfg, SEED, h2_field, HOURS)
        final = rows[-1]

        lb = final["long_births_cum"]
        bb = final["baseline_births_cum"]
        ld = final["long_deaths_cum"]
        bd = final["baseline_deaths_cum"]
        long_n = INITIAL_PER_LINEAGE + lb - ld
        base_n = INITIAL_PER_LINEAGE + bb - bd
        total = long_n + base_n

        print(f"=== {environment} seed={SEED}  ({time.time() - started:.0f}s) ===")
        print(f"  births  long={lb:4d}  baseline={bb:4d}   差 {lb - bb:+d}")
        print(f"  deaths  long={ld:4d}  baseline={bd:4d}   差 {ld - bd:+d}")
        print(f"  最終    long={long_n:4d}  baseline={base_n:4d}   "
              f"long割合 {100.0 * long_n / total:.1f}%")
        if ld == 0 and bd == 0 and lb == bb:
            print("  -> 死亡0かつ出生数が完全一致。頻度は算術的に動けない。")
            print("     この対照は「差が出なかった」ことを示せず、検出力を持たない。")
        print()


if __name__ == "__main__":
    main()
