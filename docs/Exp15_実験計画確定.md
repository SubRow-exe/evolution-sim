# Exp15 実験計画確定 — V1.8新機構切り分け + coarse light working reference

更新: 2026-09-04
状態: **人間方針確定 / Sonnet実装可能 / formal実行前**

最優先関連:
1. `docs/Exp14_表現型プロベナンス訂正.md`
2. `docs/環境因子追加・校正方針.md`
3. `docs/V1.8_現状総括_Exp14結果.md`
4. `docs/V1.8_一次Energy生態非対称仕様.md`
5. `docs/Exp15_実装チェックリスト.md`
6. `AGENTS.md`

Exp13/Exp14は再dispatchしない。

---

# 1. 背景

V1.8ではV1.7から一次Energy収支へ主に2機構を同時導入した。

```text
A. day/night cycle
B. primary-energy density response H(x,K)=x/(x+K)
```

Exp13/Exp14ではlight-onlyが成立しなかった。
Exp14からnight/storage/tick1繁殖が負荷になる兆候は得たが、`docs/Exp14_表現型プロベナンス訂正.md`の通りExp14 formalは意図したlight specialistではなくINITIAL_GENOME (`light_absorption=.3`) で走っていた。

したがってExp15では、**正しい固定light specialistを使って2新機構を一つずつ切り分ける。**

その後、combined V1.8で`light_max`だけを粗く振り、厳密な相転移点ではなくknife-edgeでないworking referenceを探す。

---

# 2. Exp15で答える問い

## Phase A — mechanism isolation

> 既知のV1.7 light scaleで、density response単独・day/night単独・combinedがEnergy収支と継続世代交代へどの程度影響するか。

## Phase B — coarse working-reference search

> 2機構を両方ONにしたV1.8 worldで、`light_max`を粗く増やしたとき、複数世代が継続できる非knife-edgeな成立域があるか。

Exp15は以下を目的にしない。

- 唯一の最適`light_max`
- 正確な絶滅/生存相転移点
- `light_uptake_half`との多軸最適化
- period/capacity/reproductionの同時最適化
- V1.8全体final acceptance

---

# 3. 全Phase共通の科学条件

light-only固定表現型診断とする。

```text
light specialist:
  light_absorption = 2.0
  chemical_absorption = 0.3
  その他 = INITIAL_GENOME

fixed_genes = canonical GENE_NAMES 全14遺伝子
initial_population = 100
initial_energy = 50
initial_matter = 0.8
placement = random
light_pattern = vertical
chem_vent_flux = 0.0
bmr_core = 0.15
memory_tau = 10.0
response_gain = 64.0
light_uptake_coef = 2.0
light_uptake_half = 0.6
energy_capacity = 100.0
repro_energy_frac = 0.6
light_cycle_period_ticks = 200
light_day_fraction = 0.5
stats_interval = 20
snapshot_interval = 1000
max_population_halt = 10000
```

`light_uptake_half=0.6`はExp15では固定する。
`energy_capacity`、period、day_fraction、初期Energy、繁殖条件も固定する。

**Phase Aではfeature flag以外を変えない。Phase Bではlight_max以外を変えない。**

---

# 4. 表現型HARD GATE

Exp14再発防止としてformal前に必ずE2E確認する。

全Exp15 Configについて:

```text
fixed_genes = GENE_NAMESの14遺伝子と完全一致
diagnostic_gene_overrides = {
  "light_absorption": 2.0,
  "chemical_absorption": 0.3
}
```

さらにConfig検査だけで終えない。

`Simulation(cfg, seed=1)`を実際に初期化し、初期100個体全てについて:

```text
light_absorption == 2.0
chemical_absorption == 0.3
```

をassertする。

1個体でも不一致なら**TECHNICAL FAIL / formal禁止**。

---

# 5. Phase A — 2×2 mechanism isolation

比較軸をV1.7のhistorical light scaleへ揃える。

共通:

```text
light_max = 1.2
seed = 1..5
ticks = 5,000
```

条件:

| arm | cycle | density response | 意味 |
|---|---|---|---|
| A0 | OFF | OFF | V1.7型static-light機構control |
| A1 | OFF | ON | density response単独 |
| A2 | ON | OFF | day/night単独 |
| A3 | ON | ON | V1.8 combined |
| A4 | OFF | OFF | technical duplicate sentinel |

A4はA0と**同一Config / 同一seed系列を別run keyで再実行**する。科学比較armではなく、Actions実行・collector・determinismのsentinelとする。

### A4の理由

Exp14で「計画と実行表現型の不一致」が起きたため、Exp15では科学条件を増やすより、formal成果物そのものが同一条件で再現されることを1本の独立sentinelで確認する。

A0とA4はseedごとに主要科学列が一致しなければTECHNICAL REVIEWとする。

Phase A formal run数:

```text
5 arms ×5 seeds = 25 runs
nominal ticks = 125,000
```

---

# 6. Phase A判定

各科学arm A0-A3をseed単位で:

```text
REACHED_TARGET:
  target tick=5,000へ到達し final population > 0

EXTINCT:
  target前にpopulation=0

OVERDRIVEN:
  max_population_haltへ到達して停止
```

arm分類:

```text
ROBUST_SHORT:
  5/5 seed REACHED_TARGET

MIXED:
  3-4/5 seed REACHED_TARGET

COLLAPSE:
  0-2/5 seed REACHED_TARGET

OVERDRIVEN:
  1 seed以上がmax_population_halt
```

Phase Aは「平衡」を判定しない。

### Phase A科学HARD GATE

A0が`ROBUST_SHORT`または`OVERDRIVEN`でなければ:

```text
SCIENTIFIC_STOP = BASELINE_NOT_VIABLE
```

とする。

これは「V1.8 featureが悪い」という切り分けの前提が成立しないため。
Phase Bを自動実行しない。

A0が成立した場合、以下を主因果解釈とする。

```text
A1のみ大幅悪化 -> density response寄与が大きい
A2のみ大幅悪化 -> day/night寄与が大きい
A1/A2単独は成立、A3のみ崩壊 -> interaction/synergyが大きい
A1/A2とも悪化、A3さらに悪化 -> 両方が独立+複合で寄与
```

「大幅」は二値分類だけでなく、連続量も併記して人間判断する。

---

# 7. Phase A必須観測量

run単位:

```text
survival / extinction tick / halt reason
population trajectory
births_cum / deaths_cum / deaths_starvation
max_generation
first tick reaching generation 1 / 2 / 3 / 5
Energy/capacity mean / median / p10 / p90
light gain per organism-tick
maintenance+movement cost per organism-tick
repair cost per organism-tick
birth overhead per organism-tick
core net Energy per organism-tick
sunset/dawn population
sunset/dawn Energy/capacity
night minimum / preceding daytime peak
```

ここで:

```text
organism_tick = 各stepで生理処理対象となった生存個体数の累積

core_net_E_per_org_tick
  = (light_gain
     - maintenance_and_movement_cost
     - repair_cost
     - birth_overhead) / organism_ticks
```

とする。

これは全Energy ledgerを置換するfitness値ではない。
一次Energyで日常維持と繁殖overheadを賄えているかを見る**診断量**に限定し、simulationへフィードバックしない。

---

# 8. density responseの観測

Phase A1/A3およびPhase Bでは、実際に生物が経験したlight density responseを観測する。

対象event:

```text
- daylight factor > 0
- local effective light I > 0
- light_absorption > ABILITY_EPS
```

各eventで:

```text
H = I/(I + light_uptake_half)
```

を読み取り専用集計し:

```text
light_H_events
light_H_mean
light_H_p10 / median / p90
light_H_frac_lt_0p05
light_H_frac_gt_0p95
```

を保存する。

nightの`I=0`をH分布へ混ぜない。
そうしないとday/nightによる0とdensity-responseによる抑制を混同するため。

---

# 9. Phase B — coarse light_max search

Phase Bは**Phase A結果後に人間が別dispatchで開始する**。
Phase A成功からPhase Bへworkflow内で自動遷移してはいけない。

combined固定:

```text
light_cycle_enabled = True
primary_energy_density_response = True
period = 200
day_fraction = 0.5
light_uptake_half = 0.6
energy_capacity = 100
```

唯一のsweep軸:

```text
light_max = 1.2, 2.4, 4.0, 6.0, 8.0, 12.0
seed = 1..3
ticks = 10,000
```

formal run数:

```text
6 levels ×3 seeds = 18 runs
nominal ticks = 180,000
```

Phase A+B最大:

```text
43 formal runs
305,000 nominal ticks
```

途中結果を見て同一Exp15へlight_max水準を追加しない。

---

# 10. Phase B分類

seed単位:

```text
VIABLE_SEED:
  10,000 tick到達
  final population > 0
  max_generation >= 5
  max_population_haltなし

EXTINCT_SEED:
  target前に絶滅

OVERDRIVEN_SEED:
  max_population_halt

LOW_GENERATION_SEED:
  10k生存するがmax_generation < 5
```

light_max水準:

```text
VIABLE_LEVEL:
  3/3 seedがVIABLE_SEED

MIXED_LEVEL:
  1-2/3 seedがVIABLE_SEED
  かつOVERDRIVENなし

COLLAPSE_LEVEL:
  0/3 VIABLE_SEEDで、主に絶滅/低generation

OVERDRIVEN_LEVEL:
  1 seed以上がOVERDRIVEN_SEED
```

`max_generation>=5`は自然界の基準ではない。
「初期個体が一度繁殖して終わる」状態をworking referenceとして採用しないための最低限の工学sentinelである。

---

# 11. working reference選定規則

厳密thresholdを探さない。

`light_max`昇順で見て、**隣接するtested levelが2つ連続でVIABLE_LEVEL**となる最初のpairを探す。

例:

```text
4.0 = VIABLE
6.0 = VIABLE
```

ならworking reference候補は:

```text
selected_light_max = 4.0
```

とする。

理由:
- 最小限の外部供給側を採る
- 1点だけの偶然成立を避ける
- 正確な相転移点は追わない

### 選定しない条件

```text
- VIABLE_LEVELが0個
- VIABLE_LEVELが1個だけ
- VIABLE_LEVEL同士が隣接しない
- lower側はcollapse、唯一の高light条件だけviable
- viable候補がOVERDRIVENと隣接し、成立域が明らかにknife-edge
```

この場合:

```text
SCIENTIFIC_VERDICT = NO_ROBUST_LIGHT_REFERENCE
```

とし、Exp15内でperiod/capacity/Kを追加sweepしない。

次の実験で初めて:
- period
- energy_capacity

のどちらを粗調整するか人間判断する。

---

# 12. featureが意味を残しているか

selected候補について、次を**診断として**併記する。

## density response

late window（tick 2,000-10,000）でlight Hを確認する。

```text
ほぼ全event H<0.05 -> responseが強すぎる可能性
ほぼ全event H>0.95 -> responseが事実上飽和している可能性
```

目安として95%超をflagするが、これだけで自動rejectしない。
人間がworking referenceとして妥当か判断する材料とする。

## day/night

complete cycleごとに:

```text
sunset Energy/capacity
next dawn Energy/capacity
```

を比較し、nightでreserveが実際に減るかを報告する。

night supplyは仕様上exact 0であることをcheckerで確認する。

これも特定のeffect-size閾値を事前に置かない。

---

# 13. late window

Phase B late window:

```text
2,000 <= tick <= 10,000
```

そのrunがtick 2,000へ到達しない場合、late指標は`N/A`。
N/AをPASS/FAIL分母へ混ぜない。

Phase Aは短期mechanism診断なのでlate平衡判定をしない。

---

# 14. 技術FAILと科学STOP

## TECHNICAL FAIL

例:
- Config生成不一致
- initial phenotype E2E不一致
- artifact欠落
- seed/run key重複
- conservation/determinism regression
- NaN/invalid Config
- collectorが予定runを回収できない
- A0/A4 duplicate sentinelが同seedで再現しない

## SCIENTIFIC STOP / REVIEW

例:
- A0 baselineが成立しない
- A3 combinedがcollapseする
- Phase Bにrobust viable pairがない
- 全条件がoverdriven

科学的に期待外れでもtechnical successならartifactとsummaryを保存する。

---

# 15. runtime / Actions方針

workflow input:

```text
mode = preflight | phase_a | phase_b
```

構造上:

```text
preflight -> 終了
phase_a   -> Phase Aだけ実行・collect・summaryして終了
phase_b   -> Phase Bだけ実行・collect・summaryして終了
```

`needs`や`if`でPhase A成功からPhase Bを自動開始する構造は禁止。

preflightでrepresentative benchmarkを取り:

```text
- Phase A 5k代表
- Phase B 10k combined代表
- max-parallel
- wave数
- setup/collect overhead
- safety factor
- phase別全体wall-clock予測
```

を`exp15_runtime_report.json`へ保存する。

予測が10時間を超えるPhaseはformal開始前に停止し、人間へ報告する。
条件/seed/ticksをSonnet判断で削らない。

---

# 16. 成果物

## raw

Actions artifact:

```text
exp15-phase-a-raw-*
exp15-phase-a-collected
exp15-phase-b-raw-*
exp15-phase-b-collected
```

## aggregate

GitHubへ残す:

```text
exp15_phase_a_summary.csv/json/md
exp15_phase_b_summary.csv/json/md
exp15_runtime_report.json
exp15_selected_light.json   # 選定成立時のみ
plots/
```

`exp15_selected_light.json`例:

```json
{
  "status": "SELECTED",
  "light_max": 4.0,
  "light_uptake_half": 0.6,
  "light_cycle_enabled": true,
  "primary_energy_density_response": true,
  "light_cycle_period_ticks": 200,
  "light_day_fraction": 0.5,
  "energy_capacity": 100.0,
  "selection_rule": "lowest level in first adjacent VIABLE_LEVEL pair"
}
```

値は実測前に書き込まない。

---

# 17. Exp15後

selected light working referenceが得られた場合も、直ちにV1.8 finalとはしない。

次:

```text
chemical暫定候補の長期validation
-> light-only長期viability
-> chemical-only長期viability
-> mixed evolution validation
-> V1.8 ACCEPT
-> v1.8-final
```

selected値は自然界の普遍定数ではなく、今後の多環境化で再調整可能なworking referenceとする。
