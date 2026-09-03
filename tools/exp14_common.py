"""Exp14 共有定数・ヘルパー (docs/Exp14_実験計画確定.md)。

Exp12/Exp13の`tools/expNN_common.py`と同じ役割: generator/checker/summarizer
が同じ手書き定数を独自に持たないよう、ここへ一元化する。

正本:
  docs/Exp14_レビュー判断.md
  docs/Exp14_実験計画確定.md
  docs/Exp14_実装チェックリスト.md
  AGENTS.md
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evosim.genome import GENE_NAMES

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Phase A/B/C 共通のworld基礎条件 (Exp13 formal defaultを踏襲)
# ---------------------------------------------------------------------------
BMR_CORE = 0.15
MEMORY_TAU = 10.0
RESPONSE_GAIN = 64.0
LIGHT_UPTAKE_HALF = 0.6

STATS_INTERVAL = 20
SNAPSHOT_INTERVAL = 1000
MAX_POPULATION_HALT = 10000

COMMON_CONFIG = dict(
    bmr_core=BMR_CORE,
    memory_tau=MEMORY_TAU,
    response_gain=RESPONSE_GAIN,
    light_uptake_half=LIGHT_UPTAKE_HALF,
    primary_energy_density_response=True,
    stats_interval=STATS_INTERVAL,
    snapshot_interval=SNAPSHOT_INTERVAL,
    max_population_halt=MAX_POPULATION_HALT,
)

# ---------------------------------------------------------------------------
# Runtime profiles (docs/Exp14_実験計画確定.md §9, HARD GATE §2)
# FULL: A=2k/B=5k/C=20k / COMPACT: A=2k/B=3k/C=10k
# 選定はpreflight実測runtimeのみで行う。科学結果で選ばない。
# ---------------------------------------------------------------------------
FULL_TICKS = dict(A=2_000, B=5_000, C=20_000)
COMPACT_TICKS = dict(A=2_000, B=3_000, C=10_000)

PROFILES = {"FULL": FULL_TICKS, "COMPACT": COMPACT_TICKS}

FULL_SELECT_MAX_HOURS = 9.0
COMPACT_MAX_HOURS = 10.0

# ---------------------------------------------------------------------------
# Phase A: mechanism diagnostic (§4-6)
# ---------------------------------------------------------------------------
PHASE_A_BASELINE = dict(
    light_cycle_enabled=True,
    light_cycle_period_ticks=200,
    light_day_fraction=0.5,
    light_max=4.0,
    energy_capacity=100.0,
    initial_energy=50.0,
    initial_matter=0.8,
    repro_energy_frac=0.6,
    chemical_absorption=0.0,  # chemical OFFはgenomeでなくConfig側grid未使用で担保
)

A1_LIGHT_MAX = 4.0 / 3.141592653589793  # 4/pi: cycle OFF時に時間平均供給を保つ

PHASE_A_ARMS: dict[str, dict] = {
    "A0": {},  # baseline そのまま
    "A1": dict(light_cycle_enabled=False, light_max=A1_LIGHT_MAX),
    "A2": dict(light_cycle_period_ticks=80),
    "A3": dict(light_max=8.0),
    "A4": dict(repro_energy_frac=0.8),
    "A5": dict(initial_energy=40.0),
    "A6": dict(energy_capacity=200.0, initial_energy=100.0),
}
A_ARM_NAMES = ["A0", "A1", "A2", "A3", "A4", "A5", "A6"]
assert list(PHASE_A_ARMS.keys()) == A_ARM_NAMES

PHASE_A_SEEDS = list(range(1, 4))  # 1..3

PHASE_A_JOBS = len(PHASE_A_ARMS) * len(PHASE_A_SEEDS)  # 21
assert PHASE_A_JOBS == 21, f"Phase A jobs が21でない: {PHASE_A_JOBS}"

# 判定 (Exp14_レビュー判断.md M2 / 実装チェックリスト.md §5)
SURVIVES_SHORT_MIN_SEEDS = 3  # /3
MARGINAL_MIN_SEEDS = 2        # /3

# ---------------------------------------------------------------------------
# Phase B: period x energy_capacity boundary map (§7)
# ---------------------------------------------------------------------------
PHASE_B_PERIODS = [80, 120, 160, 200, 240]
PHASE_B_CAPACITIES = [75, 100, 125, 150, 200]
PHASE_B_SEEDS = list(range(1, 4))  # 1..3

PHASE_B_COMMON = dict(
    light_cycle_enabled=True,
    light_max=4.0,
    light_day_fraction=0.5,
    repro_energy_frac=0.6,
    initial_matter=0.8,
)

PHASE_B_JOBS = len(PHASE_B_PERIODS) * len(PHASE_B_CAPACITIES) * len(PHASE_B_SEEDS)  # 75
assert PHASE_B_JOBS == 75, f"Phase B jobs が75でない: {PHASE_B_JOBS}"


def phase_b_initial_energy(energy_capacity: float) -> float:
    """Phase B: 全gridでinitial E/Emax fill fraction(=0.625)を保つ導出値。

    baseline: energy_capacity=100, initial_energy=50, initial_matter=0.8
      -> E_max = 100*0.8 = 80, fraction = 50/80 = 0.625
    generatorがhardcodeせずここで計算する (実装チェックリスト.md §7.1)。
    """
    e_max_baseline = 100.0 * 0.8
    fraction = 50.0 / e_max_baseline
    e_max = energy_capacity * PHASE_B_COMMON["initial_matter"]
    return fraction * e_max


# ---------------------------------------------------------------------------
# Phase C: evolutionary rescue probe (§8)
# ---------------------------------------------------------------------------
PHASE_C_COMMON = dict(
    light_cycle_enabled=True,
    light_cycle_period_ticks=200,
    light_day_fraction=0.5,
    light_max=4.0,
    energy_capacity=100.0,
    initial_energy=50.0,
    initial_matter=0.8,
    repro_energy_frac=0.6,
)

PHASE_C_MUTABLE_GENES: dict[str, list[str]] = {
    "C1": ["body_size"],
    "C2": ["reproduction_investment"],
    "C3": ["movement_power"],
    "C4": ["body_size", "reproduction_investment", "movement_power"],
}
C_ARM_NAMES = ["C1", "C2", "C3", "C4"]
assert list(PHASE_C_MUTABLE_GENES.keys()) == C_ARM_NAMES

for _arm, _mutable in PHASE_C_MUTABLE_GENES.items():
    for _g in _mutable:
        assert _g in GENE_NAMES, f"{_arm}: {_g} はGENE_NAMESにない"


def phase_c_fixed_genes(arm: str) -> list[str]:
    """canonical GENE_NAMESからmutable以外を機械的に導出する。

    手書きの固定遺伝子リストを重複して持たない (AGENTS.md §10 / 実装
    チェックリスト.md §9 再発防止)。
    """
    mutable = set(PHASE_C_MUTABLE_GENES[arm])
    return [g for g in GENE_NAMES if g not in mutable]


PHASE_C_SEEDS = list(range(1, 6))  # 1..5
PHASE_C_JOBS = len(PHASE_C_MUTABLE_GENES) * len(PHASE_C_SEEDS)  # 20
assert PHASE_C_JOBS == 20, f"Phase C jobs が20でない: {PHASE_C_JOBS}"

TOTAL_RUNS = PHASE_A_JOBS + PHASE_B_JOBS + PHASE_C_JOBS  # 116
assert TOTAL_RUNS == 116, f"Exp14 formal run総数が116でない: {TOTAL_RUNS}"


# ---------------------------------------------------------------------------
# R_ref: 診断専用の解析的推定量 (実装チェックリスト.md §4)
#
# R_ref = night_length_ticks / night_survival_ticks(reference reserve)
#
# 絶対にsimulation状態/fitness/行動へフィードしない。cross-arm順序比較の
# 診断値としてのみ使う (docs/Exp14_レビュー判断.md §2)。
# light_maxは直接入れない (光量そのものではなく夜間の時間×維持コスト対
# 貯蔵の比を見る)。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RRefInputs:
    light_cycle_enabled: bool
    light_cycle_period_ticks: float
    light_day_fraction: float
    energy_capacity: float
    initial_matter: float
    repro_energy_frac: float
    # 維持コスト計算に使うreference個体 (INITIAL_GENOME相当)
    body_size: float = 1.0
    sensory_range: float = 0.4
    membrane_strength: float = 0.5
    damage_resistance: float = 0.1
    movement_power: float = 0.5
    movement_efficiency: float = 1.0
    ability_gene_sum: float = 1.5  # organ_upkeep対象5能力遺伝子の合計 (reference)
    # Config物理定数 (evosim.config.Config default値をそのまま渡す)
    bmr_core: float = 0.15
    bmr_coef: float = 0.3
    organ_upkeep: float = 0.05
    sense_upkeep: float = 0.02
    membrane_upkeep: float = 0.03
    resist_upkeep: float = 0.02
    move_cost: float = 0.05
    speed_coef: float = 3.0
    wander_speed_frac: float = 0.6


def reference_maintenance_rate(inp: RRefInputs) -> float:
    """reference個体1体・1tickあたりの維持Energy消費 [E/tick]。

    evosim/simulation.pyのBMR/organ/sense/membrane/resist/move式と同じ
    構造を使う (実装チェックリスト.md §4: 「実装と同じ夜間コスト構造を
    使うこと」)。
    """
    m = inp.body_size
    bmr = inp.bmr_core + (inp.bmr_coef - inp.bmr_core) * (m ** 0.75)
    organ = inp.organ_upkeep * m * inp.ability_gene_sum
    sense = inp.sense_upkeep * inp.sensory_range ** 2
    membrane = inp.membrane_upkeep * inp.membrane_strength * (m ** 0.5)
    resist = inp.resist_upkeep * inp.damage_resistance * m
    v_max = inp.speed_coef * inp.movement_power / (m ** 0.5)
    v_ref = inp.wander_speed_frac * v_max
    move = inp.move_cost * m * (v_ref ** 2) / inp.movement_efficiency
    return bmr + organ + sense + membrane + resist + move


def reference_reserve(inp: RRefInputs) -> float:
    e_max = inp.energy_capacity * inp.initial_matter
    return inp.repro_energy_frac * e_max


def night_length_ticks(inp: RRefInputs) -> float:
    if not inp.light_cycle_enabled:
        return 0.0
    return inp.light_cycle_period_ticks * (1.0 - inp.light_day_fraction)


def night_survival_ticks(inp: RRefInputs) -> float:
    rate = reference_maintenance_rate(inp)
    if rate <= 0.0:
        return float("inf")
    return reference_reserve(inp) / rate


def r_ref(inp: RRefInputs) -> float:
    """R_ref = night_length_ticks / night_survival_ticks。

    light_cycle_enabled=Falseならnight_length=0、R_ref=0。
    """
    survival = night_survival_ticks(inp)
    if survival == float("inf"):
        return 0.0
    length = night_length_ticks(inp)
    return length / survival


def r_ref_for_arm(arm_overrides: dict) -> float:
    """Phase A baseline + arm差分からR_ref入力を組み立てて計算する。

    A6は energy_capacity と initial_energy(→fraction経由でreserveへ影響)
    の両方を反映しなければならない (A6が「initial charge fractionを変える
    実装にしない」= fraction一定を保ったままcapacityだけ効かせる)。
    """
    cfg = dict(PHASE_A_BASELINE)
    cfg.update(arm_overrides)
    # reference reserve = repro_energy_frac * E_max (steady-state繁殖しきい値
    # を「定常的に維持しうる貯蔵水準」の代理として使う。実装チェックリスト
    # §4の4テスト対象 A2/A3/A4/A6 はいずれもこの経路で正しく順序付けられる)。
    # A5はinitial_energyのみを変える「tick-1初期条件」限定のarmであり、
    # 定常reserveの代理であるrepro_energy_frac自体は変えないため、
    # R_refはA0と一致する (これは意図通りで、A5がR_ref非依存の
    # 初期条件効果だけを単離するという設計と整合する)。
    inp = RRefInputs(
        light_cycle_enabled=cfg["light_cycle_enabled"],
        light_cycle_period_ticks=cfg["light_cycle_period_ticks"],
        light_day_fraction=cfg["light_day_fraction"],
        energy_capacity=cfg["energy_capacity"],
        initial_matter=cfg["initial_matter"],
        repro_energy_frac=cfg["repro_energy_frac"],
    )
    return r_ref(inp)


# ---------------------------------------------------------------------------
# selected value artifact (Phase Aの結果を恒久default化しないため、
# Exp14では「選定」はない。runtime profile記録用のみ)
# ---------------------------------------------------------------------------
RUNTIME_REPORT_FILE_NAME = "exp14_runtime_report.json"


# ---------------------------------------------------------------------------
# 昼夜由来の事後集計 (recorder非改変で済ませる観測)
#
# stats.csv (tick, population, light_cycle_factor) と events.csv
# (tick, event, cause) と Config だけから、sunset/dawn population・
# daytime peak・night minimum・daylight_births_cum・
# night_starvation_deaths_cum を再構成する。recorder/simulationへ新規
# stateを足さないため、観測非干渉の対象そのものが存在しない
# (実装チェックリスト.md §6)。
# ---------------------------------------------------------------------------

def is_night_tick(tick: int, cfg: Config) -> bool:
    """evosim.daynight.daylight_factorと同じ判定 (factor==0.0が厳密night)。"""
    from evosim.daynight import daylight_factor
    return daylight_factor(tick, cfg) == 0.0


def cycle_observation_from_rows(stats_rows: list[dict], cfg: Config) -> dict:
    """stats.csvの行列 (tick昇順) からday/night遷移由来の指標を作る。

    各行の `light_cycle_factor` を使い、0.0<->0.0でない、の遷移を
    sunset(day->night)/dawn(night->day)とみなす。
    """
    sunset_pops: list[int] = []
    dawn_pops: list[int] = []
    day_peaks: list[int] = []
    night_mins: list[int] = []
    cur_day_peak = None
    cur_night_min = None
    prev_night = None
    for row in stats_rows:
        night = float(row["light_cycle_factor"]) == 0.0
        pop = int(row["population"])
        if prev_night is None:
            prev_night = night
            if night:
                cur_night_min = pop
            else:
                cur_day_peak = pop
        if night != prev_night:
            if prev_night is False and night is True:
                # day -> night: sunset
                sunset_pops.append(pop)
                if cur_day_peak is not None:
                    day_peaks.append(cur_day_peak)
                cur_day_peak = None
                cur_night_min = pop
            else:
                # night -> day: dawn
                dawn_pops.append(pop)
                if cur_night_min is not None:
                    night_mins.append(cur_night_min)
                cur_night_min = None
                cur_day_peak = pop
            prev_night = night
        else:
            if night:
                cur_night_min = pop if cur_night_min is None else min(cur_night_min, pop)
            else:
                cur_day_peak = pop if cur_day_peak is None else max(cur_day_peak, pop)
    return {
        "sunset_population": sunset_pops,
        "dawn_population": dawn_pops,
        "daytime_peak_population": day_peaks,
        "night_minimum_population": night_mins,
    }


def daylight_births_and_night_starvation(events_rows: list[dict], cfg: Config) -> dict:
    births_day = 0
    deaths_night_starvation = 0
    for row in events_rows:
        tick = int(row["tick"])
        night = is_night_tick(tick, cfg)
        if row["event"] == "birth" and not night:
            births_day += 1
        elif row["event"] == "death" and row["cause"] == "starvation" and night:
            deaths_night_starvation += 1
    return {
        "daylight_births_cum": births_day,
        "night_starvation_deaths_cum": deaths_night_starvation,
    }


# ---------------------------------------------------------------------------
# late window N/A semantics (Exp13バグ修正: 実装チェックリスト.md §5)
# ---------------------------------------------------------------------------

def late_window_metric(rows: list[dict], final_tick: int, window: int, key: str,
                        agg="mean"):
    """final_tick < window なら late window未到達 -> None (N/A)。

    Exp13では cutoff = final_tick - window が負になり、window条件を
    満たさない行まで平均に混ざって early-extinction runが誤って
    late_pop_ok=True になるバグがあった。ここでは final_tick < window の
    場合を明示的にNoneで返し、呼び出し側がPASS/FAIL集計へ混入させない
    ことを強制する。
    """
    if final_tick < window:
        return None
    cutoff = final_tick - window
    vals = [float(r[key]) for r in rows if int(r["tick"]) >= cutoff]
    if not vals:
        return None
    if agg == "mean":
        return sum(vals) / len(vals)
    if agg == "max":
        return max(vals)
    if agg == "min":
        return min(vals)
    raise ValueError(agg)


def classify_phase_a_arm(seed_results: list[dict]) -> str:
    """SURVIVES_SHORT(3/3) / MARGINAL(2/3) / COLLAPSE(0-1/3)。

    seed_results 各要素は {"reached_full_ticks": bool, "final_population": int}。
    N/A値はここに来ない (呼び出し側でN/Aはこの判定に混ぜない)。
    """
    n_survive = sum(1 for r in seed_results
                    if r["reached_full_ticks"] and r["final_population"] > 0)
    if n_survive >= SURVIVES_SHORT_MIN_SEEDS:
        return "SURVIVES_SHORT"
    if n_survive >= MARGINAL_MIN_SEEDS:
        return "MARGINAL"
    return "COLLAPSE"
