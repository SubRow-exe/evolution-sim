# Exp17 — V1.10 C/N/P資源分解 検証計画

更新: 2026-09-07  
状態: **PREREGISTRATION DRAFT / 実装後そのまま実行可能**

## 0. 前提

Exp17はV1.10のmechanism validationであり、C/N/Pの「最適な環境値」を探す実験ではない。

前提:
- V1.9 Exp15 Phase Bを完了しV1.9 close判断後にformal Exp17へ進む
- iLUCA genome / H2 baseline / Energy physiologyはV1.9確定値を固定
- phototrophy / predation innovation OFF
- C/N/P以外の新規world ruleを同時に入れない
- formal run結果を見てreference concentrationを自動調整しない

目的:

> generic Matter fieldをC/N/Pへ置換しても、iLUCAの生存・成長・分裂が説明可能で、各元素を独立した成長律速として扱え、元素台帳が閉じることを確認する。

---

# 1. 仮説

## H17-1 mechanical conservation

C/N/Pを明示化しても、closed conditionでは各元素が数値誤差範囲で保存される。

## H17-2 stoichiometric limitation

C, N, Pのいずれか1つだけを有限量にした場合、その元素だけが成長上限を決める。

## H17-3 baseline viability

reference open C/N/P環境では、V1.9 iLUCAはH2由来Energyを使って生存・成長・世代交代できる。

## H17-4 V1.9 hidden Matter ceiling removal

V1.10では旧`nutrient_initial=2/cell`から自動的に決まっていた総Matter ≈3250 unitの固定ceilingが消える。

したがってformal baselineの最終NがV1.9 Exp16 baseline ≈3000と一致することは要求しない。

## H17-5 no forced competition

realistic-order C/N/P濃度で生物によるdepletionが小さくてもFAILとはしない。

現在の1 agent=1 cell / 20mm microhabitatで資源競争が弱いなら、それ自体を結果として保存する。competitionを発生させるために濃度を後付けで下げない。

---

# 2. Phase 0 — mechanical / ledger preflight

formal multi-seedの前に必須。

## P0-A closed single-cell growth

条件:
- 1 cell
- H2十分
- background exchange OFF
- C/N/Pを十分量
- growth ON
- reproduction OFF

確認:
- biomass増加とC/N/P消費が固定stoichiometryと一致
- Energy synthesis costがV1.9式と一致
- concentration非負

PASS:
- C/N/P各ledger residual relative <= 1e-9（浮動小数条件でabsolute floor併用可）
- stoichiometric requirement relative error <= 1e-9

## P0-B individual limiter sentinels

C-limited / N-limited / P-limitedを各1 run。

方法:
- background exchange OFF
- 初期population=100
- 初期organism総Matter=50 unit
- intended limiting resourceだけ「追加biomass +50 matter unitを作れる量」に設定
- 他2資源は最低でも+500 matter unit相当
- H2は十分

期待:
- intended resource depletionにより総biomass成長が頭打ち
- 他資源は有意に残る

PASS:
- intended resourceがgrowth limiter countの最大
- intended resource residual stock <= 5% initial
- non-limiting resources >= 50% initial
- element ledger PASS

※死亡・recyclingで少量戻るため、最終population数そのものを厳密gateにはしない。

## P0-C corpse/recycling

- closed C/N/P
- corpse生成 → decay
- predator OFF

PASS:
- corpseに保持されていたC/N/Pがdecay量に応じてfieldへ戻る
- total element inventory conserved

## P0-D predation/waste bookkeeping mechanical test

predation capabilityをdiagnosticで強制ONするmechanical testのみ。

PASS:
- prey matter loss = predator biomass gain + local C/N/P waste equivalent
- C/N/P ledger conserved

formal Exp17ではpredation OFF。

## P0-E dt convergence

`dt = 2.5 / 5 / 10 s`

同一fixed setup 6 h。

PASS目安:
- total biomass差 <= 1%
- total C/N/P field inventory差 <= 0.1%

---

# 3. Phase A — reference open environment

目的:

> 現実orderのopen C/N/P環境でV1.9 iLUCAが成立するかを確認する。

## 条件

- seeds: `17001–17005`
- 5 seeds
- 10 physical days
- initial population = 100
- all continuous genes fixed
- initial jitter = 0
- structural innovation OFF
- H2 = V1.9 baseline
  - source = 10 mM
  - D_H2 = 5e-9 m2/s
  - H2 loss/exchange tau = 900 s
  - square 4-source layout
- C/N/P:
  - DIC background = 2.2 mM C-equivalent
  - fixed N background = 10 uM N-equivalent
  - phosphate background = 1 uM P
  - CNP exchange tau = 900 s
  - D_DIC = 2.0e-9 m2/s
  - D_N = 2.0e-9 m2/s
  - D_P = 0.8e-9 m2/s

## 主要readout

- survival / extinction
- max generation
- N(t)
- total biomass [kgDW]
- mean matter
- C/N/P concentrations
- C/N/P cumulative uptake
- C/N/P external inflow/outflow
- element ledger residual
- growth_limiter fraction:
  - energy
  - kinetic
  - carbon
  - nitrogen
  - phosphorus
  - room
- H2 habitability fraction（V1.9 predictorも併記）

## gate

scientific viability gate:

```text
>= 3/5 seeds survive 10 days
AND
>= 3/5 seeds reach max_generation >= 5
AND
all 5 seeds have valid C/N/P ledgers
```

FAIL時:
- Phase Bへ進まない
- auto tuning禁止
- limiter/readoutから原因診断

注意:
- final NがV1.9 baseline ≈3000と一致することはgateにしない
- max_population_halt到達は生態平衡とは扱わない

---

# 4. Phase B — resource identity validation

Phase A PASS時のみ。

目的:

> C/N/Pのどれを減らしたかによって、対応するlimiterが切り替わることを確認する。

生存閾値探索ではなく、mechanism identity test。

## 条件

Phase A referenceから**1 resourceだけ**変更。

各condition 3 seeds、3 physical days。

```text
B0 reference
B1 low DIC      : DIC background x0.01
B2 low fixed N  : fixed N background x0.01
B3 low phosphate: phosphate background x0.01
```

他条件固定。

## 期待

- B1: carbon-limiter fractionがreferenceより明確に増える
- B2: nitrogen-limiter fractionが増える
- B3: phosphorus-limiter fractionが増える

PASS基準:

各low conditionで、対応limiter fractionが

```text
referenceの対応値 + 20 percentage points以上
OR
そのcondition内の最大limiterになる
```

のどちらか。

全滅は必須ではない。むしろ「成長は落ちるが生存する」でもmechanismとして十分。

---

# 5. Phase C — competition/depletion diagnostic【条件付き】

自動実行しない。

Phase A/B後にのみ判断。

実施条件:
- baselineでC/N/P biological uptake / external supplyが極端に小さく、C/N/Pが全く生態圧にならない場合

目的は無理にcompetitionを作ることではなく、**現在のmodel densityではどのpopulation orderからresource depletionが効き始めるか**を机上計算または短runで推定すること。

候補:
- initial populationを1e2 / 1e3 / 1e4相当で短時間比較
- 可能ならsimulationではなく supply / demand analytic estimateを優先

`cells_per_agent`導入はExp17では行わない。

---

# 6. 事前登録する解釈

## 6.1 baseline C/N/Pがほぼ非律速だった場合

FAILではない。

解釈:

> 現在の20 mm world・1 agent=1 cell・reference densityでは、海水由来C/N/P reservoirが生物量より十分大きい。

この場合、V1.10の価値は:
- abstract Matter removal
- elemental bookkeeping
- future niche axes

にある。

## 6.2 NまたはPが強く律速した場合

reference値を即調整しない。

- hydrothermal / ambient mixingのassumption
- world effective volume
- source/exchange timescale

を先に診断する。

## 6.3 final Nが5000 haltへ到達した場合

carrying capacityと呼ばない。

resource supplyとpopulation guardを区別して記録する。

---

# 7. Exp17で変更禁止

formal開始後は以下を結果に応じて変更しない:

- biomass C/N/P mass fractions
- reference C/N/P concentration
- exchange tau
- iLUCA genome
- H2 baseline
- growth Energy cost
- maintenance

変更が必要ならAttempt 1を保存し、人間判断でAttempt 2を別記録にする。

---

# 8. 成果物

各run:

```text
effective_config.json
initial_genome.json
summary.json
timeseries.csv
cnp_ledger.json
growth_limiter.csv
```

aggregate:

```text
phaseA_aggregate.csv
phaseB_aggregate.csv
Exp17_result_summary.md
```

preregistered gateはmissing artifact時に**FAIL**させる。silent SKIP禁止。

---

# 9. Exp17 close判断

V1.10をclose可能とする最低条件:

1. C/N/P ledgerが閉じる
2. 各C/N/Pを独立limiterとして作動させられる
3. reference iLUCAが少なくとも複数世代成立する、またはFAIL原因がresource systemとして説明可能
4. old generic Matter stockをformal V1.10では使用していない
5. growth limiterを記録できる
6. 過去V1.9 configs/testsを壊していない

ここまででV1.10の目的は達成。

C/N/Pの全球的最適濃度、early Earth chemistryの完全再現、carrying capacityの精密校正までは要求しない。