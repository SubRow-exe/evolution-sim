# Exp13 実験計画確定 — V1.8 一次Energy生態非対称

更新: 2026-09-03
状態: **人間方針確定 / 実装後そのまま実行可能**

目的:

> V1.8で導入する一次Energyの物理差が、
> **light = renewable / broad / low-average / day-night**
> **chemical = localized / stock / high-burst / depletable / competitive**
> という異なる生活条件を実際に作れているか確認し、必要な恒久パラメータを事前規則で選定する。

正本:
- `docs/V1.8_一次Energy生態非対称仕様.md`
- `docs/V1.8_実装チェックリスト.md`
- `docs/Exp12_結果考察.md`
- `docs/数値再現性・Actions実行環境方針.md`

---

# 1. Exp13で決めること / 決めないこと

## 決める

1. V1.8のlight day/night + density-dependent uptakeが成立するか
2. 現行 `light_max=1.2` でlight specialistが周期環境を成立できるか
3. 不成立時のlight peak最小救済値
4. chemicalの高burstを作る恒久 `chem_uptake`
5. chemical stockが消費で減り、密度競争が成立するか
6. V1.8を恒久defaultへできるか

## 決めない

- phototrophyの進化起源
- 初期LUCAのlight_absorption=0化
- cyanobacteria / chloroplast / plastid
- vent sourceの有限寿命
- 季節変動
- body_size再校正
- bmr_core再選定
- 「光型とchemical型のどちらが優れているか」という単一順位

これらはV1.9以降へ送る。

---

# 2. 全Phase共通

```text
bmr_core = 0.15
memory_tau = 10
response_gain = 64
primary_energy_density_response = True
light_cycle_enabled = True（light条件）
light_cycle_period_ticks = 200
light_day_fraction = 0.5
light_uptake_half = 0.6
chemical_uptake_half = 6.15
nutrient / reproduction / movement / damage等 = V1.7-final
```

light/chemicalの知覚response halfは変更しない:

```text
light_stimulus_half = 1.2
chemical_stimulus_half = 12.3
```

`max_population_halt=10000` を科学結果変更ではなく計算安全装置として使用する。

---

# 3. 実行前Phase 0

Exp12のような10k×2の重いpreflightを毎回行わない。

V1.8は科学コード変更を含むため、以下だけをHARD GATEとする。

```text
P0-1 全Config schema / round-trip / checker
P0-2 V1.8 unit tests
P0-3 conservation / Energy ledger
P0-4 同一current runner内 2,000 tick representative determinism ×2
P0-5 workflow directory E2E smoke
P0-6 runtime preflight
P0-7 CI Green
```

2,000 tick determinism代表条件:

```text
mixed light+chemical
seed=1
primary_energy_density_response=True
light_cycle_enabled=True
chem_uptake=2.0
```

同一current runner内でbit完全一致必須。

過去V1.7 Actions artifactとのbit一致は要求しない。科学コードが意図的に変わるため比較対象外。

---

# 4. Phase A — 生理・資源物理の校正

Phase Aは**進化OFF**。

目的はパラメータを進化結果から選ばないこと。

原則、全14遺伝子を固定する。

## phenotype

### Light specialist

```text
light_absorption = 2.0
chemical_absorption = 0.3
その他 = INITIAL_GENOME
全14遺伝子固定
```

### Chemical specialist

```text
light_absorption = 0.3
chemical_absorption = 2.0
その他 = INITIAL_GENOME
全14遺伝子固定
```

---

## A1. light cycle成立確認

### A1-main

```text
environment = light-only
light_pattern = vertical
light_max = 1.2
chem_vent_flux = 0
phenotype = light specialist
placement = random
seed = 1..5
ticks = 10,000
```

### A1-static control

同じ条件で:

```text
light_cycle_enabled = False
seed = 1..5
ticks = 10,000
```

目的:
- nightでlight gainが0になること
- daylightで再び供給されること
- cycleがEnergy予算・populationへ意味のある負荷を与えること
- 現行peak 1.2で完全絶滅しないこと

### A1 HARD criteria

`light_max=1.2`をそのまま採用する条件:

```text
COMPLETE >= 4/5
EXTINCT <= 1/5
POP_HALT = 0/5
night flow_light increment = exactly 0
light_supply_cum = effective light積算と一致
```

さらにstatic controlよりcycle条件で:
- 1 cycleあたりlight取得が低いこと
- night中にEnergyがlight由来で増えないこと

をsanity確認する。

population大小そのものには合否閾値を置かない。

### A1 rescue ladder

`1.2`でCOMPLETE <4/5なら、結果を見て自由に値を作らず事前登録済みの順に:

```text
light_max = 1.5
            1.8
            2.4
```

を各5 seedで試す。

**4/5以上成立する最小値**をV1.8候補とする。

2.4でも成立しなければ:

```text
LIGHT_CALIBRATION_FAIL / REVIEW
```

で停止し、chemical校正・正式Phase Bへ進まない。

---

## A2. chemical高burst値の選定

candidate:

```text
chem_uptake = 1.0, 2.0, 4.0
```

各candidateで2配置:

### vent placement

```text
environment = chemical-only
light_max = 0
chem_vent_flux = 16
phenotype = chemical specialist
diagnostic_placement = vent
seed = 1..5
ticks = 10,000
```

### random placement

同じだが:

```text
diagnostic_placement = random
seed = 1..5
ticks = 10,000
```

総run:

```text
3 candidate × 2 placement × 5 seed = 30 run
```

---

# 5. A2で使うEnergy取得指標

populationが変わるので単純なflow総量では比較しない。

stats intervalごとにorganism-timeを近似:

```text
org_ticks ~= ((N_prev + N_now) / 2) * delta_tick
route_gain_per_org_tick = delta_flow_route / org_ticks
```

population=0 intervalは除外。

### Light reference

A1 selected light条件について、`light_cycle_factor > 0` のdaylight intervalのみから:

```text
LIGHT_DAY_GAIN
= median(route_gain_per_org_tick)
```

をseedごとに求める。

### Chemical burst

vent placementの最初の1,000 tickから:

```text
CHEM_BURST_GAIN
= median(route_gain_per_org_tick)
```

をseedごとに求める。

ratio:

```text
BURST_RATIO = CHEM_BURST_GAIN / LIGHT_DAY_GAIN
```

---

# 6. A2 chemical選定規則

候補値は小さい順に評価する。

選定条件:

```text
A. vent placement COMPLETE >= 4/5
B. POP_HALT = 0/5
C. group median BURST_RATIO >= 2.0
D. 5 seed中4 seed以上で BURST_RATIO >= 1.5
E. chemical stockが生物不在平衡から明瞭にdepleteする
```

Eの定義:

標準vent生物不在stockを `C_eq` とし、vent cellsの環境snapshotから:

```text
min_median_vent_stock_0_2k <= 0.7 * C_eq
```

を5 seed中4 seed以上で満たす。

選定:

> A〜Eを満たす**最小 `chem_uptake`**。

1.0が満たせば1.0、そうでなければ2.0、次に4.0。

4.0でも満たさなければ:

```text
CHEMICAL_CALIBRATION_FAIL / REVIEW
```

とし、結果を見て5.0等を追加しない。

---

# 7. random placementは選定gateではなく生態診断

random placementは:
- 資源を見つけるまでの探索コスト
- vent placementとの差
- seed依存性

を見る。

比較:

```text
time_to_first_birth
starvation deaths
mean_move_per_org_tick
vent_cell_frac
chemical gain per org-tick
```

期待はvent placementの方が初期収益が良いことだが、**randomが必ず不利であることをV1.8採用HARD GATEにはしない**。

理由:
- V1.6 chemotaxis性能
- seedごとのvent配置
- 初期位置

も混ざるため。

---

# 8. A3 密度競争mechanism check

長期進化runではなく短いmechanism check。

selected `chem_uptake` を使い、同一vent cell付近の需要を増やしたとき:

```text
initial_population = 1, 10, 50
placement = vent
seed = 1..3
ticks = 2,000
```

9 run。

確認:

```text
population密度増加に伴い
per-capita chemical gainが低下すること

総chemical gainがstock/source制約を超えないこと
vent stockがより低くなること
```

方向性が逆なら実装または集計をレビューする。

lightについては同一cell供給の公平配分unit testで競争機構を確認し、A3相当の追加9 runは必須としない。

---

# 9. Phase A verdict

```text
A_PASS
LIGHT_CALIBRATION_FAIL / REVIEW
CHEMICAL_CALIBRATION_FAIL / REVIEW
INTEGRITY_FAIL
```

`A_PASS` のときのみPhase Bへ進む。

Phase A終了時点で:

```text
selected_light_max
selected_chem_uptake
```

を固定し、Phase B開始後に変更しない。

---

# 10. Phase B — 生態的成立確認

Phase Bではselected V1.8 parametersを固定する。

## B1 light-only specialist

```text
light-only
light specialist
全14遺伝子固定
random placement
seed=1..8
ticks=20,000
```

目的:
- 周期light環境で長期成立可能か
- nightを跨いだEnergy budget
- population / starvation / movement

## B2 chemical-only specialist

```text
chemical-only
chemical specialist
全14遺伝子固定
random placement
seed=1..8
ticks=20,000
```

目的:
- 局所stockを探索して長期成立できるか
- vent占有・depletion・competition
- seed依存性

B1/B2は「どちらが強いか」をpopulationだけで順位付けしない。

---

## B3 mixed-world exploratory evolution

```text
light + chemical both ON
initial genome = current generalist (light=0.3 / chemical=0.3)
進化ON = light_absorption, chemical_absorption の2遺伝子のみ
その他12遺伝子固定
bmr_core=0.15
seed=1..12
ticks=30,000
```

目的:

> 同一世界でlightとchemicalの両方に進化価値が残るか、資源利用戦略の分化兆候が現れるかを探索する。

観測:
- mean / variance light_absorption
- mean / variance chemical_absorption
- lineage別両遺伝子
- lineage別light/chemical Energy flow
- vent distance帯占有
- daylight/nightの活動
- top lineage share
- 2遺伝子散布図
- phenotype clustering（事後診断のみ）

### B3はV1.8採用のHARD GATEではない

B3で明確な二峰性・共存が出なくてもV1.8を失敗としない。

V1.8の主目的はsource物理の非対称性を作ること。

多様化・phototrophyの新規出現はV1.9以降で検証する。

---

# 11. V1.8採用判定

## `V1_8_ACCEPT`

以下を全て満たす:

```text
1. Phase 0全Green
2. A1 light calibration PASS
3. A2 chemical calibration PASS
4. A3 chemical competition direction PASS
5. B1 COMPLETE >= 6/8
6. B2 COMPLETE >= 6/8
7. conservation / integrity violation 0
```

## `V1_8_RECALIBRATE / REVIEW`

mechanism自体は正しいが:
- lightが全体的に成立しない
- chemical burstが事前候補内で不足
- B1/B2どちらかが5/8以下

の場合。

**Phase B結果を見て同じExp13内で新しい候補値を追加しない。**

## `V1_8_INVALID`

- Energy/Matter台帳破綻
- density responseが非単調
- nightにlight流入
- chemical stock以上を吸収
- Config/collector/integrity不整合

---

# 12. Exp13後の恒久default反映

`V1_8_ACCEPT` の場合、別commitで:

```text
bmr_core = 0.15
primary_energy_density_response = True
light_cycle_enabled = True
light_cycle_period_ticks = 200
light_day_fraction = 0.5
light_uptake_half = 0.6
chemical_uptake_half = 6.15
light_max = selected_light_max
chem_uptake = selected_chem_uptake
```

へ確定する。

そのcommitで:
1. full tests
2. conservation
3. determinism
4. CI Green
5. V1.8 CI基準ref更新
6. `v1.8-final` branch保存

を行う。

---

# 13. 必須成果物

```text
exp13_runs.csv
exp13_phaseA_light.csv
exp13_phaseA_chemical.csv
exp13_density_competition.csv
exp13_phaseB_summary.csv
exp13_mixed_lineages.csv
SCIENTIFIC_VERDICT.txt
NOTES.md
```

plot:
- light cycle factor / light flow / population / Energy
- static vs cycle light comparison
- chemical burst ratio by candidate
- vent stock trajectory
- chemical density vs per-capita gain
- B1/B2 population and route flow
- B3 light_absorption vs chemical_absorption trajectory/scatter

---

# 14. 実行時間

Phase A / B実行前に既存performance.csvと短期preflightから見積もる。

必ず:

```text
single-run predicted max
matrix total run count
max-parallel
matrix wall-clock estimate
```

を分ける。

新しい時間計測instrumentationは不要。既存Actions timestamps / performance.csv / done logを使用する。

formal終了後に予測と実績をNOTESへ記録する。

---

# 15. Claudeへの実行順

Claudeは次の順を変更しない。

```text
0. V1.7 bmr_core=0.15確定・v1.7-final保存
1. V1.8実装
2. V1.8実装チェックリスト全項目
3. local full tests
4. CI Green
5. Exp13 Phase 0
6. A1 light calibration
7. A2 chemical calibration
8. A3 density check
9. Phase A verdict
10. A_PASSならselected parameters固定
11. B1/B2
12. B3 exploratory
13. collect / integrity
14. V1.8 verdict
15. ACCEPTなら恒久default反映
16. tests / CI
17. v1.8-final保存
18. 結果・考察をGitHubへ記録
```

途中で科学条件・候補値・閾値を独自変更しない。
