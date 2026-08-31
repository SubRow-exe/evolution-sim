"""実装変更が結果を変えていないことを、任意のgit refと直接比較して検証する。

Golden指紋は数値実行環境に依存するため、保存定数を別環境へ持ち込んで比較できない。
本ツールは **同じマシン上で旧refと現在実装を実際に走らせて比較する** ことで、
そのマシンの数値環境差を両実装へ共通化し、実装変更そのものの影響を検出する。

これは「WindowsとLinuxで同じ結果を保証する」ツールではない。
WindowsではWindows上の旧版/新版、LinuxではLinux上の旧版/新版を比較する。

    uv run python tools/verify_vs_ref.py --ref 18137b5
    uv run python tools/verify_vs_ref.py --ref v1.1-baseline

比較対象のrefにも evosim パッケージが必要。指紋の計算式は現在の
tools/golden.py を両者に適用するため、計算方法の差は入り込まない。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fingerprints_at(ref: str, single_source: bool = False) -> dict[str, str]:
    """指定refのコードで指紋を計算する (git worktreeを一時作成)。"""
    tmp = Path(tempfile.mkdtemp(prefix="evosim_ref_"))
    wt = tmp / "wt"
    try:
        subprocess.run(["git", "worktree", "add", "--detach", str(wt), ref],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        # 指紋の計算式は現在版で統一する (計算方法の差を排除)
        (wt / "tools").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "tools" / "golden.py", wt / "tools" / "golden.py")
        cmd = [sys.executable, str(wt / "tools" / "golden.py"), "--print"]
        if single_source:
            cmd.append("--single-source")
        proc = subprocess.run(cmd, cwd=wt, check=True, capture_output=True, text=True)
        return json.loads(proc.stdout)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                       cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="同一マシン上で実装同士を直接比較して結果不変性を検証")
    ap.add_argument("--ref", required=True, help="比較対象のgit ref (タグ・コミット)")
    ap.add_argument("--single-source", action="store_true",
                    help="単独source (light-only / chemical-only) のケースで比較する。"
                         "V1.5は異種比較だけを変えるため、ここは旧版と完全一致が要件")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT))
    from tools.golden import SINGLE_SOURCE_CASES, compute_all

    print(f"比較対象: {args.ref}" + ("  (単独sourceケース)" if args.single_source else ""))
    ref_fp = fingerprints_at(args.ref, args.single_source)
    print("現在の実装を実行中...")
    cur_fp = compute_all(SINGLE_SOURCE_CASES if args.single_source else None)

    ng = [k for k in cur_fp if ref_fp.get(k) != cur_fp[k]]
    for name in cur_fp:
        print(f"  [{'NG' if name in ng else 'OK'}] {name:24s} {cur_fp[name]}")
    if ng:
        raise SystemExit(
            f"\n結果が {args.ref} と異なります: {', '.join(ng)}\n"
            "実装変更が挙動を変えました。意図した変更でなければ修正してください。")
    print(f"\n全ケース一致。この数値実行環境では {args.ref} と結果は同一です。")


if __name__ == "__main__":
    main()
