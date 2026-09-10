# Exp20 Attempt 2 — paired fitness-effect assay

This directory implements the active Stage-1 assay in `docs/V1.11_選択圧直接測定_実験ロードマップ.md`.

It measures fixed physiological trait effects directly rather than waiting for evolutionary change.
Formal factors are baseline × 0.5 / 0.8 / 1.2 / 1.5 for `storage_capacity`, `starvation_horizon`, and `reproduction_horizon`, under A0_STATIC and A2_DYNAMIC_VENT, seeds 20001–20003, 48 physical hours.

The assay explicitly disables phototrophy/light Energy so the Exp20 Attempt-1 legacy-light defect cannot contaminate this Stage-1 result. The phototrophy production-path repair remains required before later photon-flux calibration.
