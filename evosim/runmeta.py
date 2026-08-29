"""実行環境の記録 (Issue #20)。

結果は数値実行環境に依存する (math.sin/cos/atan2/hypot と pow の最終ビットが
OS側の数学ライブラリ実装に依存する)。そのため seed と Config だけでは
再現条件を特定できない。比較実験群が同一環境で実行されたことを
後から確認できるよう、run ごとに環境を記録する。
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import numpy as np


def _git_sha() -> str | None:
    """コードのバージョン。git管理外なら None。"""
    try:
        root = Path(__file__).resolve().parent.parent
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return None
        sha = r.stdout.strip()
        d = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                           capture_output=True, text=True, timeout=10)
        dirty = bool(d.stdout.strip()) if d.returncode == 0 else False
        return f"{sha}-dirty" if dirty else sha
    except (OSError, subprocess.SubprocessError):
        return None


def numeric_environment() -> dict:
    """同一性を判定すべき数値実行環境。ここが違えば結果は一致し得ない。"""
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_compiler": platform.python_compiler(),
        "numpy_version": np.__version__,
        # 同一環境かの照合に使う短いキー
        "env_key": f"{platform.system().lower()}-{platform.machine().lower()}"
                   f"-py{platform.python_version()}-np{np.__version__}",
    }


def run_metadata(seed: int, version: str) -> dict:
    return {
        "seed": seed,
        "evosim_version": version,
        "git_sha": _git_sha(),
        "command": " ".join(sys.argv),
        "numeric_environment": numeric_environment(),
    }
