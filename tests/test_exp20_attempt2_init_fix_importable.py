"""Regression test for the Exp20 Attempt 2 `attempt2_init_fix` import-order bug.

`attempt2_init_fix.py` does `import exp18_core`, which only resolves if
`experiments/exp18_v1101_dynamic_vent` is already on `sys.path`. That path was
previously bootstrapped only in `run_attempt2.py`, so any script that imported
`attempt2_init_fix` *before* `run_attempt2` (e.g. `preflight_initial_state.py`,
`run_attempt2_72h.py`) crashed with `ModuleNotFoundError: No module named
'exp18_core'`.

This test imports `attempt2_init_fix` standalone, in a fresh subprocess with a
clean `sys.path`, to confirm the module bootstraps its own path regardless of
import order — the actual failure mode that reached CI.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = ROOT / "experiments" / "exp20_attempt2_paired_fitness"


def test_attempt2_init_fix_importable_standalone_without_prior_sys_path_setup():
    """Import `attempt2_init_fix` first, with nothing else having touched
    sys.path — this is exactly the failure mode from
    preflight_initial_state.py / run_attempt2_72h.py importing it before
    run_attempt2.py.
    """
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(MODULE_DIR)!r}); "
        "import attempt2_init_fix; "
        "assert hasattr(attempt2_init_fix, 'install'); "
        "print('ATTEMPT2_INIT_FIX_IMPORT_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}")
    assert "ATTEMPT2_INIT_FIX_IMPORT_OK" in result.stdout
