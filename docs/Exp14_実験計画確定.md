# Exp14 実験計画確定 — light昼夜絶滅mechanism / R-map / evolutionary rescue

更新: 2026-09-03
状態: **レビュー反映後確定 / 実装・実行前**

関連:
- `docs/Exp14_レビュー判断.md` — **Opus 5レビューの人間採否。最優先**
- `docs/Exp13_結果考察_中間.md`
- `docs/V1.8_一次Energy生態非対称仕様.md`
- `docs/Exp13_実験計画確定.md` — Exp13事前登録履歴。結果後に書き換えない

---

# 1. 背景

Exp13 Phase A1では:

```text
light_max = 0.8〜4.0
8水準 ×5 seed
```

がすべて10k前に絶滅した。

`light_max=4.0`では典型的に:

```text
initial 100
-> 最初の昼に440〜503
-> 最初の夜明けに8〜16
-> 次の昼に再繁殖
-> 次の夜に再崩壊
-> starvation extinction
```

となった。

追加の式検算から、単純なlight総量より:

```text
夜の長さ
vs
夜前Energy reserve / 夜間消費
```

の時間スケール不整合が主要因と考えられる。

現行条件では繁殖が余剰Energyを親子へ分配するため、lightを増やしても日没前reserveが十分深くならず、昼のboomが夜のcollapseへつながる。

Exp14はこの機構を検証し、その周辺の成立境界と自然適応可能性まで調べる。

---

# 2. Exp14の問い

Exp14は3段階で問う。

## Phase A — mechanism diagnostic

> Exp13のboom-bustは、夜長 / reserve / 繁殖 / 初期一斉繁殖で説明できるか。

## Phase B — R boundary map

> `light_cycle_period_ticks` と `energy_capacity` を振ったとき、固定表現型の成立/崩壊境界はR_refで整理できるか。

## Phase C — evolutionary rescue probe

> 人間が世界定数を変更しなくても、既存の進化可能形質だけで昼夜世界へ適応できる兆候が出るか。

Exp14ではworking `light_max`、恒久`energy_capacity`、恒久cycle periodを確定しない。

---

# 3. R_ref

主要診断量:

```text
R_ref = night_length_ticks / night_survival_ticks(reference reserve)
```

`night_survival_ticks`は、現行実装の:
- BMR
- organ upkeep
- sensing/membrane/resistance upkeep
- movement
- damage/repair

をそのまま用いた決定論計算で求める。

Phase A固定表現型では、そのarmのreference adultについてrun前にR_refを計算し、manifest/reportへ保存する。

R_refは普遍的なfitness式ではない。

目的は:

> arm間の崩壊/存続がR_refの順序で一貫して説明できるか

を検証すること。

---

# 4. Phase A 共通baseline

Exp13 A1 light specialistを使用。

```text
light_absorption = 2.0
chemical_absorption = 0.3
その他 = INITIAL_GENOME
全14遺伝子固定
initial_population = 100
initial_energy = 50
initial_matter = 0.8
placement = random
light_pattern = vertical
chemical = OFF
primary_energy_density_response = True

light_cycle_enabled = True
light_cycle_period_ticks = 200
light_day_fraction = 0.5
light_max = 4.0
repro_energy_frac = 0.6
energy_capacity = 100
```

```text
seed = 1..3
ticks = 2,000
```

---

# 5. Phase A conditions

## A0 — Exp13 baseline再現

baselineそのまま。

事前予測:
- COLLAPSE
- boom-bust再現

## A1 — 同じ時間平均供給、連続夜を除去

```text
light_cycle_enabled = False
light_max = 4/pi = 1.2732395447
```

供給fluxの時間平均をほぼ維持し、完全暗期だけ除去する。

注意:
`H(I,K)`は非線形なので、1個体あたり実効吸収まで完全一致するわけではない。realized H / uptakeを併記する。

事前予測:
- R_ref -> 0
- SURVIVES_SHORT方向

## A2 — 昼夜周期を短縮

```text
period = 80
light_day_fraction = 0.5
light_max = 4.0
```

40 tick昼 / 40 tick夜。

事前予測:
- R_ref大幅低下
- SURVIVES_SHORT方向

## A3 — light総量だけ増加

```text
period = 200
light_max = 8.0
repro_energy_frac = 0.6
energy_capacity = 100
```

事前予測:
- R_refはほぼ不変
- 昼のpeak populationは増えても夜collapseは根本改善しない

**A3が明確にSURVIVES_SHORTへ転じた場合、R単独仮説の重要な反証とする。**

## A4 — 繁殖Energy閾値を上げる

```text
repro_energy_frac = 0.8
```

夜長・light・capacityはbaseline。

目的:
- reserveをより深く保持してから繁殖する効果を見る

ただし初期tick1一斉繁殖も消えるため、A5で分離する。

事前予測:
- R_ref低下
- SURVIVES_SHORT方向

## A5 — initial-condition control

```text
repro_energy_frac = 0.6
initial_energy = 40
```

その他baseline。

初期繁殖閾値を下回らせ、tick1一斉繁殖だけを抑える。

解釈:
- A5がA0同様COLLAPSE -> 初期一斉繁殖は副次的、定常mechanismが主要
- A5がSURVIVES_SHORT -> initial condition寄与が大きい
- extinction tickだけ延長 -> 初期条件は寄与するが根本原因ではない

## A6 — Energy storage capacity diagnostic

```text
energy_capacity = 200
initial_energy = 100
```

その他baseline。

baselineと初期 `E/Emax` を揃えるため、capacityとinitial_energyを同倍率で変更する。

これによりtick1繁殖可能という初期状態もbaselineと同型に保ち、主に貯蔵容量スケールの効果を見る。

事前予測:
- R_ref低下
- SURVIVES_SHORT方向

A6は恒久default変更ではない。

---

# 6. Phase A run数 / 判定

```text
7 conditions ×3 seeds ×2,000 tick
= 21 formal runs
```

短期分類:

```text
SURVIVES_SHORT:
  3/3 seedが2,000 tick到達かつfinal population > 0

MARGINAL:
  2/3 seedが2,000 tick到達

COLLAPSE:
  0〜1/3 seedが2,000 tick到達
```

`SURVIVES_SHORT`は長期平衡を意味しない。

必ず連続量も保存:
- extinction tick
- survived nights
- sunset/dawn population
- daylight births
- darkness starvation deaths
- daytime peak
- night minimum
- night_min / preceding_day_peak
- per-organism Energy
- Energy/capacity mean, median, p10, p90

---

# 7. Phase B — period × energy_capacity boundary map

Phase Aだけで終えると、原因は分かっても次のparameter選定に必要な成立領域が分からない。

約10時間の計算枠を使い、固定表現型で境界地図を作る。

## 7.1 grid

```text
light_cycle_period_ticks = 80, 120, 160, 200, 240
energy_capacity          = 75, 100, 125, 150, 200
```

```text
5 ×5 = 25 cells
seed = 1..3
= 75 formal runs
```

共通:

```text
light_max = 4.0
light_day_fraction = 0.5
repro_energy_frac = 0.6
initial_matter = 0.8
全遺伝子固定
```

`energy_capacity`変更時は初期充填率をbaselineと揃える:

```text
initial_energy = 0.5 × energy_capacity
```

baselineでは `50 = 0.5×100`。

これにより初期:

```text
E / Emax(initial matter=.8) = 0.625
```

を全gridで維持し、initial conditionをcapacityへ交絡させない。

## 7.2 目的

各cellについて:
- R_ref
- survival class
- extinction tick
- night_min/day_peak
- reserve distribution

を取得し、成立/崩壊境界がR_refでcollapseするかを見る。

Exp14ではこのmapから恒久値を自動選定しない。

出力は:

```text
ROBUST SURVIVAL REGION
TRANSITION REGION
COLLAPSE REGION
```

の地図化まで。

---

# 8. Phase C — evolutionary rescue probe

ユーザー方針上、最も重要なのは:

> 初期個体を人間が環境へ合わせて救済するのではなく、自然選択で耐えられる個体が出るか

である。

そこで世界定数はExp13 baselineのままにし、既存遺伝子だけを解放する。

共通:

```text
period = 200
light_day_fraction = 0.5
light_max = 4.0
energy_capacity = 100
repro_energy_frac = 0.6
initial_energy = 50
initial_matter = 0.8
chemical = OFF
```

## C1 — body_size only

mutable:
```text
body_size
```

その他13遺伝子固定。

問い:
- Energy capacityを増やせる大型化方向へ選択されるか
- boom-bustを脱出できるか

## C2 — reproduction_investment only

mutable:
```text
reproduction_investment
```

問い:
- 親子へのEnergy分配戦略の変化だけで夜越しが改善するか

## C3 — movement_power only

mutable:
```text
movement_power
```

問い:
- 夜もwanderする現行世界で、移動コスト低下方向が選択されるか

夜専用の休眠ruleは追加しない。

## C4 — combined relevant traits

mutable:
```text
body_size
reproduction_investment
movement_power
```

問い:
- 3つの既存進化軸を組み合わせれば自然な適応経路が成立するか

## Phase C run数

```text
4 arms ×5 seeds = 20 formal runs
```

Phase Cは探索診断であり、V1.8 ACCEPTのHARD GATEではない。

全滅しても「進化的に不可能」とは断定しない。初期絶滅が速すぎて有利変異が出る前に消える可能性を区別する。

必須出力:
- survival / extinction
- population
- generation
- births/deaths
- trait mean/median/p10/p90
- lineage persistence
- sunset/dawn reserve

---

# 9. runtime profile — 約10時間枠

formal開始前にrepresentative benchmarkを実施し、**Exp14全体wall-clock予測を先に報告する。**

結果ではなくruntime予測だけで以下から選ぶ。

## FULL profile

```text
Phase A: 21 run ×2k
Phase B: 75 run ×5k
Phase C: 20 run ×20k
formal total = 116 runs
nominal ticks = 817,000
```

## COMPACT profile

```text
Phase A: 21 run ×2k
Phase B: 75 run ×3k
Phase C: 20 run ×10k
formal total = 116 runs
nominal ticks = 467,000
```

選択規則:

```text
FULLの安全率込み全体予測 <= 9時間
  -> FULL
else
  -> COMPACT
```

COMPACTの安全率込み予測が10時間を超える場合:
- formalを開始しない
- 人間へ報告
- Claude判断でgrid/seed/条件を削らない

1 run時間だけでなく:
- phase別run/tick
- benchmark実測
- max-parallel
- wave数
- setup/preflight/collect
- safety factor
- Exp14全体wall-clock
を報告する。

実行後はprediction vs actualも保存する。

---

# 10. Exp14前 technical HARD GATE

## 10.1 late metric semantics

Exp13でearly extinctionなのに`late_pop_ok=True`となった表示を修正する。

- late window未到達は `N/A`
- N/AをPASS/FALSEの分子・分母へ混ぜない
- unit test

## 10.2 scientific STOP / technical FAIL

```text
SCIENTIFIC_STOP / REVIEW
```

をActions technical failureと分離する。

technical FAIL:
- crash
- test fail
- artifact欠落
- Config/SHA/integrity違反

scientific result:
- EXTINCT
- POP_HALT
- SCIENTIFIC_STOP/REVIEW

科学STOPでもartifact/reportを保存する。

## 10.3 observation non-interference

新しいcycle/reserve recorderが:
- RNGを消費しない
- stateを変更しない
- update orderを変えない

ことを独立testする。

## 10.4 config / matrix tests

手書きmatrixミスを防ぐ。

独立testで:

```text
Phase A = 21
Phase B = 75
Phase C = 20
formal total = 116
```

を確認。

fixed_genesはcanonical `GENE_NAMES`から検証する。

## 10.5 preflightとformalを分離

Exp13でPhase 0 PASS後にformalが自動開始した再発を防ぐ。

Exp14 workflowは少なくとも:

```text
mode = preflight
mode = formal
```

を分離する。

`preflight`はformal matrixを自動開始しない。

preflight完了
-> runtime全体予測をユーザーへ報告
-> formalを別dispatch

の順をHARD RULEとする。

---

# 11. Actions構成推奨

```text
preflight workflow
  -> config/checker/unit/integration
  -> deterministic smoke
  -> representative runtime benchmark
  -> report only / STOP

formal workflow
  -> Phase A matrix
  -> Phase A collect
  -> Phase B matrix
  -> Phase C matrix
  -> collect/integrity
  -> Exp14 report
```

Phase B/Cは科学結果を見て条件を後付け変更しない。
事前登録済みmatrixを実行する。

Phase A/B/Cは同一formal SHA / numeric environmentであることを確認する。

---

# 12. Exp14の読み方

第一にR_ref仮説を見る。

期待:

```text
A0 collapse
A1/A2/A4/A6 improve
A3 does not improve
A5 transient effect at most
```

この順序が概ね成立し、Phase Bでも低R_refほど安定するなら:

> 主機構 = continuous starvation intervalとEnergy reserve time scaleの不整合

と判断する。

複数armが改善したことだけを理由に`interaction`とは呼ばない。

A3が明確に改善、またはPhase BがR_refと非単調なら:

> R単独モデル不十分

としてdensity uptake / spatial competition / resource sharing / population feedback等を再検討する。

Phase Cで自然適応が観測された場合:

> 世界定数を即変更せず、進化によるdiel adaptationを優先候補として次実験へ進む

Phase Cで適応が観測されない場合も:

> 直ちにenergy_capacityやperiodを恒久変更しない

Phase B mapと絶滅時間を合わせ、次の選定実験を設計する。

---

# 13. Chemicalの扱い

Exp14ではExp13 A2 chemical gridを再計算しない。

暫定候補:

```text
chemical_uptake_half = 1.5
chem_uptake = 0.5
```

を保存する。

A2b/A3相当のchemical長期/探索/密度確認はlight問題整理後に戻る。

---

# 14. Exp14終了条件

- 116 formal runの期待key完全性、またはresource原因の明示的INCOMPLETE
- Phase A因果診断report
- Phase B R-map
- Phase C evolutionary rescue report
- runtime prediction vs actual
- SCIENTIFIC resultとTECHNICAL statusを分離

Exp14内で恒久parameterを自動確定しない。

---

# 15. Exp14後

```text
Exp14
  mechanism + R map + evolution probe
      ↓
人間考察
      ↓
必要ならworking period / storage / lightの選定実験
      ↓
chemical暫定候補の長期・探索・density確認
      ↓
light-only / chemical-only長期成立
      ↓
mixed evolution
      ↓
V1.9 chemical-first ancestor -> phototrophy創発
```
