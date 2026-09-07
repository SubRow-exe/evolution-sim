# Exp18 — V1.10.1 動的熱水噴出口 検証計画

更新: 2026-09-08  
状態: **PREREGISTRATION / Claude実装後に実行**

## 0. 目的

Exp18は、V1.10.1で導入するH2 source条件の時間変動・位置turnoverが、固定iLUCAおよび進化可能集団へどのような影響を与えるかを検証する。

本実験の中心は:

> **H2総供給量をできるだけ揃えたまま、供給の時間・空間パターンだけを変える。**

これにより、単純な「餌を減らした効果」とdynamic environmentの効果を分ける。

V1.10.1実装方針の正本:

- `docs/V1.10.1_動的熱水噴出口_実装方針.md`

---

# 1. 共通baseline

```text
physical_mode = True
dt = 10 s
world = 20 mm x 20 mm
40 x 40 grid
cell size = 0.5 mm
initial population = 100
H2 diffusion = 5e-9 m2/s
H2 exchange/loss tau = 900 s
vent count = 4
legacy geometry = (10,10),(10,30),(30,10),(30,30)
phototrophy OFF
predation OFF
```

C/N/P:

```text
50 biomass-equivalents
background exchange OFF
```

C/N/PはExp18で変更しない。

H2 uptake / Energy physiology / iLUCA genomeはV1.10確定値を維持する。

---

# 2. Phase 0 — source calibration / mechanical validation

formal multi-seedの前に必須。

## P0-A legacy Dirichlet source flux measurement

条件:

```text
organism = 0
4 source cells
10 mM Dirichlet
D = 5e-9 m2/s
tau = 900 s
```

旧V1.10 sourceを十分warm-upし、定常後のsource補給量を測る。

推奨:

```text
warm-up >= 6 h
measurement window = final 1 h以上
```

定義:

```text
F_total_legacy = source_in_mol / measurement_seconds
F0 = F_total_legacy / 4
```

この `F0` を以後のfinite-flux controlに使用する。

成果物へ実測値を保存する。

## P0-B finite flux source sanity

4 vents x `F0` を固定供給。

確認:

- source ledger == 4*F0*time
- field非負/finite
- H2 concentration gradient形成
- Energy/H2 ledger正常

## P0-C temporal supply equivalence

12 hについて比較。

Static:

```text
4 vents x F0 continuous
```

Temporal:

```text
2 vents active at a time
active vent = 2*F0
6hごとにpair切替
```

PASS:

```text
integrated source mol static == temporal
within numerical tolerance
```

## P0-D turnover geometry / RNG

48 h intervalで1 ventをrelocateするテスト。

PASS:

- vent count常時4
- 位置重複なし
- boundary/min separation制約PASS
- 同一seedでschedule完全一致
- 別seedで少なくとも一部scheduleが変わる
- organism RNGを消費しない

## P0-E dt convergence

`dt=5 s / 10 s` を最低限比較。

finite-flux static環境を短時間回し:

```text
total H2 source
final total H2 stock
representative radial concentration
```

が十分近いことを確認する。

---

# 3. Phase A — fixed iLUCA environmental comparison

目的:

> 進化を入れる前に、dynamic ventそのものが環境・生存・飢餓・世代交代へ与える影響を測る。

全continuous genes固定、initial jitter=0。

各条件:

```text
3 seeds x 10 physical days
seeds = 18001, 18002, 18003
```

## A0 Static finite flux control

```text
4 vents
位置固定
各vent flux = F0
24 h連続ON
```

## A1 Temporal fluctuation only

```text
位置固定
12 h cycle
6 h ON / 6 h OFF
2 ventずつ交互にON
ON vent flux = 2*F0
```

世界全体の瞬間総fluxは常にA0と同じ `4F0`。

## A2 Spatial turnover only

```text
4 vents常時ON
各vent flux = F0
48 hごとに1 ventを別位置へrelocate
vent countは常に4
```

世界全体の総fluxはA0と同じ。

## A3 Temporal + spatial turnover

```text
A1 + A2
```

時間変動と位置turnoverを同時に適用する。

---

# 4. Phase A readout

主要:

```text
survival / extinction time
population N(t)
max generation
births / deaths
population AUC
total biomass
mean runway
starvation-active fraction
mean local H2
H2 >= 248 uM occupancy fraction
H2 habitability fraction of world
mean distance to nearest active vent
H2 source / loss / biological uptake ledger
C/N/P ledger
```

特に比較したいもの:

1. A0に対するpopulation/generation低下
2. starvation時間の増加
3. active ventへの追従性
4. local extinction的なpopulation contractionが起きるか
5. A1とA2で「時間変動」と「場所変動」の影響が分離できるか

---

# 5. Phase A integrity / interpretation

A0はfinite-flux変換後のreference controlであり、V1.10 fixed iLUCAと大きく矛盾しないことを確認する。

目安:

```text
3/3 survive 10 d
複数世代へ到達
```

ただしDirichlet -> finite flux自体が生態を変えるため、V1.10 final Nとの一致は要求しない。

A1/A2/A3の絶滅はscientific resultであり、workflow FAILにしない。

ただしPhase Bへ使うdynamic conditionは、進化を観測できる程度の成立性が必要。

### Phase B dynamic arm selection rule

事後恣意性を避けるため、以下の順で選択する。

1. A3
2. A2
3. A1

各候補が:

```text
>= 2/3 seeds survive 10 d
AND
median max_generation >= 3
```

を満たした最初の条件をPhase B dynamic armとする。

どれも満たさない場合:

> Phase Bは実行せず「現在のdynamic条件は既存iLUCAに強すぎる」と報告する。

値を自動調整して救済しない。

---

# 6. Phase B — evolution test

目的:

> dynamic vent環境が、V1.9で追加したEnergy戦略3形質へ本当に異なる選択圧を与えるかを確認する。

進化対象は以下のみ。

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

その他のcontinuous genesは固定。

phototrophy/predation innovation OFF。

initial jitterは既存Exp15 evolution armと同orderを使用し、値をExp18結果から調整しない。

## 2 x 2 design

```text
Environment: STATIC / DYNAMIC
Genetics:    FIXED / EVOLVE
```

4 arms:

### B0 STATIC-FIXED

A0 static finite flux / 3 genes固定。

### B1 STATIC-EVOLVE

A0 static finite flux / 3 genes進化ON。

### B2 DYNAMIC-FIXED

Phase A selection ruleで決めたdynamic condition / 3 genes固定。

### B3 DYNAMIC-EVOLVE

同じdynamic condition / 3 genes進化ON。

各arm:

```text
5 seeds x 20 physical days
seeds = 18101-18105
```

同一seedを4 armで対応させる。

---

# 7. Phase B主要readout

生態:

```text
survival/extinction
population AUC
final / max population
max generation
generation interval
birth/death counts
starvation-active fraction
active vent occupancy
mean nearest-active-vent distance
```

進化:

```text
storage_capacity mean/median/q10/q90
starvation_horizon mean/median/q10/q90
reproduction_horizon mean/median/q10/q90
initial -> final shift
last 20% window mean
between-seed direction consistency
```

必要ならlineage-level reproductive successとの相関も出す。

---

# 8. Phase B仮説

方向をPASS条件として固定しない。

期待候補としては:

- dynamicでstorage_capacityの価値が上がる可能性
- starvation_horizonが変動時間スケールへ適応する可能性
- reproduction_horizonが「すぐ増える vs 貯めて耐える」のtrade-offを示す可能性

ただし、どの形質も動かない可能性を正式な結果として認める。

重要なのは:

> staticとdynamicで進化応答が異なるか、またEVOLVEがDYNAMIC-FIXEDより持続性を改善するか。

---

# 9. Exp18で変更禁止

formal開始後、結果に応じて以下を変更しない。

```text
F0 calibration method
12 h / 6 h temporal schedule
2x ON flux
48 h turnover interval
vent count=4
H2 diffusion/tau
C/N/P 50 equivalents
C/N/P exchange OFF
iLUCA physiology
3 evolution genesの範囲
run duration / seeds
```

変更が必要な場合はAttempt 1を保存し、human decisionでAttempt 2として明示する。

---

# 10. 成果物

各run:

```text
effective_config.json
initial_genome.json
vent_schedule.json
timeseries.csv
summary.json
H2 ledger
C/N/P ledger
snapshots (必要なsampling頻度)
```

aggregate:

```text
phase0_calibration.json
phaseA_aggregate.csv/json
phaseB_aggregate.csv/json
Exp18_result_summary.md
```

missing artifactはsilent skipせずintegrity FAIL。

---

# 11. Exp18終了時の判断

Exp18で決めたいことは「最適なvent schedule」ではない。

以下が分かれば十分。

1. finite-flux H2 sourceが数値・ledger上成立する
2. temporal/spatial variabilityがfixed ancestorへどの程度圧をかけるか
3. 3つのEnergy戦略形質がdynamic環境でstaticと異なる進化応答を示すか
4. dynamic environmentを次の世界のworking conditionとして使えるか

細かなcycle/turnover最適化は行わず、不都合が出た時点で後続experimentで見直す。
