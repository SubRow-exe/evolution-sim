# Exp11 実験計画案 — core maintenance と body size 進化

更新: 2026-09-01
状態: **レビュー用事前登録案 / 未実装 / 未実行**

関連:
- `docs/V1.7_基礎維持代謝仕様案.md`
- `docs/LUCA参照モデル方針.md`
- `docs/Exp10_結果考察.md`

---

## 1. 問い

V1.7候補の縮小不能な基礎維持代謝 `C_core` を導入すると、

1. 現行世界で見えた `body_size=0.2` 方向への強い小型化圧を弱められるか
2. 逆に `body_size=10` への大型化を強制してしまわないか
3. 特定サイズを設計者が直接指定せず、内部サイズに進化平衡を作れるか
4. 同じ `C_core` でも資源環境によって異なるサイズが選択される余地を残せるか
5. 個体数爆発を抑える方向へ働きつつ、生態そのものを壊さないか

を検証する。

**populationを小さくすること自体を最適化目的にはしない。**
主目的は、サイズ進化が遺伝子境界へ一方向に張り付く構造を解消することである。
計算コスト低下は、その結果として期待する副次的効果とする。

---

## 2. 変更する軸

Exp11で振る世界パラメータは `C_core` だけ。

```text
BMR = C_core + (0.3 - C_core) * M^0.75
```

`M` は現在の身体Matter。

body size の進化効果を切り分けるため、Phase Bでは **14遺伝子中 body_sizeだけ進化ON**、
残り13遺伝子は全世代固定する。

温度、body_size上下限、繁殖則、吸収則、行動則、捕食等は変更しない。

---

## 3. C_core候補 — 15水準

合法範囲 `0 <= C_core <= bmr_coef(0.3)` を広く覆う。
低値側は転換点を拾うため密に、0.3は極端な上限対照として置く。

```text
0.000
0.005
0.010
0.015
0.020
0.025
0.030
0.040
0.050
0.060
0.075
0.100
0.150
0.200
0.300
```

`bmr_coef=0.3` に対するcore比率では:

```text
0%, 1.7%, 3.3%, 5%, 6.7%, 8.3%, 10%, 13.3%, 16.7%,
20%, 25%, 33.3%, 50%, 66.7%, 100%
```

### 3.1 候補を広く取る理由

現行モデルにはすでに固定的なsense維持費、固定birth overhead、
サイズ依存速度から生じる概ねサイズ非依存の移動費がある。それでも exploratory run では
`body_size≈0.226` まで縮小した。

したがって単純なBMR比較だけから狭い候補範囲を決めるのは危険である。
Exp11では0から理論上限0.3まで一度に走らせ、**結果を見て候補を追加する中間判断は行わない**。

---

## 4. 実行前提 — V1.6を先に閉じる

Exp10人間判断で採用した

```text
memory_tau = 10
response_gain = 64
```

のうち、2026-09-01時点で通常defaultの `response_gain` は16のまま残っている。

Exp11実装前に、V1.7とは別の確定処理として:

1. `response_gain=64` をV1.6 defaultへ反映
2. 結果変更に伴うCI基準を更新
3. `v1.6-final` branchを保存
4. そのcommitをV1.7の親とする

Exp11 Configにも `memory_tau=10 / response_gain=64` を明示する。

---

# Phase 0 — 決定論・式・回帰テスト

Phase 0は本番runを投入する前の**停止条件**。

## 5. 必須項目

### P0-1. `C_core=0` 完全回帰

V1.6-final と同一Config・同一seedで、`bmr_core=0` のV1.7候補実装が
既存goldenケースに完全一致すること。

### P0-2. reference point不変

任意の合法 `C_core` で:

```text
M=1.0 -> BMR=0.3
```

が数値誤差なし、または実装上妥当な厳密許容差で成立。

### P0-3. 境界

```text
C_core=0.0 -> old formula
C_core=0.3 -> BMR=0.3 constant
```

### P0-4. illegal Config

```text
C_core < 0
C_core > 0.3
```

を拒否する。

### P0-5. Energy / Matter / RNG

- Energy台帳整合
- Matter厳密保存
- 同一seed決定性
- 観測コードがRNG系列を変えない

### P0-6. body_size only evolution

Phase B Config全45ケース（15 `C_core` × 3環境）について、
`fixed_genes` が body_size以外の13遺伝子をすべて含み、body_sizeだけを含まないことを
生成時テストで機械的に確認する。

1項目でも失敗したらPhase Bを起動しない。

---

# Phase A — 実行前の生理・life-cycle監査

Phase Aは**候補削減に使わない**。全15候補は結果に関係なくPhase Bへ進む。
途中判断を発生させないためである。

## 6. A1: サイズ地形の決定論計算

以下の現在Matterについて、全15 `C_core` を計算する。

```text
M = 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.0,
    1.5, 2.0, 3.0, 5.0, 7.5, 10.0
```

INITIAL_GENOME、健全度 `phi=1` を基準に、以下をCSV/図で出す。

- BMR
- BMR内のcore成分 / scalable成分
- organ upkeep
- sense upkeep
- membrane upkeep
- resistance upkeep
- movement cost（`v=0` と通常wander速度の両方）
- total maintenance
- `total maintenance / M^(2/3)`
- `C_core / total maintenance`

これは「どのサイズが勝つか」を決める適応度計算ではない。
実際の選択はPhase Bの生態・繁殖・資源競合の帰結に任せる。

## 7. A2: 出産直後の状態監査

core cost は成体だけでなく、親Matterの35%を受け取る小さな子個体へ強く効く可能性がある。
現行繁殖則を変えず、次のtarget sizeで決定論的なbirth-stateを算出する。

```text
target body_size = 0.2, 0.5, 1.0, 2.0, 5.0, 10.0
```

標準化した親状態:

```text
parent matter = target body_size
parent energy = repro_energy_frac * E_max
reproduction_investment = INITIAL_GENOME (=0.4)
child_matter_frac = 0.35
birth_overhead = 2.0
```

実際の `_try_reproduce` と同じ順序で:

- child matter / parent matter
- child energy / parent energy
- child/parent Energy capacity
- child/parent BMR
- 静止時total maintenance
- intake=0と仮定した単純Energy reserve / maintenance

を出す。

ここでも値を見て候補を除外しない。Phase Bの結果解釈用の診断資料とする。

---

# Phase B — body_sizeだけを進化させる正式実験

## 8. 共通条件

```text
ticks                  = 10,000
initial_population     = 100
initial genome         = INITIAL_GENOME + 通常standing variation
body_size              = 進化ON
other 13 genes         = 完全固定
memory_tau             = 10
response_gain          = 64
stats_interval         = 20
snapshot_interval      = 1,000
max_population_halt    = 10,000
```

`max_population_halt=10,000` はpopulationを抑制する生態ルールではない。
10,000個体へ到達した時点でrunを保存して終了する**計算安全装置**であり、
その到達自体を「このC_coreでは多数小型化が十分抑制されなかった」という科学的結果として扱う。

絶滅・population haltは workflow failure にしない。
Config不整合、遺伝子固定違反、環境不一致、保存則破壊、必要run欠落等だけを実行失敗とする。

---

## 9. B1 — Light-only / light specialist（主選定環境）

Exp10 exploratory runで小型化・個体数増大が最も明確に出た環境を主校正条件とする。

```text
light          = vertical standard
chemical       = off
phenotype      = light specialist
light_abs      = 2.0 fixed
chemical_abs   = 0.3 fixed
body_size      = only mutable gene
C_core         = 15 levels
seed           = 1..8
```

run数:

```text
15 × 8 = 120 run
```

---

## 10. B2 — Chemical-only / chemical specialist（一般化・veto）

```text
light          = 0
chemical       = vent flux 16
phenotype      = chemical specialist
light_abs      = 0.3 fixed
chemical_abs   = 2.0 fixed
body_size      = only mutable gene
C_core         = 15 levels
seed           = 1..4
```

初期配置等はExp10正式B2の成立条件を踏襲する。

run数:

```text
15 × 4 = 60 run
```

---

## 11. B3 — Mixed / generalist（一般化・veto）

```text
light          = vertical standard
chemical       = vent flux 16
phenotype      = generalist
light_abs      = 1.0 fixed
chemical_abs   = 1.0 fixed
body_size      = only mutable gene
C_core         = 15 levels
seed           = 1..4
```

run数:

```text
15 × 4 = 60 run
```

---

## 12. 総run数と計算時間設計

```text
B1 120
B2  60
B3  60
------
計 240 run
```

240はGitHub Actions matrixの256ジョブ上限内に収められるため、
**1回のworkflow_dispatchで全条件を登録し、途中の人間判断なしで完走させる**。

`max-parallel=20` を基準とする。

Exp10 exploratoryで最も重かった実測は約40分 / 10,000 tick / run。
これを240 runすべてへ悲観的に当てても:

```text
240 / 20 × 40 min = 480 min = 約8時間
```

約2時間の余裕を残す。
さらにpopulation 10,000到達時は保存して終了するため、想定外の個体数増加で
1 runが際限なく重くなることを避ける。

各jobのtimeoutは余裕を持って120分程度とし、timeoutは科学的STOPではなく実行失敗として記録する。

---

# 測定指標

## 13. runごとの主要指標

### サイズ

- final mean / median body_size
- final Q10 / Q25 / Q75 / Q90
- lower-bound occupancy:

```text
p_low = fraction(body_size <= 0.21)
```

`0.21` は下限0.2の5%以内。

- upper-bound occupancy:

```text
p_high = fraction(body_size >= 9.5)
```

`9.5` は上限10の5%以内。

- late-window mean body_size（8,000–10,000 tick）
- 6,000–8,000 vs 8,000–10,000 のlate drift

### 生態

- 10,000 tick生存 / extinction
- population halt到達
- final / peak population
- births / deaths / death cause
- Energy flow by source
- Matter conservation

### 進化診断

- body_size variance
- body_size以外13遺伝子の分散=0
- boundary occupancyのseed間一貫性

populationは重要な副次指標だが、最小populationになるC_coreを選ぶルールにはしない。

---

# 判定ルール

## 14. runの分類

### COMPLETE

10,000 tickまでpopulation>0で完走し、population haltなし。

### EXTINCT

10,000 tick前にpopulation=0。
科学的結果でありworkflow failureではない。

### POP_HALT

population=10,000へ到達して安全停止。
科学的結果でありworkflow failureではない。

### INVALID

Config不整合、固定遺伝子違反、Energy/Matter破壊、環境不一致、run欠落、timeout等。
これはworkflow failure。

---

## 15. B1 主選定Green

各 `C_core` について8 seed中、以下をすべて満たすこと。

1. **COMPLETE >= 7/8**
2. **POP_HALT <= 1/8**
3. **EXTINCT <= 1/8**
4. final `p_low < 0.25` を **7/8以上**で満たす
5. final `p_high < 0.25` を **7/8以上**で満たす

意味:

- 下限0.2近傍が集団の主要部分を占めない
- 上限10近傍にも押し付けない
- 生態をほぼ維持する
- 爆発的多数化が再現性高く起きない

「mean body_sizeを1.0へ戻す」は条件にしない。

---

## 16. B2/B3 一般化veto

B1 Greenの候補について、B2とB3をそれぞれ評価する。
各環境4 seedで:

1. COMPLETE >= 3/4
2. POP_HALT <= 1/4
3. EXTINCT <= 1/4
4. `p_high >= 0.50` の**上限支配runが1/4以下**

を満たすこと。

B2/B3では `p_low` をveto条件にしない。
異なる資源環境で小型が本当に有利なら、下限方向が再び選択されること自体は
環境依存の自然選択として許容する。

ただしpopulation haltは計算・生態の双方で極端な多数化の信号なのでveto対象とする。

---

## 17. C_core恒久値の選定規則

15候補を小さい順に並べ、

```text
B1主選定Green
AND B2 veto通過
AND B3 veto通過
```

を初めて満たす**最小の `C_core`**を恒久値候補として選ぶ。

これは「効果を出すために必要な最小変更」を選ぶ原則である。

### 17.1 同値・境界

候補格子上で最小値が選ばれるだけで、結果を見て中間値を補間して採用しない。
より細かい再校正が必要と判断した場合はExp11を変更せず、別実験として事前登録する。

### 17.2 1つも通らなかった場合

**NO SELECTION / REVIEW** とする。

Exp11結果を見てその場で式、body_size範囲、候補値、閾値を変更して再試行しない。
次の案は別バージョン/別実験として扱う。

---

## 18. 補助的な全体診断（選定条件ではない）

以下は解釈用に必ず出す。

- `C_core` とB1 seed中央値body_sizeのSpearman相関
- `C_core` とpopulationの関係
- 3環境の最終body_size曲線
- lower/upper boundary occupancy曲線
- extinction / POP_HALT heatmap
- late drift曲線
- Energy flow / maintenanceの関係

同じ `C_core` で環境ごとに異なるbody sizeが出れば、
「特定サイズを強制せず、環境依存のサイズ選択が生じた」強い支持材料になる。
ただし環境間差をGreenの必須条件にはしない。

---

# 停止・継続方針

## 19. 途中で人間判断を要求しない

今回の重要原則。

- Phase Aの値を見て候補を削らない
- B1の途中結果でB2/B3を止めない
- ある候補が明らかに失敗しても他候補は予定どおり走らせる
- 科学的STOP/REVIEWはworkflowを赤にしない
- 240 runすべてを最初から登録する

ただし**実験整合性の破壊**が見つかった場合のみworkflow failureとし、
そのrun結果を正式解析へ混ぜない。

---

# 保存

## 20. 保存物

`docs/実験結果保存方針.md` に従う。

GitHub:

```text
docs/Exp11_結果考察.md
experiments/<exp11_id>/NOTES.md
experiments/<exp11_id>/figures/
```

最低限の図:

1. C_core vs final body_size（3環境）
2. lower / upper boundary occupancy
3. final / peak population
4. extinction / POP_HALT heatmap
5. Phase A maintenance landscape
6. birth-state audit
7. 選定候補の代表body_size時系列

生データはGoogle Drive + Actions artifactへ保存する。

---

## 21. Exp11で結論できること / できないこと

### 結論できる

- core maintenance機構がサイズ境界張り付きを弱めるか
- どの候補が最小変更で主条件を満たすか
- 強すぎるC_coreが大型化・絶滅を起こすか
- 複数資源環境で大きな副作用があるか

### 結論できない

- 現実のLUCAのmaintenance power
- `M=1` の実際の細胞サイズ
- C_coreのSI単位での正確さ
- 温度を含む現実的なサイズ最適化
- 多細胞化や巨大化の妥当性
- C_core自体を進化させるべきか

これらは別軸として扱う。
