# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/次の実験計画.md` — **現在の司令塔**
2. `docs/Exp14_レビュー判断.md` — **Opus 5レビューの人間採否 / 最優先科学判断**
3. `docs/Exp14_実験計画確定.md` — **Exp14科学条件正本**
4. `docs/Exp14_実装チェックリスト.md` — **Exp14実装品質HARD GATE**
5. `docs/Exp13_結果考察_中間.md` — Exp13実測/原因考察
6. `docs/V1.8_一次Energy生態非対称仕様.md` — V1.8物理仕様
7. `docs/V1.8_Exp13_レビュー判断.md` — V1.8設計判断履歴
8. `docs/Exp13_実験計画確定.md` — Exp13事前登録履歴。**再dispatchしない**
9. `docs/V1.7_総括.md`
10. `docs/メインストリーム開発ストーリー.md`
11. `docs/数値再現性・Actions実行環境方針.md`
12. `docs/実験結果保存方針.md`
13. `docs/バージョニング方針.md`

Exp14レビュー原文:

```text
branch: claude/review-v1-7-exp11-kflr82
commit: 2383ee5afee50ac5493d3a5332eb7d2433ae0c0e
file: docs/Exp14_Opus5レビュー.md
```

**レビュー原文を独自採用しない。必ず`docs/Exp14_レビュー判断.md`を優先する。**

---

# 2. 現在地

```text
V1.4 / Exp08                  完了
V1.5 / Exp09                  完了
V1.6 / Exp10                  完了
V1.7 / Exp11 / Exp12          完了 / bmr_core=.15
V1.8実装                      完了 / main merge済み
Exp13 Phase 0                 PASS
Exp13 A1                      8 light水準すべて5/5 EXTINCT
Exp13 A2                      chemical grid完了 / 暫定候補あり
Exp13                         LIGHT_CALIBRATION_FAIL / REVIEWで科学STOP
Exp14                         ← 現在ここ
```

Exp13 formal:

```text
run id 33722634280
SHA a8f33648c0287b5eb47304f0c079b90715a19130
```

Exp13のActions赤表示は科学STOPをtechnical failureとして表現した運用問題を含む。Exp14前に分離する。

---

# 3. V1.8絶対方針

```text
light
- broad
- renewable flow
- day/night
- low-average input
- surface area + intensity dependent

chemical
- localized stock
- depletable
- competitive
- high-local-return potential
- vent source replenishes
```

一次Energy直接吸収のみ:

```text
H(x,K)=x/(x+K)
```

light day/nightはhalf-sine / day_fraction=.5。
**energy中立正規化しない。**

絶対にしない:
- light直接fitness penalty
- chemical固定Energy bonus
- plant/cyanobacteria/chloroplast class
- oxygen field
- finite vent lifetime
- V1.8でINITIAL_GENOME.light_absorption=0
- bmr_coreを小型化だけのため再調整
- light userだけを強制静止

phototrophy起源はV1.9事項。

---

# 4. Exp13で得た新しい問題

light_maxを0.8〜4.0まで広く振っても全滅した。

典型:

```text
昼: population 100 -> 400〜500級
夜: starvationで一桁〜十数個体
翌昼: 再増殖
翌夜: 再崩壊
```

現時点の主要mechanism:

```text
continuous darkness duration
vs
available Energy reserve / night drain
```

繁殖が昼の余剰Energyを親子へ分配するため、light量を増やすだけでは夜前reserveが十分増えない可能性が高い。

Exp14では分析専用量:

```text
R_ref = night length / reference night survival ticks
```

を事前登録する。

R_refをsimulationのfitness/behaviorへ使ってはいけない。

---

# 5. Exp14 science matrix

詳細は`docs/Exp14_実験計画確定.md`。

## Phase A — mechanism diagnostic

```text
A0 baseline
A1 no night / same mean supply
A2 period80
A3 light8
A4 repro threshold .8
A5 initial_energy40
A6 energy_capacity200 + initial_energy100
```

```text
7 arms ×3 seed ×2k =21
```

A3はR仮説の反証arm。
A5は初期tick1一斉繁殖の交絡分離。
A6は初期E/Emaxを揃えたstorage capacity診断。

## Phase B — period × energy_capacity map

```text
period = 80,120,160,200,240
energy_capacity = 75,100,125,150,200
```

```text
25 cells ×3 seed =75
```

capacity変更時:

```text
initial_energy = 0.5 * energy_capacity
```

固定表現型の成立/崩壊境界とR_refを地図化する。
恒久parameterは自動選定しない。

## Phase C — evolutionary rescue

baseline world constantsを維持し、既存形質だけ解放。

```text
C1 body_size only
C2 reproduction_investment only
C3 movement_power only
C4 above 3 traits
```

```text
4 arms ×5 seed =20
```

Formal total:

```text
21 +75 +20 =116 simulation runs
```

---

# 6. runtime — 約10時間枠

formal前にrepresentative runtime benchmarkを取る。

科学結果ではなくruntime予測だけで事前登録profileを選択する。

```text
FULL:
 Phase A 2k
 Phase B 5k
 Phase C 20k
 nominal 817k ticks

COMPACT:
 Phase A 2k
 Phase B 3k
 Phase C 10k
 nominal 467k ticks
```

選択:

```text
FULL安全率込み全体予測 <=9h -> FULL
else -> COMPACT
```

COMPACT安全率込み>10hならformalを開始せず人間へ報告する。
Claude判断でseed/grid/armを削らない。

---

# 7. preflight / formalを絶対に分離

Exp13ではPhase 0 PASS後にformalが自動開始した。再発禁止。

Exp14:

```text
preflight dispatch
 -> tests
 -> config/matrix
 -> determinism
 -> representative benchmark
 -> runtime reportを作って終了
```

**preflightからformalへ自動遷移しない。**

ユーザーへExp14全体wall-clock予測を報告した後、formalを別dispatchする。

formal開始前の報告:
- FULL/COMPACT
- formal 116 run
- phase別tick
- benchmark
- max-parallel
- wave数
- preflight/collect
- safety factor
- Exp14全体wall-clock

1 run時間だけでは不可。

---

# 8. Exp14実装品質HARD GATE

`docs/Exp14_実装チェックリスト.md`を全項目確認する。

formal前に:

| Requirement | Implementation | Independent Test | Result |
|---|---|---|---|

を作る。

空欄が1つでもあればGOしない。

特に:
- A0-A6
- Phase B 25×3
- Phase C mutable/fixed genes
- formal total=116
- FULL/COMPACT
- A6 initial_energy連動
- Phase B initial_energy導出
- R_ref
- late N/A semantics
- scientific STOP分離
- recorder非干渉
- artifact完全性
- preflight/formal分離

を独立testする。

---

# 9. Recorder / ledger

既存V1.8:

```text
light_cycle_factor
light_supply_rate
light_supply_cum = actual effective supply integral
flow_light_cum = actual uptake
```

Exp14追加集計:
- sunset/dawn population
- daylight births
- night starvation deaths
- daytime peak / night minimum
- night_min / preceding_day_peak
- Energy/capacity mean/median/p10/p90
- Phase C trait quantiles
- lineage persistence

観測コードはRNG/state/update orderを変更してはいけない。

---

# 10. run status

```text
COMPLETE
EXTINCT
POP_HALT
SCIENTIFIC_STOP / REVIEW
INCOMPLETE_RESOURCE
INTEGRITY_FAIL
```

- EXTINCT/POP_HALT/SCIENTIFIC_STOP = 科学結果
- timeout/runner interruption = INCOMPLETE_RESOURCE
- crash/test/artifact/Config/SHA integrity違反 = technical fail

科学STOPでもartifact/reportを必ず保存する。

late window未到達は`N/A`。PASS扱いしない。

---

# 11. CI / push運用

CIは最終独立確認。

- 途中デバッグpushを乱発しない
- Python/Config/collector/workflow変更はpush前に関連test＋原則full pytest
- formal前CI Green
- checker/testが同じ手書き誤定数を共有しない
- fixed_genesはcanonical `GENE_NAMES`
- recorder実形式のE2E fixture
- expected artifact key完全性

---

# 12. プロジェクト絶対原則

- 適応度を直接計算しない
- 完成した種classを作らない
- 寿命を直接設定しない
- costは物理/生理則から
- Matter保存 / Energy台帳
- RNG / 決定性
- 想定外戦略を許容
- 特定生態型へ直接bonusしない
- 遺伝子の存在と進化経路の成立を区別
- Energy戦略は単独成立性を先に確認
- 行動へ未来予測/知能を暗黙導入しない
- 結果後に同一experimentへ条件を思いつき追加しない
- 科学STOPと技術FAILを分離

小型化だけを防ぐ人工penaltyを追加しない。

---

# 13. Chemical

Exp14ではExp13 A2を再sweepしない。

暫定候補:

```text
chemical_uptake_half =1.5
chem_uptake =.5
```

light問題整理後に長期/探索/density validationへ戻る。

---

# 14. V1.9以降

```text
V1.8 source物理分化
 -> V1.9 chemical-first ancestorからphototrophy創発
 -> dynamic vents/resource turnover
 -> HGT
 -> engulfment/intracellular symbiosis
 -> plastid-like integration
 -> oxygenic photosynthesis/planetary feedback
```

メインストリーム方針はExp14では変更しない。

---

# 15. 実験結果保存

`docs/実験結果保存方針.md`に従う。

文字summaryだけでformalを閉じない。

GitHub:
- 結果考察
- aggregate plot/table
- runtime prediction vs actual
- scientific/technical verdict

raw:
- Actions artifact / external storage

技術stack: Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest
