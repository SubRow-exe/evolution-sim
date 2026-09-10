"""Formal 72 h entrypoint for Exp20 Attempt 2 paired fitness assay.

A2_DYNAMIC_VENT relocates a vent every 48 physical hours. A 48 h assay would
observe the first relocation only at the endpoint, so it cannot measure the
post-turnover fitness response. The formal Stage-1 window is therefore 72 h:
48 h before the first relocation + 24 h after it.
"""
from __future__ import annotations

import run_attempt2 as core

core.DURATION_H = 72.0

if __name__ == "__main__":
    core.main()
