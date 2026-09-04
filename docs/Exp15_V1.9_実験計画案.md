# Exp15 V1.9 実験計画

更新: 2026-09-04
状態: **IMPLEMENTATION-READY / DO NOT DISPATCH UNTIL V1.9 PHASE-0 GATE PASSES**

正本実装仕様: `docs/V1.9_検証実装仕様_物理スケール版.md`

旧 `docs/Exp15_実験計画確定.md` はV1.8時代の計画であり **SUPERSEDED / DO NOT DISPATCH**。

本Exp15は、議論をこれ以上長引かせず、現在のV1.9仮説を実際に検証するための最初のformal experimentである。

> **Exp15の主題は「H2枯渇競争」ではない。物理単位へ接続したH2空間勾配の中で、chemical-first iLUCAが成立し、storage / starvation / reproduction strategyが自然選択へ接続されるか」を見る。**

H2 biological depletionは記録するが、depletionが大きいことを成功条件にしない。

---

# 1. 仮説

## H15-0 physical-environment hypothesis

物理スケール版V1.9 worldには、同一world内に:

```text
H2-rich / net Energy positive region
H2-poor / net Energy negative region
```

の両方が成立する。

## H15-1 fixed-iLUCA hypothesis

fixed iLUCAはrandom spawnからH2勾配を経験し、少なくとも一部seedで複数世代を形成できる。

resource-rich領域でも必ず赤字になる旧PR #67のunit mismatchは解消されている。

## H15-2 adaptive-physiology hypothesis

以下3形質のみ進化可能にすると:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

fixed ancestorに対して再現性のある形質変化、またはadaptive rescue / physiology shiftが起きる。

## H15-3 attribution hypothesis

Phase Bで明確な応答が出た場合、その後のPhase C単独解禁で寄与を切り分けられる。

---

# 2. Exp15前 Phase 0 — 非formal preflight

Phase 0はV1.9実装チェックであり、formal Exp15 runには数えない。
自動parameter sweep / PASSさせるためのtuningは禁止。

## P0-A no-organism H2 field

条件:

```text
duration = 6 h
organism = 0
standard dt = 10 s
```

確認:

- source cell ≈ 1 mM
- source外へ滑らかなH2 gradient
- negative concentrationなし
- H2 source/exchange ledger閉鎖
- diffusion subcycle CFL条件成立

## P0-B radial single-cell Energy balance

reproduction OFF / movement OFF。
sourceから距離:

```text
0 / 2 / 4 / 8 / 12 / 16 cells
```

各1個体、24 h。

記録:

```text
local H2 [mM]
H2 uptake [mol/s]
Energy income power [W]
P_full [W]
net power [W]
Energy trajectory [J]
runway [s]
```

**必須gate:** world内に少なくとも1つ `net power > 0` の距離帯と、少なくとも1つ `net power < 0` の距離帯が存在する。

- 全距離positive -> 選択圧不足としてSTOP
- 全距離negative -> Energy/scale不整合としてSTOP

どちらも自動調整せず人間へ報告。

## P0-C random movement exposure

```text
initial_population = 100
fixed genome
random spawn
reproduction OFF
duration = 48 h
```

確認:

- 個体が異なるH2 exposureを経験する
- starvation responseが一部で作動
- temporal sensingのdQが全期間ほぼ0ではない
- high-H2 occupancyが完全0にならない

## P0-D timestep convergence

P0-A + P0-B代表caseを:

```text
dt = 2.5 / 5 / 10 s
```

で比較。

PASS目安:

```text
5 s vs 10 s:
  H2 profile主要band差 <= 5%
  24 h Energy差 <= 5%
```

2.5 sはreference。

## Phase 0 dispatch gate

```text
[ ] full tests PASS
[ ] Energy/Matter/H2 conservation PASS
[ ] same-seed determinism PASS
[ ] P0-A PASS
[ ] P0-B positive/negative region both exist
[ ] P0-C heterogeneous exposure PASS
[ ] P0-D dt convergence PASS
```

全部PASS後にformal Exp15へ進む。

---

# 3. 共通formal config

```text
physical model     = V1.9 physical-scale verification baseline
agent semantics    = 1 agent = 1 cell
world              = 20 mm x 20 mm
40 x 40 grid
cell length        = 0.5 mm
effective depth    = 0.5 mm
biology dt         = 10 s
H2 source          = 4 fixed point-source cells, 1 mM reservoir boundary
D_H2               = 5e-9 m2/s
H2 exchange tau    = 900 s
PHOTOTROPHY        = OFF
PREDATION          = OFF/locked
light_absorption   = 0
damage axes        = OFF (metabolic_damage=0, movement_damage=0)
initial population = 100
initial matter     = 0.50 matter unit
initial Energy     = 0.50 * E_max
initial placement  = world uniform random
max population halt = 5000
```

Matter:

```text
1 matter unit = 0.28 pgDW
initial nutrient = 2 matter unit / voxel
```

binary fission reference:

```text
repro matter gate = matter >= body_size
child matter = 50%
reproduction_investment initial = 50%
birth_overhead = 0 J
```

formal duration:

```text
10 physical days = 864000 s
```

standard dt=10 sなら86400 steps/run。

seed set:

```text
15001
15002
15003
15004
15005
```

Phase A/Bは必ず同一seed setを使う。
vent placement / initial positions等もmatched seedで比較する。

Recorder:

```text
stats every 10 min = 600 s
snapshot every 6 h = 21600 s
```

---

# 4. Phase A — fixed iLUCA baseline

## 4.1 purpose

physical-scale chemical-first iLUCAそのものが、H2 gradient worldでどの程度成立するかを確認する。

## 4.2 evolution

全continuous genes固定。

```text
storage_capacity fixed
starvation_horizon fixed
reproduction_horizon fixed
all other genes fixed
initial jitter OFF
PHOTOTROPHY innovation OFF
PREDATION locked
```

## 4.3 runs

```text
5 seeds x 10 days = 5 runs
```

## 4.4 primary readouts

population / generation:

- population(t)
- births / deaths / death cause
- extinction time [h/d]
- max generation
- median generation
- realized parent-child generation intervals [h]
- population-time AUC

Energy physiology:

- Energy [J]
- P_income / P_full / net power [W]
- runway [s/h]
- metabolic_factor / uptake_factor
- starvation-response occupancy
- E/Emax
- movement power
- growth Energy

H2 spatial ecology:

- H2 field [mM]
- organism-local H2 distribution
- source-distance occupancy
- high-H2 / low-H2 occupancy
- dQ_chem distribution
- H2 biological uptake / source influx ratio

conservation:

- Energy residual
- Matter residual
- H2 mol residual

## 4.5 Phase A adequacy gate

Phase Bへ正式に進む最低条件:

```text
>= 3/5 seeds が max_generation >= 5
```

10日で5世代にも到達しないseedが多数なら、進化実験の時間スケールとして情報不足なのでPhase BをSTOPし、人間レビューへ戻す。

なおfixed iLUCAの絶滅自体はFAILではない。

---

# 5. Phase B — adaptive physiology evolution

## 5.1 purpose

同一physical environmentで、新設3形質が自然選択へ実際に接続されるか確認する。

## 5.2 evolve genes

進化ON:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

固定:

```text
その他全continuous genes
PHOTOTROPHY innovation OFF
PREDATION locked
```

initial standing variation:

```text
上記3 genesのみ initial jitter sigma = 0.02
その他genes = exact baseline
```

continuous mutationは既存V1.9 mutation mechanismを使用。

## 5.3 runs

```text
same 5 seeds x 10 days = 5 runs
```

## 5.4 primary comparison

```text
A(seed_i) fixed
vs
B(seed_i) 3-gene evolution
```

matched-pairで比較する。

## 5.5 evolutionary-response判定

### Case 1: Phase Aがfragile / collapse傾向

adaptive rescue evidence:

```text
Phase BがPhase Aより survival time / generation reach / population-time AUC の
少なくとも1つで同方向改善を >=4/5 matched seedsで示す
```

かつ、3形質の少なくとも1つが最終20%時間窓で初期値から10%以上ずれる。

### Case 2: Phase Aがstable

population改善を必須にしない。

response evidence:

```text
少なくとも1形質が同方向へ >=10% shift を >=4/5 seedsで示す
AND
runway / starvation-response occupancy / reproduction interval のいずれかが
Phase Aから同方向へ >=10%変化する
```

これは「自然界の閾値」を主張する基準ではなく、Exp15で進化レバーが実際にfitnessへ接続されているかを判定する事前登録ルール。

---

# 6. Phase C — attribution

**Phase A/B結果を人間レビューした後のみdispatch。自動実行しない。**

候補:

| Arm | storage_capacity | starvation_horizon | reproduction_horizon |
|---|---|---|---|
| C0 | fixed | fixed | fixed |
| C1 | evolve | fixed | fixed |
| C2 | fixed | evolve | fixed |
| C3 | fixed | fixed | evolve |
| C4 | evolve | evolve | evolve |

Phase Bで複数形質が動いた、またはadaptive rescueが確認された場合に寄与を切り分ける。

---

# 7. Exp15で主張しないこと

Exp15では以下を証明しない。

- LUCAの正確なサイズ/倍加時間
- H2競争が自然界と同じ強さであること
- H2 depletionが主要選択圧であること
- phototrophy origin
- oxygen / temperature / pH / pressure適応
- biofilm / colony ecology
- predation

Exp15が検証するのは:

> **physical-unit chemical-first baseline + heterogeneous H2 exposure + evolvable homeostasis strategy が、モデル内部で自己矛盾なく機能するか。**

---

# 8. Exp16への接続

Exp15でbaselineとadaptive physiologyが成立した後、Exp16でphototrophy originへ進む。

その前にlight fluxをW/m2 / photon flux等のphysical unitへ再校正する。

```text
chemical-first ancestor
 -> phototrophy structural innovation
 -> weak light use
 -> selection/refinement
 -> day/night secondary pressure
```

---

# 9. implementation / dispatch order

```text
V1.9 physical-scale patch implementation
 -> unit/integration tests
 -> conservation / determinism
 -> Phase 0 P0-A/B/C/D
 -> implementation report
 -> human review
 -> Exp15 Phase A dispatch
 -> Phase A adequacy review
 -> Exp15 Phase B dispatch
 -> A/B analysis
 -> human decision on Phase C
```

Claude / SonnetはPhase 0 PASS前にformal Phase A/Bをdispatchしない。
