# Exp11 実験計画 — `bmr_core` と body size 進化

更新: 2026-09-01
状態: **事前登録確定 / 未実装 / 未実行**

関連:
- `docs/V1.7_基礎維持代謝仕様案.md`
- `docs/V1.7_Exp11_レビュー判断.md`
- `docs/LUCA参照モデル方針.md`
- `docs/Exp10_結果考察.md`

---

## 1. 目的

V1.7候補の縮小不能な基礎維持代謝 `bmr_core` を導入し、次を検証する。

1. 現行世界で示唆された `body_size=0.2` 方向への強い小型化圧を弱められるか
2. body size の上下限へ一方向に張り付かず、内部領域に進化状態を作れるか
3. 同じ `bmr_core` でも資源環境ごとに異なるbody sizeが選択される余地を残せるか
4. 生態を壊さず、小型多数化による計算量増大も副次的に緩和できるか

**populationを小さくすること、body_sizeを1.0へ戻すことは選定目的にしない。**
選定対象は、境界への一方向張り付きを解消するために必要な**最小の生理変更**である。

Exp11で変える世界パラメータは `bmr_core` だけ。進化可能遺伝子は `body_size` だけとし、他13遺伝子は固定する。

---

## 2. V1.7候補式

```text
BMR = bmr_core + (bmr_coef - bmr_core) * M^0.75
bmr_coef = 0.3
0 <= bmr_core <= 0.3
```

`M` は現在の身体Matter (`org.matter`)。

候補15水準:

```text
0.000, 0.005, 0.010, 0.015, 0.020,
0.025, 0.030, 0.040, 0.050, 0.060,
0.075, 0.100, 0.150, 0.200, 0.300
```

低値側を密に取り、理論的に変化が見込まれる0.03–0.10を細かく覆う。0.300はBMRがサイズ非依存になる上端対照である。

`p_high`（上限張り付き）は安全用sentinelとして測るが、理論検算では `bmr_core=0.3` でも効率最小点がbody size上限10より十分下にあるため、**`p_high`を通過したこと自体を「大型化の問題がない強い証拠」とは解釈しない。**

---

## 3. 実行前提 — V1.6を先に閉じる

Exp10で採用した現行参照値:

```text
memory_tau    = 10
response_gain = 64
```

2026-09-01時点では通常defaultの `response_gain` が16のままなので、V1.7とは別の確定処理として先に:

1. `response_gain=64` をV1.6 defaultへ反映
2. test / CI基準を更新
3. `v1.6-final` branchを保存
4. その確定commitをV1.7の親にする

その後にV1.7 `bmr_core` を実装する。

正式Exp11を起動する前に、**V1.7実装、45 Config、`.github/workflows/exp11.yml` をmainへマージ済み**でなければならない。`workflow_dispatch`をfeature branch上だけに置かない。

正式run開始後は、全255 runで同一Git SHA・同一数値環境を固定し、科学コード・Config生成則・判定ロジックを変更しない。

---

# Phase 0 — 実装・回帰・Config健全性

Phase 0は正式run開始前の停止条件。1項目でも失敗したらPhase Bを起動しない。

## P0-1 `bmr_core=0` 完全回帰

`v1.6-final` と同一Config・同一seedで、`bmr_core=0` のV1.7が既存goldenケースと完全一致すること。

## P0-2 式の境界

```text
M=1.0              -> 任意の合法bmr_coreでBMR=0.3
bmr_core=0.0       -> V1.6式と一致
bmr_core=0.3       -> BMR=0.3でサイズ非依存
bmr_core<0 / >0.3  -> ValueError
```

## P0-3 Energy / Matter / RNG / 決定性

- Energy台帳整合
- Matter厳密保存
- 同一seed決定性
- 観測追加がRNG系列・分岐を変えない

## P0-4 body_size-only evolution

Phase B全45 Config（15 `bmr_core` × 3環境）について、`fixed_genes` がbody_size以外の13遺伝子をすべて含み、body_sizeのみ含まないことを機械検証する。

## P0-5 Config silent-drop防止

`bmr_core` を以下すべてへ含める。

- `Config`
- 保存 `config.json`
- run summary / fingerprint / collect table

非ゼロ値（例 `bmr_core=0.05`）のJSON round-trip testを必須とし、生成JSONの値とロード後Config値が一致することを全45 Configで検証する。未知キーが黙って捨てられて `bmr_core=0` として走る事故を許容しない。

---

# Phase A — 安価な決定論監査

Phase Aは**候補削減・途中判断には使わない**。全15候補を必ずPhase Bへ送る。目的はPhase B結果を解釈するための予測を実行前に固定すること。

## A1 maintenance landscape

現在Matter:

```text
M = 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 0.80,
    1.00, 1.50, 2.00, 3.00, 5.00, 7.50, 10.00
```

全15 `bmr_core`、各診断表現型について次をCSV/図へ出す。

- BMR（core / scalable内訳）
- organ / sense / membrane / resistance upkeep
- movement cost（静止 / 通常wander）
- total maintenance
- `total maintenance / M^(2/3)`
- `bmr_core / total maintenance`
- 通常wander速度

`M=0.8` は正式runの `initial_matter=0.8` なので必須。`M=1`だけ不変でも、初期個体では `bmr_core>0` によりBMRが上がることを明示的に監査する。

## A2 出産直後の親子状態

対象target size:

```text
0.2, 0.5, 1.0, 2.0, 5.0, 10.0
```

各targetについて、繁殖時parent matterを:

```text
0.8 × target, 1.0 × target, 1.2 × target
```

で監査する。実際の `_try_reproduce` と同じ順序で、親子のMatter / Energy / Energy capacity / BMR / total maintenance / intake=0時のEnergy reserveを出す。`child_matter_frac=0.35`、`birth_overhead=2.0`、`reproduction_investment=0.4`等は正式Config値を使う。

## A3 reproductive-opportunity proxy

小型化圧には維持効率だけでなく、短い世代時間と高速移動が含まれるため、世界シミュレーションを使わない決定論診断を追加する。

標準化条件:

```text
adult matter = target body_size
start energy = 0.5 * E_max
matter       = 繁殖条件を満たす
phi          = 1
wander       = 通常値
gross intake proxy I = k * M^(2/3)
k = 0.6, 1.2, 2.4
```

各 `bmr_core × M × k` について:

```text
net = I - total_maintenance
```

`net>0`なら `E=0.6*E_max` 到達までのtick `T` と `1/T` を出し、`net<=0`なら `T=inf` とする。wander速度も併記する。

これは**適応度ではなくreproductive-opportunity diagnostic**であり、候補選定条件には使わない。

---

# Phase B — 正式 body_size-only evolution

## 4. 共通条件

```text
ticks                  = 10,000
initial_population     = 100
initial_energy         = 50.0
initial_matter         = 0.8
initial genome         = INITIAL_GENOME + 通常standing variation
body_size              = 進化ON
other 13 genes         = 完全固定
memory_tau             = 10
response_gain          = 64
stats_interval         = 20
snapshot_interval      = 1,000
max_population_halt    = 10,000
```

`max_population_halt=10,000` は生態ルールではない。10,000個体到達時に個体を殺さず、状態を保存してrunを終了する計算安全装置である。

## 5. B1 Light-only / light specialist — 主選定

Exp10正式B1 treatmentをテンプレートにし、`bmr_core`追加とbody_size-only evolution以外は維持。

```text
placement      = random
light          = vertical standard
chemical       = off
light_abs      = 2.0 fixed
chemical_abs   = 0.3 fixed
seed           = 1..8
```

```text
15 × 8 = 120 run
```

## 6. B2 Chemical-only / chemical specialist — 一般化/veto

Exp10正式B2 treatmentをテンプレートにする。

```text
placement      = vent
light          = 0
chemical       = vent flux 16
light_abs      = 0.3 fixed
chemical_abs   = 2.0 fixed
seed           = 1..5
```

```text
15 × 5 = 75 run
```

B2は低populationによる確率絶滅が起こりやすいため、B3より1 seed多くする。

## 7. B3 Mixed / generalist — 一般化/veto

Exp10正式B5 treatmentをテンプレートにする。

```text
placement      = random
light          = vertical standard
chemical       = vent flux 16
generalist     = light_abs=1.0 / chemical_abs=1.0 fixed
seed           = 1..4
```

```text
15 × 4 = 60 run
```

## 8. 総run数・Actions

```text
B1 = 120
B2 =  75
B3 =  60
---------
計 = 255 run
```

1つのmatrix（255 job）として1回の `workflow_dispatch` で全条件を最初から登録する。`max-parallel=20`。

Exp10 exploratoryの旧最悪実績40分 / 10,000 tick / runを全runへ悲観的に当てても:

```text
ceil(255/20) × 40 min = 13 × 40 = 520 min ≈ 8時間40分
```

ユーザーが確保している約10時間枠に約1時間20分の余裕を残す。

各matrix jobの `timeout-minutes` は **350分**を基準とする。timeout / runner interruption / artifact欠落は科学的STOPではなく `INCOMPLETE_RESOURCE` として扱う。collectorは `if: always()` 等で可能な限り完了済み結果を集約し、技術的不完了を科学判定と分離する。同一SHA・同一Configで技術的不完了jobだけ再実行してよい。

---

# 9. run状態の定義

各runは次のいずれかに分類する。

```text
COMPLETE             10,000 tick到達
EXTINCT              population=0
POP_HALT             population 10,000到達で安全停止
INCOMPLETE_RESOURCE  timeout / runner中断 / output欠落
INTEGRITY_FAIL       Config・環境・固定遺伝子・保存則等の整合性違反
```

EXTINCT / POP_HALTは科学的結果でworkflow failureにしない。
INCOMPLETE_RESOURCEは技術的不完了で科学的成功/失敗へ数えない。
INTEGRITY_FAILは正式結果として無効。

POP_HALTの `final` は `finalize()` が保存した**halt時最終snapshot**と定義し、そこからfinal body-size統計と `p_low/p_high` は報告してよい。一方、COMPLETEでないrunのlate-window / stationarityは **N/A** とする。

---

# 10. 測定指標

## body size

- final mean / median / Q10 / Q25 / Q75 / Q90
- `p_low = fraction(body_size <= 0.21)`
- `p_high = fraction(body_size >= 9.5)`
- COMPLETE runのみ:
  - `m1` = mean body_size over tick 6,000–8,000
  - `m2` = mean body_size over tick 8,000–10,000
  - `late_drift = abs(m2-m1) / max(0.2, abs(m2))`

`p_low/p_high` はsnapshotから計算する。finalizeによる最終snapshotを必ず保存する。

## 進化機会

- final `max_generation`
- same-seed `bmr_core=0` の `max_generation=g0`
- body_size以外13遺伝子のvariance=0

## 生態

- final / peak population
- births / deaths / death cause
- Energy flow by source
- free nutrient total (`nutrient_total`)
- total biomass
- corpse matter
- `biomass_fraction = total_biomass / total_system_matter`
- free nutrient fraction
- Matter保存

Matter指標は「Energy側の `bmr_core` が効かなかった場合にMatter制限だったか」を解釈する診断であり、候補選定条件には使わない。

POP_HALTと`p_low`はMatter保存下で強く相関しうるため、独立した2証拠として二重に解釈しない。

---

# 11. 事前登録判定

## 11.1 B1 `bmr_core=0` 対照妥当性

旧Exp10 exploratory B1は複数遺伝子が自由だったため、body_size-onlyでも小型化圧が存在することをまず内部対照で確認する。

`bmr_core=0` B1について、各seedの最終利用可能snapshotで:

```text
p_low >= 0.50
```

を「small-size signal」とする。

**8 seed中5 seed以上**でsmall-size signalが出ることを対照妥当性条件とする。POP_HALT seedも最終snapshotが正常ならこの判定には使用できる。

未達なら:

```text
CONTROL_NOT_REPRODUCED
SCIENTIFIC_VERDICT = NO_SELECTION / REVIEW
```

とし、全255 runは最後まで集約するが恒久 `bmr_core` は選ばない。

## 11.2 B1 candidate per-seed Green

`bmr_core>0` の各B1 seedは、以下を**すべて**満たしたときper-seed Green。

1. `COMPLETE`（10,000 tick到達）
2. `p_low < 0.25`
3. `p_high < 0.25`
4. `max_generation >= max(5, ceil(0.5 * g0))`
   - `g0` は同一seed・B1・`bmr_core=0` のfinal `max_generation`
5. `late_drift <= 0.10`
6. body_size以外13遺伝子variance=0、その他integrity OK

第4条件は「進化が遅すぎて初期値付近に残っただけ」をGreenにしないための相対的な進化機会条件。第5条件のstationarityは「10,000 tick内で明らかな一方向driftが残る状態」をGreenにしないための運用条件であり、永続平衡の証明ではない。

候補の **B1 Green** はper-seed Greenが **7/8以上**。

## 11.3 持続的転換（3-point persistence）

単発のseed運で「最初に通った候補」を選ばない。

候補 `b_i` は、候補列上で:

```text
b_i, b_(i+1), b_(i+2)
```

の**連続3水準すべてがB1 Green**のときだけ `TRANSITION_ELIGIBLE` とする。上に2候補が残っていない末端候補はこの規則では選定対象にならない。

「それより大きい全候補Green」は要求しない。極端に大きな `bmr_core` が別の理由で生態を壊しても、妥当な中間転換点を無効化しないためである。

## 11.4 B2/B3 baseline viability

各一般化環境の `bmr_core=0` で、healthy COMPLETE数を確認する。

```text
B2: >= 3/5
B3: >= 3/4
```

healthy COMPLETE = `COMPLETE`かつintegrity OK。

未達ならその一般化環境自体の判定能力が不足しているため、恒久値は選ばず `NO_SELECTION / REVIEW`。

## 11.5 B2/B3 environmental veto

`TRANSITION_ELIGIBLE`候補についてのみ、B2/B3で重大な副作用をvetoする。

環境ごとに `n` をseed数、`H0` を同環境 `bmr_core=0` のhealthy COMPLETE数、`Hc`を候補のhealthy COMPLETE数とする。

次のどちらかでveto:

```text
A) Hc <= floor(n/2) かつ H0 - Hc >= 2
B) healthy COMPLETE seedの過半数で p_high >= 0.25
```

単にpopulationが小さい、1 seedが絶滅した、B1と違うbody sizeへ進化した、という理由ではvetoしない。B2/B3の`p_low`も報告するが、低body sizeがその環境で自然に選択される可能性を残すため必須条件にはしない。

## 11.6 恒久値選定

以下を順番に機械判定する。

1. Phase 0 integrity Green
2. B1 `bmr_core=0` 対照妥当性 Green
3. B2/B3 baseline viability Green
4. `TRANSITION_ELIGIBLE`候補を小さい順に列挙
5. B2/B3 vetoを受けた候補を除外
6. **残った最小 `bmr_core` を恒久値候補として選定**

候補が残らない場合:

```text
SCIENTIFIC_VERDICT = NO_SELECTION / REVIEW
```

とする。その場で式・候補値・seed・閾値を変更せず、Exp11はその結果で閉じる。

---

# 12. 結論できること / できないこと

Exp11で結論できるのは、**他13遺伝子を固定しbody_sizeだけ進化させた条件で**、`bmr_core` が極端な小型化圧へどう作用するか、および一般化3環境で重大な副作用があるかである。

以下は結論しない。

- 全14遺伝子を共進化させたときの最終body size
- `bmr_core` が地球生命の実測絶対値と一致すること
- body_size=1がLUCAそのものを再現すること
- temperature等を追加した将来世界での最適値
- 10,000 tickより長期の永続平衡

---

# 13. 実装・保存要件

- `exp11.yml` / 45 Config / checker / summarizer / testsを**mainへマージしてから**正式dispatch
- run単位で seed / Git SHA / 数値環境 / config fingerprint / `bmr_core` / statusを保存
- 科学的STOP/REVIEWと技術的不完了・integrity failureを分離
- 全生データ・全画像はGoogle Drive / Actions artifactへ保存
- GitHubへ `docs/Exp11_結果考察.md`、`experiments/<exp11_id>/NOTES.md`、集計plot、代表図、READMEを保存
- 途中結果を見て候補・判定基準を変更しない
