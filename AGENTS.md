# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/次の実験計画.md` — **現在の司令塔**
2. `docs/V1.8_Exp13_レビュー判断.md` — **Opus 5レビューの人間採否 / 最優先設計判断**
3. `docs/V1.8_一次Energy生態非対称仕様.md` — **V1.8実装正本**
4. `docs/Exp13_実験計画確定.md` — **Exp13条件・選定規則・run構成正本**
5. `docs/V1.8_実装チェックリスト.md` — **実装品質HARD GATE**
6. `docs/V1.7_総括.md` — **V1.7完了判断 / Exp11・Exp12総括**
7. `docs/Exp12_結果考察.md`
8. `docs/メインストリーム開発ストーリー.md`
9. `docs/数値再現性・Actions実行環境方針.md`
10. `docs/LUCA参照モデル方針.md`
11. `docs/実験結果保存方針.md`
12. `docs/バージョニング方針.md`

Opus 5レビュー原文はbranch `claude/review-v1-7-exp11-kflr82` commit `6dba4b4` にある。**レビュー原文の提案を独自採用せず、上記1〜5を優先する。**

旧Exp11/12事前登録・レビューは履歴として保存する。

---

# 2. 現在地

```text
V1.4 / Exp08                      完了
V1.5 / Exp09                      完了
V1.6 / Exp10                      完了
V1.7 bmr_core実装                 完了
Exp11                            完了 / 255 run
Exp12                            完了 / 71/71 formal run
V1.7科学判断                      bmr_core=.15で終了
V1.7 default反映 / v1.7-final     ← 最初に実施
V1.8実装                          ← その次
Exp13                            ← 実装・監査後
```

Exp13結果考察はV1.8チャットで行う。

---

# 3. V1.7確定事項

```text
BMR = bmr_core + (bmr_coef - bmr_core) * M^0.75
bmr_core = 0.15
```

Exp12 B1では0.15が8/8 seedでinterior equilibrium、B1 `DELAY_CONTINUES=0`。

Exp12の事前登録機械判定は:

```text
SCIENTIFIC_VERDICT = INVALID_OR_METHOD_REVIEW
```

（B2 method-control gate未達）。

人間判断は:

```text
METHOD CONTROL ASSUMPTION INVALID
```

すなわちB2自身が50kでも変化しており、既知stationary controlという前提が不成立。B2科学runを失敗扱いしない。

0.15は自然界の相転移点ではなく、事前sentinelを最初に超えた試験格子点。将来環境変更後にbody_size平衡を再確認しうる。

---

# 4. V1.7 closeをV1.8より先に行う

V1.8コード変更前に:

```text
Config.bmr_core default 0.0 -> 0.15
```

必須:
1. full pytest
2. conservation
3. determinism
4. CI Green
5. V1.7 CI基準ref更新
6. `v1.7-final`保存

V1.7 closeとV1.8科学変更を同一の曖昧なcommitへ混ぜない。

---

# 5. V1.8絶対方針

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

共通density response:

```text
H(x,K)=x/(x+K)
```

をlight/chemical**直接一次Energy吸収だけ**へ導入。

### day/night重要判断

half-sine / day_fraction=.5を使用し、**energy中立正規化しない。**

同じ`light_max`なら静的V1.7より一周期平均lightが低くなることを意図した性質とする。昼を3.14倍して旧総量へ合わせない。

`light_max`はExp13で広くsweepする。

### 絶対にしない

- light直接fitness penalty
- chemical固定Energy bonus
- light user movement強制OFF
- plant/cyanobacteria/chloroplast class
- oxygen field
- finite vent lifetime
- V1.8でINITIAL_GENOME.light_absorption=0
- bmr_core再調整

phototrophy起源はV1.9事項。

---

# 6. V1.8 Config

選定前feature OFF:

```text
primary_energy_density_response = False
light_cycle_enabled = False
```

新項目:

```text
light_uptake_half = 0.6
chemical_uptake_half = 6.15  # 暫定default、Exp13でsweep
light_cycle_period_ticks = 200
light_day_fraction = 0.5
```

feature OFF/OFFでV1.7-final回帰をHARD GATE。

Exp13 chemical grid:

```text
chemical_uptake_half = 0.5,1.5,3.0,6.15
chem_uptake          = 0.5,1.0,2.0,4.0
```

---

# 7. Recorder / ledger注意

昼夜導入後、`static light supply × tick`で`light_supply_cum`を計算してはいけない。

必ずactual effective light supplyをstepごとに積算する。

追加/明確化:

```text
light_cycle_factor
light_supply_rate
light_supply_cum = effective supply integral
flow_light_cum = actual organism uptake
```

`World.light` static snapshotはbase/peak habitat field。

観測機能がRNG/stateへ影響しないこと。

---

# 8. Exp13構成

Phase 0後、A1/A2を並列開始可。

```text
Phase 0
 -> A1 light map
 -> A2 chemical grid
 -> select_A
 -> A2b selected validation + A3 density
 -> Phase A collect
 -> B1/B2/B3/B4
 -> final collect
```

### A1 light

```text
light_max = 0.8,1.2,1.5,1.8,2.1,2.4,3.0,4.0
5 seed ×10k = 40 run
```

全水準を実行。working lightは`ROBUST_LIGHT_VIABLE`を満たす最小値。

初期個体を各光量へ合わせて救済しない。

### A2 chemical

```text
4 K × 4 uptake ×3 seed ×5k = 48 run
```

selected:
1. admissible中の最小`chem_uptake`
2. 同じuptakeでrealized median Hが0.5に最も近いK

### A2b / A3

```text
selected vent/random validation = 10 run
density competition             = 9 run
```

Phase A = 107 run。

### Phase B

```text
B1 light-only                8 ×20k
B2 chemical-only             8 ×20k
B3 mixed 2-gene evolution   12 ×30k
B4a body_size=.246 fixed     3 ×5k
B4b body_size-only evolution 5 ×20k
```

Phase B = 36 run。

Formal planned total = **143 simulation runs**。

BURST_RATIOは選定HARD GATEにしない。

---

# 9. Phase 0 / 数値再現性

Exp12の10k×2を毎回繰り返さない。

V1.8科学コード変更のため:
- unit/integration
- conservation
- Config/manifest
- feature flag 4組合せ
- representative 2k×2 current-run determinism
- collector E2E
- CI Green

をHARD GATE。

過去Hosted Runner artifactとのbit mismatch単独をFAILにしない。

formalではConfig/SHA/numeric environment/artifact/expected key完全性を確認する。

---

# 10. Actions・CI・push運用

CIは最終独立確認。途中実装のデバッグ目的でpushを乱発しない。

- 論理的変更単位までローカルで完成
- Python/Config/collector/workflow変更はpush前に関連test＋原則full pytest
- 新科学ロジック/Config/workflowはformal前CI Green
- local failureの原因調査だけをCIへ投げない
- Markdownのみはまとめる
- 科学コードと文書をCI回避目的で不自然に混ぜない

Exp11/12再発防止:
- fixed_genesはcanonical `GENE_NAMES`から検証
- checker/testが同じ手書き誤定数を共有しない
- Recorder実形式のE2E fixture
- artifact全件取得
- technical failとscientific REVIEW分離

---

# 11. run status

```text
COMPLETE
EXTINCT
POP_HALT
INCOMPLETE_RESOURCE
INTEGRITY_FAIL
```

- EXTINCT/POP_HALT = 科学結果
- timeout/runner interruption/artifact欠落 = INCOMPLETE_RESOURCE
- Config/SHA/numeric environment等のformal integrity違反 = INTEGRITY_FAIL
- 技術的不完了のみ同一SHA/Configで再実行可

---

# 12. Exp13実行時間 — 今回の最重要運用

時間専用instrumentationを追加しない。

**Phase A formal開始前に、Sonnet 5はExp13全体終了までのwall-clock概算をユーザーへ報告する。**

必須:
- formal 143 run予定
- phase別run/tick
- short benchmark
- single-run最大概算
- max-parallel
- wave数
- Phase 0/selection/collectを含む**Exp13全体合計予測時間**
- safety factor / uncertainty

1 run時間だけ報告して開始してはいけない。

実験後:
- workflow total
- phase別wall-clock
- run median/P90/max
- prediction vs actual

を保存。

---

# 13. V1.8実装品質HARD GATE

`docs/V1.8_実装チェックリスト.md`全項目を確認。

formal前に:

| Requirement | Implementation | Independent Test | Result |
|---|---|---|---|

を作り、空欄が1つでもあれば未完成。

特に:
- V1.7 close
- day/night non-normalized
- step内factor一貫性
- light/chemical density uptake
- chemical K sweep
- fair sharing
- actual light ledger
- V1.7 regression
- 4 feature flags
- Config/fixed genes
- artifact completeness
- runtime total estimate

を漏らさない。

---

# 14. 小型化に関する原則

小型化抑制だけを目的にした人工penaltyを追加しない。

V1.7 `bmr_core`は全生命共通基礎維持代謝。

V1.8 day/nightはbody_size選択圧を自然に変える可能性があるのでB4で診断する。

---

# 15. LUCA-inspired / プロジェクト絶対原則

- 適応度を直接計算しない
- 完成した種classを作らない
- 寿命値を直接作らない
- costは物理/生理則から
- Matter保存/Energy台帳
- RNG/決定性
- 想定外戦略を許容
- 特定生態型へ直接bonusしない
- 原則1軸ずつ。ただし複数機構を同一versionへ入れる場合はfeature flagでfactorize
- 遺伝子の存在と進化経路の成立を区別
- Energy戦略は単独成立性を先に確認
- 行動へ未来予測/知能を暗黙導入しない
- 結果後に同一実験候補/閾値を追加しない
- 科学STOP/REVIEWと技術FAILを区別

現実からは構造・因果・scaling・比率を優先して借り、未校正SI絶対値を直接移植しない。

---

# 16. V1.9以降

```text
V1.8 source物理分化
 -> V1.9 chemical-first ancestorからphototrophy創発
 -> dynamic vents/resource turnover
 -> HGT
 -> engulfment/intracellular symbiosis
 -> plastid-like integration
 -> oxygenic photosynthesis/planetary feedback
```

V1.9前に`light_absorption=0`から有意値へ到達する待ち時間を軽量検算する。

engulfment以降は「個体が個体を内包する」データモデル変更規模と認識し、独立設計する。

---

# 17. 実験結果保存

`docs/実験結果保存方針.md`に従う。

文字サマリーだけでformalを閉じない。

- GitHub: 結果考察 / NOTES / aggregate plots / representative figures / runtime prediction-vs-actual
- raw data / 全画像: external storage / Actions artifact

技術stack: Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest
