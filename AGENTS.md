# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/次の実験計画.md` — **現在の司令塔**
2. `docs/Exp12_結果考察.md` — **Exp12正式結果 / V1.7 `bmr_core=0.15`判断**
3. `docs/V1.8_一次Energy生態非対称仕様.md` — **V1.8科学・実装仕様の正本**
4. `docs/Exp13_実験計画確定.md` — **Exp13条件・選定規則・判定の正本**
5. `docs/V1.8_実装チェックリスト.md` — **実装品質HARD GATE**
6. `docs/メインストリーム開発ストーリー.md` — **V1.9以降の更新前提ロードマップ**
7. `docs/数値再現性・Actions実行環境方針.md`
8. `docs/LUCA参照モデル方針.md`
9. `docs/実験結果保存方針.md`
10. `docs/バージョニング方針.md`

Exp11/Exp12の事前登録・レビュー文書は履歴として保存する。

**現在の実装・次実験について古いExp12司令より本書と上記1〜5を優先する。**

---

# 2. 現在地

```text
V1.4 / Exp08                         完了 / Green
V1.5 / Exp09                         完了 / Green
V1.6 / Exp10                         完了 / Green
V1.7 bmr_core実装                    完了
Exp11                               完了 / 再集計・考察済み
Exp12初回Phase0                     過去artifact bit比較で安全停止（履歴）
Exp12再現性gate修正                  完了
Exp12 formal run 33592901348          71/71 / workflow success
Exp12考察                             完了
V1.7恒久値                            bmr_core=0.15 人間判断確定
V1.7 default反映 / v1.7-final        ← 最初に実施
V1.8実装                             ← V1.7 close後
Exp13                               ← V1.8実装後
```

---

# 3. Exp12最終解釈

B1 = light-only / light specialist / body_sizeのみ進化。

```text
bmr_core 0.00〜0.10 -> lower-bound equilibrium
0.15                -> interior equilibrium 8/8
0.20                -> interior 7/8 + converging 1
0.30                -> interior 6/8 + converging 2
```

B1で `DELAY_CONTINUES` は0 run。

したがって `bmr_core` は極端小型化を抑制する機能を持つと判断し、**目的を達成する最小側の試験値 `0.15` を恒久採用**する。

B2 = chemical-only / chemical specialist は事前登録method positive controlを満たさなかったが、50kでもB2自体が変化していた。

したがって:

```text
B2 = METHOD CONTROL ASSUMPTION INVALID / NOT A KNOWN STATIONARY CONTROL
```

と扱う。

B2科学run自体を失敗扱いしない。V1.7の目的達成に追加100k等は不要。

---

# 4. V1.7 closeをV1.8より先に行う

V1.8変更前に:

```text
Config.bmr_core default = 0.15
```

へ変更する。

必須:
1. full pytest
2. conservation
3. determinism
4. CI Green
5. V1.7 CI基準ref更新
6. `v1.7-final` branch保存

V1.7 default確定とV1.8科学ロジックを1つの曖昧な差分へ混ぜない。

---

# 5. V1.8絶対方針

V1.8は一次Energy sourceの生態的非対称性を作る。

```text
light
- broad
- renewable flow
- low-average instantaneous input
- day/night
- surface area + intensity dependent

chemical
- localized stock
- high burst potential
- consumption depletes stock
- competition
- vent source replenishes
```

## 実装原則

共通飽和response:

```text
H(x,K)=x/(x+K)
```

をlight/chemicalの最大要求量へ入れる。

light effective flux:

```text
base_light * daylight_factor(tick)
```

nightは厳密0。

### 絶対にしない

- lightへ直接penalty
- chemicalへ固定Energy bonus
- light userだけmovement強制OFF
- chloroplast専用維持費
- cyanobacteria class
- vent source有限寿命
- V1.8でINITIAL_GENOME.light_absorptionを0化
- bmr_coreの再調整

phototrophyの進化起源はV1.9事項。

---

# 6. V1.8 Config予定

Exp13選定前はV1.7互換feature flags:

```text
primary_energy_density_response = False
light_cycle_enabled = False
```

新項目:

```text
light_uptake_half = 0.6
chemical_uptake_half = 6.15
light_cycle_period_ticks = 200
light_day_fraction = 0.5
```

feature OFFでV1.7-final bit完全回帰をHARD GATEとする。

Exp13はfeature ON Configで実行。

---

# 7. Recorderで特に注意する点

昼夜導入後、現在の:

```text
static light supply per tick * tick
```

では `light_supply_cum` が誤る。

必ず実効供給をtickごとに積算する。

追加観測:

```text
light_cycle_factor
light_supply_rate
```

`World.light` static snapshotはpeak/base habitat fieldとして残す。

既存指標の意味を黙って変更しない。

---

# 8. Exp13の順序

```text
Phase 0
  ↓
A1 light calibration
  ↓
A2 chemical calibration
  ↓
A3 density competition
  ↓
Phase A verdict
  ↓ A_PASSのみ
selected parameters固定
  ↓
B1 light-only
B2 chemical-only
B3 mixed exploratory evolution
  ↓
collect / verdict
```

A1 light:

```text
light_max=1.2
```

から始める。不成立時のみ事前登録rescue:

```text
1.5 -> 1.8 -> 2.4
```

4/5以上成立する最小値。

A2 chemical:

```text
chem_uptake=1.0,2.0,4.0
```

から事前条件を満たす最小値。

結果を見て新しい候補値を同じExp13へ追加しない。

詳細はExp13正本。

---

# 9. Exp13 Phase 0は軽量化

Exp12の10k×2再現試験を毎回繰り返さない。

V1.8は科学コード変更なので:

```text
representative 2,000 tick ×2
same current runner / same seed / same config
```

をbit完全一致HARD GATEとする。

その他:
- Config schema/manifest
- unit tests
- conservation
- workflow E2E
- CI Green

必須。

---

# 10. 数値再現性

過去Hosted Runner artifactとのbit mismatch単独をFAILにしない。

HARD GATE:

```text
現在SHA / 現在runner / 現在numeric environment内の再現性
```

正式runでは:
- expected run完全性
- Config
- SHA
- numeric environment
- artifact
- aggregation

を確認する。

詳細は `docs/数値再現性・Actions実行環境方針.md`。

---

# 11. Actions・CI・push運用

CIは最終独立確認。途中実装のデバッグ目的でpushを乱発しない。

- 論理的変更単位までローカルで完成させる
- Python/Config/collector/workflow変更は原則 `uv run pytest tests -q` をpush前に通す
- 新Exp・科学ロジック・Config・出力形式・workflow変更はformal前CI Green必須
- local failureをCIで原因調査するだけのpushは禁止
- Markdownのみの修正はまとめる
- 科学コードと文書をCI回避目的で不自然に混ぜない

作業完了報告は:
1. local tests
2. CI
3. Phase 0
4. runtime estimate
5. formal dispatch
6. 未確認事項

を分ける。

---

# 12. run status

```text
COMPLETE
EXTINCT
POP_HALT
INCOMPLETE_RESOURCE
INTEGRITY_FAIL
```

- EXTINCT / POP_HALT = 科学結果
- timeout / runner interruption / artifact欠落 = INCOMPLETE_RESOURCE
- SHA / Config / numeric environment等のformal integrity違反 = INTEGRITY_FAIL
- 技術的不完了だけ同一SHA/Configで再実行可

---

# 13. 実行時間

時間測定専用instrumentationを追加しない。

既存Actions timestamps / performance.csv / done logsを使う。

formal前:
- single-run max予測
- run数
- max-parallel
- matrix wall-clock概算
- safety margin / uncertainty

formal後:
- workflow wall-clock
- phase別wall-clock
- run median/P90/max
- prediction vs actual

を残す。

**single-run timeout予測とmatrix全体wall-clockを混同しない。**

---

# 14. V1.8実装品質HARD GATE

`docs/V1.8_実装チェックリスト.md` を全項目確認する。

要求トレーサビリティ:

| Requirement | Implementation | Test | Result |
|---|---|---|---|

をformal dispatch前に作り、空欄が1つでもあれば未完成。

特に:
- day/night
- effective light sensing
- density-dependent light uptake
- density-dependent chemical uptake
- stock depletion
- fair sharing
- actual light ledger
- V1.7 regression
- Config validation
- Phase A selection
- artifact completeness

を漏らさない。

---

# 15. 小型化に関する絶対原則

**小型化を抑えるためだけの人工的ペナルティは入れない。**

V1.7 `bmr_core` はbody_sizeへの直接罰ではなく、全生命共通の基礎維持代謝。

`max_population_halt` は計算安全停止であり生態ルールではない。

---

# 16. LUCA-inspired参照方針

LUCAそのものを再現しない。

- 現実から構造・因果・scaling・比率を主に借りる
- 未校正Energy/Matter/tickへSI絶対値を直結しない
- LUCAらしさへ適応度を与えない
- 地球史どおりの結果を直接指定しない
- その後の進化は自然選択へ任せる

---

# 17. プロジェクト絶対原則

1. 適応度を直接計算しない
2. 完成した種classを作らない
3. 寿命値を直接作らない
4. コストは物理・生理則から導く
5. Matter保存・Energy台帳を守る
6. RNG系列・決定性を意識する
7. 想定外戦略を許容する
8. 特定生態型へ直接bonusを与えない
9. 原則1軸ずつ変更する
10. 遺伝子の存在と進化経路の成立を区別する
11. 比較Energy戦略は単独成立性を先に確認
12. 行動へ暗黙の未来予測/知能を入れない
13. 結果を見て同じ実験の候補・閾値を後付け変更しない
14. 科学STOP/REVIEWと技術FAILを区別する

---

# 18. V1.9以降

近未来mainstream:

```text
V1.8  light/chemical source物理の分化
  ↓
V1.9  chemical-first祖先からphototrophy創発
  ↓
動的vent / resource turnover
  ↓
HGT / primitive recombination
  ↓
engulfment / intracellular symbiosis
  ↓
plastid-like integration
  ↓
oxygenic photosynthesis / planetary feedback
```

詳細は `docs/メインストリーム開発ストーリー.md`。

遠未来ほど更新前提。AIはこのroadmapを勝手に固定仕様扱いしない。

---

# 19. 実験結果保存

`docs/実験結果保存方針.md` に従う。

文字サマリーだけでformal experimentを閉じない。

- GitHub: 結果考察 / NOTES / aggregate plots / representative figures / runtime prediction-vs-actual
- raw data / 全画像: external storage / Actions artifact

## 技術stack

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest
