"""Exp13 Config生成 (docs/Exp13_実験計画確定.md, V1.8_実装チェックリスト.md §12)。

Phase A1/A2 は selected値に依存しないため静的に生成できる。
Phase A2b/A3/B1-B4 は Phase A の selected値 (light_max, chemical_uptake_half,
chem_uptake) が確定してから生成する。generatorはbuild_*関数として提供し、
CLIからもActions workflowのpythonステップからも同じ関数を呼ぶ
(人手Config複製禁止)。

    uv run python tools/make_exp13_configs.py            # A1+A2 を configs/exp13/ へ
    uv run python tools/make_exp13_configs.py --check     # 既存ファイルとの一致確認
    uv run python tools/make_exp13_configs.py --phase-b <selected.json>
        # selected値からA2b/A3/B1-B4を生成 (configs/exp13_phaseb/)
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES, fixed_mask_from_names
from tools.exp13_common import (
    A1_JOBS, A1_LIGHT_MAX, A1_SEEDS, A1_TICKS,
    A2_CHEM_UPTAKE, A2_CHEMICAL_UPTAKE_HALF, A2_JOBS, A2_SEEDS, A2_TICKS,
    A2B_JOBS, A2B_PLACEMENTS, A2B_SEEDS, A2B_TICKS,
    A3_JOBS, A3_POPULATIONS, A3_SEEDS, A3_TICKS,
    B1_JOBS, B1_SEEDS, B1_TICKS, B2_JOBS, B2_SEEDS, B2_TICKS,
    B3_JOBS, B3_SEEDS, B3_TICKS,
    B4A_BODY_SIZE, B4A_JOBS, B4A_SEEDS, B4A_TICKS,
    B4B_JOBS, B4B_SEEDS, B4B_TICKS,
    COMMON_CONFIG, PHASE_A_TOTAL, PHASE_B_TOTAL, TOTAL_RUNS,
    b4a_derived_initial_energy,
)

OUT_DIR_A = ROOT / "configs" / "exp13"
OUT_DIR_B = ROOT / "configs" / "exp13_phaseb"

ALL_GENES: list[str] = list(GENE_NAMES)
assert len(ALL_GENES) == 14

# --- phenotypes (Exp11/12と同一テンプレート) ---
LIGHT_SPECIALIST = {"light_absorption": 2.0, "chemical_absorption": 0.3}
CHEM_SPECIALIST = {"light_absorption": 0.3, "chemical_absorption": 2.0}
GENERALIST = {"light_absorption": 0.3, "chemical_absorption": 0.3}


def _base(**overrides) -> dict:
    d = dict(COMMON_CONFIG)
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# Phase A1: light map — 進化OFF、全14遺伝子固定、light-only
# ---------------------------------------------------------------------------

def build_a1(light_max: float, seed: int | None = None) -> Config:
    return Config(
        **_base(
            light_max=light_max,
            light_pattern="vertical",
            chem_vent_flux=0.0,
            diagnostic_placement="random",
            light_cycle_enabled=True,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=dict(LIGHT_SPECIALIST),
        ),
    )


def a1_config_name(light_max: float) -> str:
    return f"exp13_A1_light{light_max:.2f}.json"


# ---------------------------------------------------------------------------
# Phase A2: chemical grid — 進化OFF、全14遺伝子固定、chemical-only
# ---------------------------------------------------------------------------

def build_a2(chemical_uptake_half: float, chem_uptake: float) -> Config:
    return Config(
        **_base(
            light_max=0.0,
            chem_vent_flux=16.0,
            diagnostic_placement="vent",
            light_cycle_enabled=False,  # 光が存在しない条件
            chemical_uptake_half=chemical_uptake_half,
            chem_uptake=chem_uptake,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=dict(CHEM_SPECIALIST),
        ),
    )


def a2_config_name(k: float, uptake: float) -> str:
    return f"exp13_A2_K{k:.3f}_uptake{uptake:.3f}.json"


# ---------------------------------------------------------------------------
# Phase A2b: selected chemical pairの検証 (vent/random placement)
# ---------------------------------------------------------------------------

def build_a2b(chemical_uptake_half: float, chem_uptake: float, placement: str) -> Config:
    assert placement in A2B_PLACEMENTS
    return Config(
        **_base(
            light_max=0.0,
            chem_vent_flux=16.0,
            diagnostic_placement=placement,
            light_cycle_enabled=False,
            chemical_uptake_half=chemical_uptake_half,
            chem_uptake=chem_uptake,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=dict(CHEM_SPECIALIST),
        ),
    )


def a2b_config_name(placement: str) -> str:
    return f"exp13_A2b_{placement}.json"


# ---------------------------------------------------------------------------
# Phase A3: density competition — selected chemical pair, vent placement
# ---------------------------------------------------------------------------

def build_a3(chemical_uptake_half: float, chem_uptake: float,
            initial_population: int) -> Config:
    return Config(
        **_base(
            light_max=0.0,
            chem_vent_flux=16.0,
            diagnostic_placement="vent",
            light_cycle_enabled=False,
            chemical_uptake_half=chemical_uptake_half,
            chem_uptake=chem_uptake,
            initial_population=initial_population,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=dict(CHEM_SPECIALIST),
        ),
    )


def a3_config_name(pop: int) -> str:
    return f"exp13_A3_pop{pop}.json"


# ---------------------------------------------------------------------------
# Phase B1: light-only long-term — selected light_max, light specialist
# ---------------------------------------------------------------------------

def build_b1(light_max: float) -> Config:
    return Config(
        **_base(
            light_max=light_max,
            light_pattern="vertical",
            chem_vent_flux=0.0,
            diagnostic_placement="random",
            light_cycle_enabled=True,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=dict(LIGHT_SPECIALIST),
        ),
    )


# ---------------------------------------------------------------------------
# Phase B2: chemical-only long-term — selected chemical pair, chem specialist
# ---------------------------------------------------------------------------

def build_b2(chemical_uptake_half: float, chem_uptake: float) -> Config:
    return Config(
        **_base(
            light_max=0.0,
            chem_vent_flux=16.0,
            diagnostic_placement="random",
            light_cycle_enabled=False,
            chemical_uptake_half=chemical_uptake_half,
            chem_uptake=chem_uptake,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=dict(CHEM_SPECIALIST),
        ),
    )


# ---------------------------------------------------------------------------
# Phase B3: mixed-world exploratory evolution — 2遺伝子のみ進化ON
# ---------------------------------------------------------------------------

B3_FIXED_GENES = [g for g in ALL_GENES
                  if g not in ("light_absorption", "chemical_absorption")]
assert len(B3_FIXED_GENES) == 12


def build_b3(light_max: float, chemical_uptake_half: float, chem_uptake: float) -> Config:
    return Config(
        **_base(
            light_max=light_max,
            light_pattern="vertical",
            chem_vent_flux=16.0,
            diagnostic_placement="random",
            light_cycle_enabled=True,
            chemical_uptake_half=chemical_uptake_half,
            chem_uptake=chem_uptake,
            fixed_genes=list(B3_FIXED_GENES),
            diagnostic_gene_overrides=dict(GENERALIST),
        ),
    )


# ---------------------------------------------------------------------------
# Phase B4a: Exp12平衡付近の固定小型個体 (light-only, night viability診断)
# ---------------------------------------------------------------------------

def build_b4a(light_max: float) -> Config:
    std = Config()  # 標準初期状態 (initial_energy=50, initial_matter=0.8, energy_capacity=100)
    initial_matter = std.initial_matter * B4A_BODY_SIZE  # 0.8 * 0.246 = 0.1968
    initial_energy = b4a_derived_initial_energy(
        std.initial_energy, std.initial_matter, std.energy_capacity, B4A_BODY_SIZE)
    overrides = dict(LIGHT_SPECIALIST)
    overrides["body_size"] = B4A_BODY_SIZE
    return Config(
        **_base(
            light_max=light_max,
            light_pattern="vertical",
            chem_vent_flux=0.0,
            diagnostic_placement="random",
            light_cycle_enabled=True,
            initial_matter=initial_matter,
            initial_energy=initial_energy,
            fixed_genes=list(ALL_GENES),
            diagnostic_gene_overrides=overrides,
        ),
    )


# ---------------------------------------------------------------------------
# Phase B4b: body_size-only evolution (light-only)
# ---------------------------------------------------------------------------

B4B_FIXED_GENES = [g for g in ALL_GENES if g != "body_size"]
assert len(B4B_FIXED_GENES) == 13


def build_b4b(light_max: float) -> Config:
    return Config(
        **_base(
            light_max=light_max,
            light_pattern="vertical",
            chem_vent_flux=0.0,
            diagnostic_placement="random",
            light_cycle_enabled=True,
            fixed_genes=list(B4B_FIXED_GENES),
            diagnostic_gene_overrides=dict(LIGHT_SPECIALIST),
        ),
    )


# ---------------------------------------------------------------------------
# 書き出しヘルパー
# ---------------------------------------------------------------------------

def _write_or_check(path: Path, cfg: Config, check: bool, errors: list[str]) -> None:
    payload = json.dumps(dataclasses.asdict(cfg), indent=2)
    # round-trip検証
    data = json.loads(payload)
    loaded = Config(**{k: v for k, v in data.items()
                       if k in {f.name for f in dataclasses.fields(Config)}})
    if dataclasses.asdict(loaded) != dataclasses.asdict(cfg):
        errors.append(f"{path.name}: round-trip不一致")
    try:
        fixed_mask_from_names(cfg.fixed_genes)
    except ValueError as e:
        errors.append(f"{path.name}: fixed_mask_from_names失敗: {e}")

    if check:
        if not path.exists():
            errors.append(f"{path.name}: ファイルが存在しない")
        elif path.read_text(encoding="utf-8").strip() != payload.strip():
            errors.append(f"{path.name}: 内容が一致しない")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def generate_phase_a(check: bool = False) -> list[str]:
    errors: list[str] = []
    for light_max in A1_LIGHT_MAX:
        cfg = build_a1(light_max)
        _write_or_check(OUT_DIR_A / a1_config_name(light_max), cfg, check, errors)
    for k in A2_CHEMICAL_UPTAKE_HALF:
        for uptake in A2_CHEM_UPTAKE:
            cfg = build_a2(k, uptake)
            _write_or_check(OUT_DIR_A / a2_config_name(k, uptake), cfg, check, errors)
    n_expected = len(A1_LIGHT_MAX) + len(A2_CHEMICAL_UPTAKE_HALF) * len(A2_CHEM_UPTAKE)
    assert n_expected == 8 + 16 == 24, n_expected
    return errors


def generate_phase_b(selected: dict, check: bool = False) -> list[str]:
    """selected = {"light_max":..., "chemical_uptake_half":..., "chem_uptake":...}"""
    errors: list[str] = []
    lm = selected["light_max"]
    k = selected["chemical_uptake_half"]
    up = selected["chem_uptake"]

    for placement in A2B_PLACEMENTS:
        cfg = build_a2b(k, up, placement)
        _write_or_check(OUT_DIR_B / a2b_config_name(placement), cfg, check, errors)
    for pop in A3_POPULATIONS:
        cfg = build_a3(k, up, pop)
        _write_or_check(OUT_DIR_B / a3_config_name(pop), cfg, check, errors)

    _write_or_check(OUT_DIR_B / "exp13_B1.json", build_b1(lm), check, errors)
    _write_or_check(OUT_DIR_B / "exp13_B2.json", build_b2(k, up), check, errors)
    _write_or_check(OUT_DIR_B / "exp13_B3.json", build_b3(lm, k, up), check, errors)
    _write_or_check(OUT_DIR_B / "exp13_B4a.json", build_b4a(lm), check, errors)
    _write_or_check(OUT_DIR_B / "exp13_B4b.json", build_b4b(lm), check, errors)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp13 Config生成")
    ap.add_argument("--check", action="store_true", help="書き出さず既存ファイルとの一致だけ確認")
    ap.add_argument("--phase-b", type=Path, default=None,
                    help="selected value JSONを指定してPhase B系Configを生成")
    args = ap.parse_args()

    errors: list[str] = []
    if args.phase_b is not None:
        selected = json.loads(args.phase_b.read_text(encoding="utf-8"))
        errors.extend(generate_phase_b(selected, args.check))
        n_bcfg = 2 + 3 + 5  # A2b + A3 + B1..B4b (Config単位。seedはmatrix展開)
    else:
        errors.extend(generate_phase_a(args.check))
        n_bcfg = 0

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.phase_b is not None:
        print(f"Exp13 Phase B系 Config {n_bcfg} 件 "
              f"{'確認' if args.check else '生成'}完了 → {OUT_DIR_B}")
    else:
        print(f"Exp13 Phase A (A1+A2) Config 24件 "
              f"{'確認' if args.check else '生成'}完了 → {OUT_DIR_A} "
              f"(実行時seed展開でPhase A total {PHASE_A_TOTAL} run, "
              f"Phase B total {PHASE_B_TOTAL} run, formal total {TOTAL_RUNS} run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
