"""Exp10 Phase B をローカルで実行する (docs/Exp10_実行手順.md §4)。

    uv run python tools/run_exp10_phaseB.py --out runs/exp10 --ticks 10000 \
        --seeds 1-20 --workers 4

`.github/workflows/exp10.yml` と同じ条件・同じ停止条件をローカルで回すための
driverである。workflow は default branch にある必要があり、exp10.yml が
まだ main へ入っていない間はこちらを使う。

やること (workflowのjobと同じ順):

  1. Config が生成物と一致するか確認         (停止条件)
  2. Phase 0 テスト                          (停止条件)
  3. 保存則・決定性テスト                    (停止条件)
  4. 10条件 × seed を実行
  5. 数値実行環境の同一性 / 健全性 / 診断条件チェック
  6. Phase B の要約と事前登録判定
  7. 生データを条件ごとにtar.gzへまとめ、マニフェストを作る

生データはGitへ入れない。`--archive-dir` の中身はGoogle Drive /
Actions artifact へ退避する (docs/実験結果保存方針.md §1)。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_exp10_configs import CONDITIONS, RULES  # noqa: E402

CASES = [f"{c}_{r}" for c in CONDITIONS for r in RULES]


def run(cmd: list[str], *, check: bool = True) -> int:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    rc = subprocess.call(cmd, cwd=ROOT)
    if check and rc != 0:
        raise SystemExit(f"★ 停止条件: {' '.join(cmd)} が rc={rc} で失敗した")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp10 Phase B のローカル実行")
    ap.add_argument("--out", default="runs/exp10")
    ap.add_argument("--ticks", type=int, default=10000)
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cases", default="", help="カンマ区切りで条件を絞る")
    ap.add_argument("--skip-checks", action="store_true",
                    help="実行前の停止条件チェックを飛ばす (再開時のみ)")
    ap.add_argument("--archive-dir", default="archives/exp10")
    args = ap.parse_args()

    cases = ([c.strip() for c in args.cases.split(",") if c.strip()]
             if args.cases else CASES)
    out = ROOT / args.out
    py = [sys.executable]

    if not args.skip_checks:
        print("=== 実行前の停止条件 (workflow setup job 相当) ===")
        run(py + ["tools/make_exp10_configs.py", "--check"])
        run(py + ["-m", "pytest", "tests/test_v16_temporal.py", "-q"])
        run(py + ["-m", "pytest", "tests/test_conservation.py",
                  "tests/test_determinism.py", "-q"])

    print(f"\n=== Phase B 実行: {len(cases)} 条件 × seed {args.seeds} "
          f"× {args.ticks:,} tick ===")
    t0 = time.time()
    for i, case in enumerate(cases, 1):
        cfg = ROOT / "configs" / "exp10" / f"exp10_{case}.json"
        if not cfg.exists():
            raise SystemExit(f"★ {cfg} が無い")
        el = time.time() - t0
        print(f"\n--- [{i}/{len(cases)}] {case}  (経過 {el / 60:.1f} 分) ---",
              flush=True)
        run(py + ["tools/run_batch.py", "--seeds", args.seeds,
                  "--ticks", str(args.ticks), "--workers", str(args.workers),
                  "--config", str(cfg), "--out", str(out / case)])

    print(f"\n=== 実行完了 ({(time.time() - t0) / 60:.1f} 分) ===")

    print("\n=== 数値実行環境 ===")
    run(py + ["tools/check_env.py"] + [str(p) for p in sorted(out.iterdir())
                                       if p.is_dir()], check=False)
    print("\n=== 健全性チェック ===")
    n_seeds = len(cases) and _seed_count(args.seeds)
    run(py + ["tools/health_check.py"] + [str(p) for p in sorted(out.iterdir())
                                          if p.is_dir()]
        + ["--ticks", str(args.ticks), "--expect-runs", str(n_seeds)],
        check=False)
    print("\n=== 診断条件チェック ===")
    cond_rc = run(py + ["tools/check_exp10.py", str(out), "--seeds", args.seeds],
                  check=False)
    print("\n=== Phase B の要約と事前登録判定 ===")
    sum_rc = run(py + ["tools/summarize_exp10_phaseB.py", str(out),
                       "--ticks", str(args.ticks)], check=False)

    print("\n=== 生データのアーカイブ ===")
    arch = ROOT / args.archive_dir
    arch.mkdir(parents=True, exist_ok=True)
    for c in sorted(out.iterdir()):
        if not c.is_dir():
            continue
        tar = arch / f"exp10_{c.name}.tar.gz"
        subprocess.call(["tar", "-czf", str(tar), "-C", str(c.parent), c.name])
    subprocess.call(["du", "-sh", str(arch)])
    print(f"\n生データは Git へ入れない。{args.archive_dir} を "
          "Google Drive / Actions artifact へ退避すること "
          "(docs/実験結果保存方針.md §1)")

    if cond_rc != 0 or sum_rc != 0:
        print("\n★ 診断条件または事前登録判定が停止条件に該当した")
        return 1
    return 0


def _seed_count(spec: str) -> int:
    n = 0
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            n += int(hi) - int(lo) + 1
        elif part:
            n += 1
    return n


if __name__ == "__main__":
    sys.exit(main())
