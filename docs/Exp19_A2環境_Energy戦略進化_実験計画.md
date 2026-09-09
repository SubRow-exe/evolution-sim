# Exp19 — A2 vent turnover環境におけるEnergy戦略3形質の進化検証

更新: 2026-09-09  
状態: **PREREGISTRATION / Claude実装・実行待ち**

## 0. 背景

Exp18ではV1.10.1のfinite-flux H2 vent機構を検証し、以下を確認した。

- finite-flux source自体は数値・ledger上成立する
- A0 static finite-flux環境ではiLUCAは安定して生存・増殖する
- A1（6 h ON / 6 h OFF）は3/3絶滅し、現在のiLUCAには時間変動が強すぎる
- A2（48 hごとに1 ventをrelocate）は3/3生存し、強いpopulation contractionを起こしながら6–9世代まで到達した
- A3（temporal + turnover）はPhase Aで2/3生存したが、Phase Bの別seed集合ではFIXED/EVOLVEとも5/5早期絶滅し、進化を観察するworking environmentとしては強すぎた
- Exp18 Phase B static側は20日runで個体数が大きく維持され、GitHub-hosted runnerの実行時間上限に到達してformal comparisonを完了できなかった

Exp18結果考察の正本:

- `docs/Exp18_V1.10.1_動的熱水噴出口_結果考察.md`

このためExp19では、H2環境条件そのものの再調整は行わず、**A2をdynamic working environmentとして固定**し、V1.9で導入したEnergy戦略3形質に異なる選択圧が生じるかを短期で確認する。

---

# 1. 目的

Exp19の主目的は:

> **H2 vent位置が48 hごとに変わるA2環境が、static環境とは異なるEnergy戦略3形質の進化応答を生むかを確認する。**

ここで見る3形質は:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

Exp19は長期進化の最終結論を出す実験ではない。

目的は、現在のGitHub Actions環境で6 h以内に完了可能な範囲で:

1. A2環境で進化を観察できること
2. FIXEDとEVOLVEで生態応答に差が出るか
3. 3形質に方向性のある変化が出るか
4. その変化がstaticでも起きる一般的応答か、A2に特有か

を確認することである。

---

# 2. Version / scope

Exp19は**V1.10.1内の追加実験**として扱う。

新しい生理・代謝・環境法則は追加しない。

変更するのはformal experiment harness / diagnostic / workflowのみ。

V1.10 / V1.10.1で確定した以下は変更しない:

```text
H2 uptake kinetics
Energy physiology
C/N/P stoichiometry
finite-flux H2 source
vent count
vent flux F0
H2 diffusion
H2 loss tau
initial iLUCA baseline
```

---

# 3. Exp19実行前の必須修正

Exp18で発見したH2 diagnosticの単位換算ミスを修正する。

現在:

```python
H2_HABITABILITY_MOLM3 = 248e-6
```

これは248 µMをmol/m3へ変換するとき1000倍小さい。

正しくは:

```text
248 µM
= 248e-6 mol/L
= 0.248 mol/m3
```

したがって:

```python
H2_HABITABILITY_MOLM3 = 0.248
```

へ修正する。

このdiagnosticはExp18の生理計算・生死判定・H2 uptakeには使われていないため、Exp18本体の結果を無効化しない。

Claudeは修正後、最低限のunit testを追加して、0.248 mol/m3が248 µMとして扱われることを確認すること。

---

# 4. 共通baseline

Exp18/V1.10.1確定値をそのまま使用する。

```text
physical_mode = True
dt = 10 s
world = 20 mm x 20 mm
grid = 40 x 40
cell size = 0.5 mm
initial population = 100
vent count = 4
phototrophy = OFF
predation = OFF
```

H2:

```text
source mode = finite flux
F0 = 4.890000722073717e-11 mol/s / vent
H2 diffusion = 5e-9 m2/s
H2 exchange/loss tau = 900 s
```

C/N/P:

```text
50 biomass-equivalents
background exchange = OFF
```

H2のinitial fieldはExp18と同じcalibration方法を再利用する。

F0を再チューニングしない。

---

# 5. 実験デザイン

## 5.1 2 × 2 design

```text
Environment: STATIC / A2_DYNAMIC
Genetics:    FIXED  / EVOLVE
```

4 arms:

### E0 STATIC-FIXED

```text
4 vents
位置固定
各vent flux = F0
3 Energy戦略形質固定
```

### E1 STATIC-EVOLVE

```text
環境はE0と同じ
storage_capacity / starvation_horizon / reproduction_horizonのみ進化ON
```

### E2 A2_DYNAMIC-FIXED

```text
4 vents常時ON
各vent flux = F0
48 hごとに4 ventsのうち1 ventをrelocate
vent countは常に4
3 Energy戦略形質固定
```

### E3 A2_DYNAMIC-EVOLVE

```text
環境はE2と同じ
storage_capacity / starvation_horizon / reproduction_horizonのみ進化ON
```

---

# 6. Run数 / seed / duration

計算時間制約を考慮し:

```text
3 seeds x 4 arms x 10 physical days
seeds = 19001, 19002, 19003
```

同一seedを4 armsで対応させる。

総run数:

```text
12 runs
```

### 10日にする理由

Exp18ではA0 staticの10日runはGitHub Actions上で十分完走できた。

A2も10日で6–9世代まで到達したため、短期の選択圧検出には利用可能と判断する。

一方、Exp18 Phase Bの20日static runでは個体数が数千規模で長期間維持され、GitHub-hosted runnerの実行時間制約に達した。

Exp19では**formal scientific questionを保ったまま、現在の計算基盤で完走可能性を優先する**。

---

# 7. 進化対象

進化ON arm（E1/E3）で変異可能にするのは以下のみ:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

その他continuous genesは固定。

initial jitter:

```text
initial_jitter_sigma = 0.02
```

これはExp15 / Exp18 evolution armと同orderを維持する。

Exp19結果を見てjitterやmutation幅を変更しない。

---

# 8. 3形質の意味

## storage_capacity

Energyをどれだけ蓄えられるか。

A2ではvent移動によって現在利用しているH2 sourceが失われる可能性があるため、H2が豊富な時点でより多く貯蔵する戦略に価値が生じる可能性がある。

ただし増加を事前のPASS条件にはしない。

## starvation_horizon

将来のEnergy不足をどの程度先まで見越して節約状態へ入るか。

vent移動後のH2不足への対応に影響する可能性がある。

## reproduction_horizon

Energy余裕をどの程度見越して繁殖判断するか。

「早く繁殖する」戦略と「蓄えてから繁殖する」戦略のtrade-offにA2環境が影響する可能性がある。

---

# 9. 主要readout

## 9.1 生態

各runで最低限:

```text
survival / extinction time
population N(t)
final population
max population
population AUC
births / deaths
starvation deaths
max generation
generation interval
starvation-active fraction
mean runway
mean local H2
H2 >= 248 µM occupancy fraction
H2 habitability fraction of world
mean distance to nearest active vent
vent turnover count
H2 source/loss/biological uptake ledger
C/N/P ledger
```

## 9.2 進化

3形質について:

```text
initial mean / median / q10 / q90
final mean / median / q10 / q90
last 20% window mean / median
initial -> final shift
initial -> last20% shift
seedごとの変化方向
```

可能なら、最終populationだけではなくtime seriesとして保存する。

---

# 10. 主要比較

## Comparison A: E2 vs E3

最重要比較。

同じA2環境で:

```text
E2 = 進化不可
E3 = 3形質進化可
```

を比較する。

確認したいこと:

- E3で生存率が改善するか
- population AUCが増えるか
- starvation deathが減るか
- max generationが深くなるか
- 3形質に方向性のある変化が現れるか

E3がE2を必ず改善することをPASS条件にはしない。

## Comparison B: E1 vs E3

進化ON同士でstaticとA2を比較する。

目的:

> 3形質の変化が単なる一般的な進化ドリフト/選択なのか、A2環境特有なのかを区別する。

例:

```text
E1: storage_capacityほぼ不変
E3: 3/3 seedsでstorage_capacity増加
```

であれば、A2環境によりstorage側へ追加の選択圧がかかった可能性が高い。

## Comparison C: E0 vs E1

static環境における3形質のbaseline evolutionを確認する。

---

# 11. 判定方針

Exp19では特定形質の方向をPASS/FAILとして事前固定しない。

たとえば:

```text
storage_capacity +10%以上でPASS
```

のような閾値は置かない。

Exp19の目的はmechanistic calibrationではなく、**選択圧の有無と方向性の探索**である。

以下が確認できればExp19として十分:

1. A2環境で複数世代の進化観察が成立する
2. E2 / E3で生態応答の差を評価できる
3. 3形質の少なくとも一部にseed間で方向性を評価できる程度の変化がある、または変化がないことを正式結果として記録できる
4. E1 / E3比較によりstaticとA2の違いを評価できる

3 seed / 10日は最終進化結論ではなく、**次の長期計算環境構築前の短期選択圧確認**として扱う。

---

# 12. Integrity / 変更禁止

formal開始後、結果を見て以下を変更しない:

```text
F0
vent count = 4
48 h turnover interval
H2 diffusion / loss tau
C/N/P 50 equivalents
C/N/P exchange OFF
iLUCA physiology
進化対象3 genes
initial jitter sigma = 0.02
run duration = 10 days
seeds = 19001-19003
```

変更が必要になった場合はExp19 Attempt 1を保存し、Attempt 2として別途明示する。

---

# 13. Claude向け実装指示

既存Exp18 harnessを最大限再利用すること。

推奨:

```text
experiments/exp19_v1101_a2_energy_evolution/
```

を新規作成し、Exp18の:

```text
exp18_core.py
run_exp18_phase_b.py
aggregate_phase_b.py
```

のロジックを再利用または明示的にimportする。

ただしExp18のformal artifact / preregistrationを上書きしない。

### 必須実装

1. 248 µM diagnosticを0.248 mol/m3へ修正
2. diagnostic回帰test追加
3. E0/E1/E2/E3 arm定義
4. dynamic conditionはA2固定
5. 19001–19003の3 seed
6. 10 physical days
7. Phase Aの再実行は不要
8. Exp18のA3 selection ruleをExp19で再利用しない
9. aggregateで4 armsを機械的に比較可能にする
10. missing/incomplete artifactをsilent skipしない

### Actions

formal workflowはExp19専用ファイルを作ること。

例:

```text
.github/workflows/exp19_v1101_a2_energy_evolution.yml
```

1 jobあたりのtimeoutはGitHub-hosted runner実制約を考慮し、**360 minを超えることを前提にしない**。

`max-parallel`は12 runを同時に走らせすぎてresource/queue面で不安定にならない範囲で設定する。Exp18実績から6程度を第一候補とする。

### Artifact軽量化

Exp19の目的に不要な高頻度snapshotは削減してよい。

ただし以下は必ず残す:

```text
effective_config.json
initial_genome.json
vent_schedule.json
timeseries.csv
summary.json
H2/C/N/P ledgers
3 gene time-series/statistics
```

snapshotを削る場合も、進化形質のtime-series集計に必要な情報は失わないこと。

---

# 14. Exp19終了後

Exp19でA2環境における短期進化応答を確認したら、H2 vent仕様の校正は一旦終了する。

長期計算基盤が整うまでは、結果に応じて追加の短時間実験を行うことは認めるが、vent cycle / F0 / turnover intervalの細かな最適化は行わない。

長期環境構築後に必要であれば、Exp19と同じ2×2 designをより長期間・多seedで再検証する。
