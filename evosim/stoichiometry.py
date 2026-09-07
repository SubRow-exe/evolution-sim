"""V1.10 biomass元素化学量論ヘルパー (docs/V1.10_CNP資源分解_実装仕様.md §2-3)。

Organism.matter は dry biomass (V1.9 matter unit) のまま維持する。V1.10は
これを固定biomass組成 (C 47% / N 11% / P 2% 質量分率、残り約40%はH/O/S/ash
等としてimplicit・non-limiting) からmol C/N/Pへ変換するだけで、新しい
geneは追加しない (variable stoichiometryはV1.10の対象外)。
"""
from __future__ import annotations

from .config import Config

# IUPAC標準原子量 [kg/mol]
CARBON_MOLAR_MASS_KG_PER_MOL = 0.012011
NITROGEN_MOLAR_MASS_KG_PER_MOL = 0.014007
PHOSPHORUS_MOLAR_MASS_KG_PER_MOL = 0.030974

# V1.10 growth_limiter分類 (docs/V1.10_CNP資源分解_実装仕様.md §9)。
# simulation.py と recorder.py の両方から参照するため循環import回避も兼ねて
# ここに置く。
GROWTH_LIMITERS = ("energy", "kinetic", "carbon", "nitrogen", "phosphorus", "room")


def carbon_mol_per_kgdw(cfg: Config) -> float:
    return cfg.biomass_carbon_mass_frac / CARBON_MOLAR_MASS_KG_PER_MOL


def nitrogen_mol_per_kgdw(cfg: Config) -> float:
    return cfg.biomass_nitrogen_mass_frac / NITROGEN_MOLAR_MASS_KG_PER_MOL


def phosphorus_mol_per_kgdw(cfg: Config) -> float:
    return cfg.biomass_phosphorus_mass_frac / PHOSPHORUS_MOLAR_MASS_KG_PER_MOL


def matter_to_element_mol(matter_units: float, cfg: Config) -> tuple[float, float, float]:
    """matter unit (dry biomass) -> (C mol, N mol, P mol) の固定組成換算。

    負のmatter_unitsを渡した場合もそのまま比例計算する (corpse decay等の
    差分計算で呼び出し側が符号を扱えるように)。
    """
    kgdw = matter_units * cfg.matter_unit_to_kgdw
    return (
        kgdw * carbon_mol_per_kgdw(cfg),
        kgdw * nitrogen_mol_per_kgdw(cfg),
        kgdw * phosphorus_mol_per_kgdw(cfg),
    )
