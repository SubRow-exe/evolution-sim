"""実行環境の記録 (Issue #20)。

結果は数値実行環境に依存する (math.sin/cos/atan2/hypot と pow の最終ビットが
OS側の数学ライブラリ実装に依存する)。そのため seed と Config だけでは
再現条件を特定できない。比較実験群が同一環境で実行されたことを
後から確認できるよう、run ごとに環境を記録する。
"""
from __future__ import annotations

import os
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
    """同一性を判定すべき数値実行環境。ここが違えば結果は一致し得ない。

    libm (C標準数学ライブラリ) の実装差が結果を変えるため、Linuxでは
    glibc版も記録する。CI上ではランナーイメージ版も残し、実験の途中で
    イメージが切り替わっていないか後から照合できるようにする。
    """
    libc_name, libc_ver = platform.libc_ver()
    env = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "libc": f"{libc_name}{libc_ver}" if libc_name else None,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_compiler": platform.python_compiler(),
        "numpy_version": np.__version__,
        # CI実行時のみ。ランナーイメージが途中で変わっていないかの照合用
        "ci_image_version": os.environ.get("ImageVersion"),
        "ci_runner_os": os.environ.get("RUNNER_OS"),
    }
    # 照合キー。libm実装が変わる単位を含める
    libc_key = f"-{libc_name}{libc_ver}" if libc_name else ""
    env["env_key"] = (f"{platform.system().lower()}-{platform.machine().lower()}"
                      f"{libc_key}-py{platform.python_version()}-np{np.__version__}")
    return env


def run_metadata(seed: int, version: str) -> dict:
    return {
        "seed": seed,
        "evosim_version": version,
        "git_sha": _git_sha(),
        "command": " ".join(sys.argv),
        "numeric_environment": numeric_environment(),
    }
