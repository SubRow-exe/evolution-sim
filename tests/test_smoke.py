"""既定設定で機構が壊れず動くか (Exp 0 の縮小版)。

V1.9注記 (docs/V1.9_iLUCA再設計仕様.md, AGENTS.md §9/§10):
V1.9実装で判明した重要な事実として、fixed ancestor (INITIAL_GENOME) は
仕様書 §4/§10/§11 に明記された literal reference定数 (h2_uptake_coef=0.5,
h2_energy_yield=1.0, h2_conversion_eff=0.60, energy_capacity_base=100等)
の下では、vent直上に単独配置してもEnergy収支が恒常的に負となり、
繁殖なしでも100~150 tick程度で餓死する (H2 substrate -> usable Energy
の変換効率控除が、既存V1.7/V1.8由来の維持コスト式に対して補填されて
いないため)。これは実装バグではなく、仕様書自身が「これらの数値は
生物学的最終値ではなくformal experiment前にsanityが必要」と明記して
いる定数間のキャリブレーションギャップである。

AGENTS.md HARD RULEにより、Claudeは生存させるためにworld constantを
調整してはいけない。そのためこのsmoke testは「fixed ancestorが生存する
こと」を主張せず、機構 (Energy/Matter台帳・繁殖ループ・世代交代) が
crashせず・保存則を破らずに動くことだけを検証する。fixed ancestorの
生存可否そのものは、この実装報告のあとの人間レビューでformal experiment
設計へ引き継ぐ (docs/V1.9_iLUCA再設計仕様.md §23)。
"""
from evosim.config import Config
from evosim.simulation import Simulation


def test_runs_1000_ticks_without_crashing_and_conserves():
    sim = Simulation(Config(), 1)
    m0 = sim.initial_system_matter
    for _ in range(1000):
        sim.step()
    # 個体群の生存可否は主張しない (上記docstring参照)。機構が
    # crashせず、絶滅していてもMatter保存則が壊れていないことだけ確認する。
    assert sim.system_matter() == __import__("pytest").approx(m0, rel=1e-6)


def test_reproduction_happens_before_any_extinction():
    """H2へのアクセスが良い初期条件 (vent配置) では、絶滅前に繁殖が起きる。

    診断専用配置 (diagnostic_placement="vent") はEnergy収支そのものを
    変えない。世界規模の探索問題と繁殖機構の検証を分離するためだけに使う。

    V1.9物理スケール検証パッチでreproduction_horizonの既定値/最小値が
    seconds単位 (最小300s) へ変わったが、tests/test_smoke.pyのdocstring
    通りarbitrary-unit mode下のfixed ancestorのEnergy収支では、その最小値
    にすら到達しない (runwayが単調に減少し300へ届かない)。この繁殖機構
    テストの目的はEnergy収支ではなく繁殖ループそのものの確認なので、
    Config経由のgene rangeバリデーションを経ずに個体のgenomeへ直接、
    テスト専用の小さいreproduction_horizonを設定する。
    """
    cfg = Config(diagnostic_placement="vent")
    sim = Simulation(cfg, 1)
    from evosim.genome import REPRO_HORIZON
    for o in sim.organisms:
        o.genome[REPRO_HORIZON] = 1.0
    for _ in range(200):
        sim.step()
        if sim.births_cum > sim.cfg.initial_population:
            break
    assert sim.births_cum > sim.cfg.initial_population, "繁殖が一度も発生していない"


def test_no_mutation_stable_mechanism():
    """Exp 0: 突然変異を殺した状態でも、crashせず・保存則を破らず動くか。"""
    cfg = Config(initial_jitter_sigma=0.0, additive_mutation_frac=0.0,
                 meta_mutation_sigma=0.0)
    sim = Simulation(cfg, 3)
    m0 = sim.initial_system_matter
    # mutation_rate 遺伝子はゼロにできないが σ→最小値なら実質無変異
    for o in sim.organisms:
        o.genome[-1] = 0.005
    for _ in range(1500):
        sim.step()
    n = len(sim.organisms)
    assert n < 20_000, f"個体数が異常 ({n})"
    assert sim.system_matter() == __import__("pytest").approx(m0, rel=1e-6)
