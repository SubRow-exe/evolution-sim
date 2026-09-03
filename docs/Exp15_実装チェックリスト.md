# Exp15 実装チェックリスト — Sonnet 5向け

更新: 2026-09-04
状態: **実装仕様確定 / この文書だけで実装開始可能**

正本優先順:
1. `docs/Exp15_実験計画確定.md`
2. `docs/Exp14_表現型プロベナンス訂正.md`
3. `docs/環境因子追加・校正方針.md`
4. `docs/V1.8_一次Energy生態非対称仕様.md`
5. `AGENTS.md`

このチェックリストと計画書の科学条件をSonnet判断で変更しない。

---

# 0. 実装禁止事項

Exp15実装ではsimulation科学則を変更しない。

禁止:
- light uptake式変更
- `H(x,K)`変更
- daylight shape変更
- BMR/reproduction/movement/repair式変更
- `light_uptake_half`変更
- period/capacity/repro条件の隠れsweep
- 初期genome変更
- light specialistへのfitness bonus
- 結果を見て条件追加
- Phase AからPhase Bへの自動遷移

許可:
- Config generator/checker/summarizer/workflow追加
- **読み取り専用・非干渉の観測counter追加**
- 観測counter用の独立test追加

---

# 1. 新規/更新ファイル

最低限:

```text
tools/exp15_common.py
tools/make_exp15_configs.py
tools/check_exp15.py
tools/summarize_exp15.py
tools/exp15_runtime_report.py
.github/workflows/exp15.yml

tests/test_exp15_common.py
tests/test_exp15_configs.py
tests/test_check_exp15.py
tests/test_summarize_exp15.py
tests/test_exp15_observation_noninterference.py

docs/Exp15_実装監査.md
```

必要なら観測追加で:

```text
evosim/simulation.py
evosim/recorder.py
```

を変更してよい。

既存Exp14 helperを再利用できる場合は再利用する。day/night境界判定を別実装で複製しない。

---

# 2. `tools/exp15_common.py`

全generator/checker/summarizerが共有する科学定数を一元化する。

必須定数:

```python
LIGHT_SPECIALIST = {
    "light_absorption": 2.0,
    "chemical_absorption": 0.3,
}

PHASE_A_LIGHT_MAX = 1.2
PHASE_A_SEEDS = [1,2,3,4,5]
PHASE_A_TICKS = 5_000
PHASE_A_ARMS = ["A0","A1","A2","A3","A4"]

PHASE_B_LIGHT_MAX = [1.2, 2.4, 4.0, 6.0, 8.0, 12.0]
PHASE_B_SEEDS = [1,2,3]
PHASE_B_TICKS = 10_000

LIGHT_UPTAKE_HALF = 0.6
PERIOD = 200
DAY_FRACTION = 0.5
ENERGY_CAPACITY = 100.0
INITIAL_ENERGY = 50.0
INITIAL_MATTER = 0.8
REPRO_ENERGY_FRAC = 0.6
```

job数assert:

```text
Phase A = 25
Phase B = 18
TOTAL_MAX = 43
```

A0/A4は科学Configが完全同一であることを定数レベルでも明示する。

---

# 3. `make_exp15_configs.py`

## 3.1 共通Config

必ず:

```python
fixed_genes=list(GENE_NAMES)
diagnostic_gene_overrides=dict(LIGHT_SPECIALIST)
diagnostic_placement="random"
chem_vent_flux=0.0
light_pattern="vertical"
bmr_core=0.15
memory_tau=10.0
response_gain=64.0
light_uptake_half=0.6
energy_capacity=100.0
initial_energy=50.0
initial_matter=0.8
repro_energy_frac=0.6
light_cycle_period_ticks=200
light_day_fraction=0.5
stats_interval=20
snapshot_interval=1000
max_population_halt=10000
```

を明示する。

Config defaultへ暗黙依存しすぎない。Exp15正本値が将来default変更で変わらないようにする。

## 3.2 Phase A

```text
A0: cycle=False, density=False, light_max=1.2
A1: cycle=False, density=True,  light_max=1.2
A2: cycle=True,  density=False, light_max=1.2
A3: cycle=True,  density=True,  light_max=1.2
A4: cycle=False, density=False, light_max=1.2
```

A4はA0の完全duplicate sentinel。

Config名:

```text
exp15_A_A0.json
...
exp15_A_A4.json
```

run keyはworkflow側で:

```text
exp15_A_A0_seed1
...
```

## 3.3 Phase B

```text
cycle=True
density=True
light_max = 1.2/2.4/4.0/6.0/8.0/12.0
```

Config名はfloat文字列表現揺れを避ける。
推奨:

```text
exp15_B_L1p2.json
exp15_B_L2p4.json
exp15_B_L4p0.json
exp15_B_L6p0.json
exp15_B_L8p0.json
exp15_B_L12p0.json
```

---

# 4. 最重要E2E phenotype oracle

`test_exp15_configs.py`でConfig fieldだけを見るtestでは不十分。

必ず各Phase代表Configを使い:

```python
sim = Simulation(cfg, seed=1)
assert len(sim.organisms) == 100
for o in sim.organisms:
    assert o.genome[LIGHT_ABS] == 2.0
    assert o.genome[CHEM_ABS] == 0.3
```

を実施する。

少なくとも:
- A0
- A1
- A2
- A3
- Phase B L4.0

で確認する。

さらに全生成Configについて`diagnostic_gene_overrides`と`fixed_genes`をcheckerが確認する。

このoracleはgeneratorと同じ定数だけを参照して自己正当化しない。
期待値`2.0/.3`をtest側独立oracleとして明示する。

---

# 5. Config差分oracle

Phase A A0-A3は以下以外が全field一致することを独立testする。

許可差分:

```text
light_cycle_enabled
primary_energy_density_response
```

A0 vs A4は**Config全field完全一致**。

Phase B 6 Configは:

```text
light_max
```

以外が完全一致。

これにより隠れparameter交絡を防止する。

---

# 6. 観測counter追加

`docs/Exp15_実験計画確定.md §7-8`を満たすため、既存simulationへ読み取り専用累積counterを追加する。

推奨名称:

```python
self.exp15_obs = {
    "organism_ticks": 0,
    "maintenance_movement_cost": 0.0,
    "repair_cost": 0.0,
    "birth_overhead": 0.0,
    "light_h_events": 0,
    "light_h_sum": 0.0,
    "light_h_values_interval": [],   # percentileが必要ならinterval専用
}
```

ただし大量listを全run累積しない。
percentile用はstats interval内だけ保持し、Recorder記録後resetする方式を優先する。

## 6.1 organism ticks

1個体がそのstepで生理処理対象になった時点で1加算。
死亡済み/skip個体を二重計上しない。

## 6.2 maintenance/movement

既存:

```python
cost = physiology.maintenance_and_movement(...)
self.energy_out_cum += cost
```

の`cost`を同時に観測counterへ加算する。
**関数を2回呼ばない。**

## 6.3 repair

既存`physiology.repair()`戻り値を一度だけ受け、energy ledgerと観測counterへ同じ値を加える。

## 6.4 birth overhead

既存reproductionで実際に`cfg.birth_overhead`を散逸計上した時だけcounterへ加算する。

simulation結果へcounterを戻さない。

---

# 7. light H観測

light uptake処理で、実際に使われるeffective local light `I`と同じ値から計算する。

観測対象:

```text
daylight_factor_now > 0
I > 0
organism light_absorption > ABILITY_EPS
```

density flag OFF時も比較用に**counter上だけ同じH(I,K)を計算してよい**。
これは「もしresponseを適用した場合の局所operating point」を比較する診断であり、gain計算へは戻さない。

記録:

```text
light_H_events
light_H_mean
light_H_p10
light_H_median
light_H_p90
light_H_frac_lt_0p05
light_H_frac_gt_0p95
```

night `I=0`は除外。

percentile計算でsimulationのRNG/stateを触らない。

---

# 8. Recorder列

既存`stats.csv`へ追加する場合、列末尾または意味が明確な観測セクションへ追加する。

最低限interval/cumulativeの意味を列名で曖昧にしない。

推奨:

```text
organism_ticks_cum
maint_move_cost_cum
repair_cost_cum
birth_overhead_cum
light_gain_per_org_tick_cum
maint_move_per_org_tick_cum
repair_per_org_tick_cum
birth_overhead_per_org_tick_cum
core_net_E_per_org_tick_cum

light_H_events_interval
light_H_mean_interval
light_H_p10_interval
light_H_median_interval
light_H_p90_interval
light_H_frac_lt_0p05_interval
light_H_frac_gt_0p95_interval
```

既存`flow_light_cum`を利用し、light gainを二重counterにしない。

`core_net_E_per_org_tick_cum`:

```text
(flow_light_cum
 - maint_move_cost_cum
 - repair_cost_cum
 - birth_overhead_cum)
 / organism_ticks_cum
```

0 denominatorはblank/N/A。

---

# 9. 観測非干渉test

`test_exp15_observation_noninterference.py`必須。

同一Config/seedで:

- 新観測あり通常run
- 新観測値を記録しないreference path、または変更前と等価なpath

を比較し、少なくとも最初の500-2,000 tickについて:

```text
population
organism ids
position
energy
matter
damage
genome
lineage/generation
world nutrient/chemical
flows
birth/death events
RNG state
```

が一致することを確認する。

観測機能のためにRNGを1回でも追加消費してはいけない。

既存`tests/test_exp14_observation_noninterference.py`を参考にする。

---

# 10. day/night post-hoc helper

Exp14で実装済みのsunset/dawn helperを再利用・一般化する。

必須出力:

```text
sunset_population
dawn_population
sunset_energy_frac_median
dawn_energy_frac_median
day_peak_population
night_min_population
night_min_over_day_peak
```

stats interval=20、period=200の境界で意味が定義できることをunit testする。

cycle OFFではday/night由来列をN/Aにし、偽のsunset/dawnを生成しない。

---

# 11. `check_exp15.py`

2モード:

```text
static/check-config
run-dir completeness/scientific-input integrity
```

最低限check:

### Config
- Phase A 5 configs
- Phase B 6 configs
- job counts 25/18
- seed set exact
- fixed_genes exact 14
- overrides exact 2.0/.3
- chemical OFF
- Phase A差分only flags
- A0=A4
- Phase B差分only light_max
- K=.6 / period200 / day.5 / cap100 exact

### run artifact
各runに:

```text
config.json
meta.json
stats.csv
events.csv
lineages.csv
performance.csv
```

が存在。

run key完全性:
- Phase Aなら25 unique keys
- Phase Bなら18 unique keys

`--skip-completeness`はpreflight smokeなどpartial collectでのみ明示使用可能。
formal collectorは絶対にskipしない。

### actual config provenance
run artifact内`config.json`を読み、予定Configと一致確認。

---

# 12. A0/A4 duplicate sentinel checker

Phase A collect後、seedごとにA0/A4を比較する。

比較対象:

```text
stats.csv       performance由来でない全科学列
events.csv
lineages.csv
snapshots       存在する共通tick
config.json     完全一致
```

`performance.csv`はwall-clock依存なので一致要求しない。
`meta.json`も実行環境情報・run timing差を理由にbit一致HARD GATEへしない。ただしPython/numpy/platform等の主要環境が同じHosted Runner familyであることをreportする。

A0/A4科学出力不一致:

```text
TECHNICAL_REVIEW = DUPLICATE_SENTINEL_MISMATCH
```

formal Phase A科学解釈を止める。

---

# 13. `summarize_exp15.py` — Phase A

出力:

```text
exp15_phase_a_summary.csv
exp15_phase_a_summary.json
exp15_phase_a_summary.md
```

armごと:

```text
n_seed
n_reached_target
n_extinct
n_overdriven
classification
extinction_tick median/range
final_population median/range
max_generation median/range
first_gen2_tick
first_gen5_tick
light_gain_per_org_tick
maint_move_per_org_tick
repair_per_org_tick
birth_overhead_per_org_tick
core_net_E_per_org_tick
energy_frac late/terminal summary
starvation deaths
```

A0 gateとA0/A4 sentinel結果を明記。

mechanism effectはA0基準で連続量差を表にするが、統計的p値で唯一原因を決めない。

---

# 14. `summarize_exp15.py` — Phase B

出力:

```text
exp15_phase_b_summary.csv
exp15_phase_b_summary.json
exp15_phase_b_summary.md
```

各light_max:

```text
3 seed分類
VIABLE/MIXED/COLLAPSE/OVERDRIVEN level
survival
max generation
population
Energy/capacity
core net Energy
H diagnostics
sunset/dawn reserve
```

事前登録規則だけで隣接VIABLE pairを探索する。

selection成立時のみ:

```text
exp15_selected_light.json
```

を生成する。

selection不成立時は値を捏造せず:

```json
{"status":"NO_ROBUST_LIGHT_REFERENCE"}
```

をsummary JSONへ記録する。

---

# 15. plots

最低限aggregate plot:

Phase A:
1. arm別population trajectory（seed薄線 + median）
2. arm別Energy/capacity trajectory
3. arm別 per-org-tick gain/cost/net比較

Phase B:
1. light_max vs level classification / survival count
2. light_max vs max_generation
3. light_max vs core net Energy
4. selected候補があればsunset→dawn reserve変化

plotは科学判定の唯一根拠にしない。CSV/JSONを正本にする。

---

# 16. Workflow

`.github/workflows/exp15.yml`

input:

```yaml
mode:
  choice: [preflight, phase_a, phase_b]
```

## preflight

- checkout
- uv sync --frozen
- Exp15 static checker
- Exp15 unit/integration tests
- full relevant conservation/determinism
- representative A0 5k ×2 deterministic smoke
- representative A3 5k runtime
- representative Phase B 10k runtime
- collector partial smoke
- runtime report作成
- artifact upload
- **終了**

## phase_a

matrix:

```text
arm A0-A4
seed 1-5
```

25 jobsを実行→artifact upload。
collector:
- exact 25 completeness
- config provenance
- A0/A4 sentinel
- summary/plots
- aggregate artifact

## phase_b

matrix:

```text
light 1.2/2.4/4/6/8/12
seed 1-3
```

18 jobs→collector→summary/selection artifact。

phase_a jobからphase_b jobへの`needs`は禁止。
同一dispatchで両Phaseを実行しない。

---

# 17. runtime report

`exp15_runtime_report.py`は少なくとも:

```text
A 5k representative sec
B 10k representative sec
A jobs/waves/max-parallel
B jobs/waves/max-parallel
setup overhead
collector overhead estimate
safety factor >=1.5
Phase A predicted wall-clock
Phase B predicted wall-clock
```

をJSONへ保存。

formal後summaryへprediction vs actualを追記できる構造にする。

10時間超予測ならそのPhaseを開始せず報告。

---

# 18. tests / CI HARD GATE

formal前に最低限:

```text
uv run pytest tests/test_exp15_common.py \
  tests/test_exp15_configs.py \
  tests/test_check_exp15.py \
  tests/test_summarize_exp15.py \
  tests/test_exp15_observation_noninterference.py -q

uv run pytest tests/test_conservation.py tests/test_determinism.py -q

uv run pytest -q
```

全てGREEN。

Config round-trip、invalid値validationも壊さない。

---

# 19. 実装監査文書

Sonnetは実装完了時に`docs/Exp15_実装監査.md`を作る。

表:

| Requirement | Implementation | Independent test | Status |
|---|---|---|---|

最低限以下を1行ずつ追跡:
- light specialist 2.0/.3 actual organism oracle
- A0-A3 flag-only differences
- A0/A4 duplicate sentinel
- Phase B light_max-only sweep
- no chemical
- H night exclusion
- cost counters
- observation noninterference
- exact run counts
- artifact completeness
- preflight/formal separation
- Phase A/Phase B separation
- selection rule
- scientific STOP vs technical FAIL

---

# 20. Sonnetへの完了条件

「実装完了」と言ってよいのは:

```text
1. 上記ファイル実装
2. 全test GREEN
3. Exp15_実装監査.md作成
4. preflight workflowが実行可能
5. formal Phase A/Phase Bはまだ人間dispatch待ち
6. V1.8 default値・科学則はまだ変更していない
```

まで。

**Sonnetは実装完了後に勝手にformalを開始しない。**
