# Exp12 実験計画確定 — `bmr_core` は body_size の長期平衡を変えたのか

更新: 2026-09-02
状態: **事前登録確定 / 実装・実行前**

> 本書をExp12の正本とする。`docs/Exp12_実験計画案.md` は初版ドラフトであり、本書と矛盾する場合は本書を優先する。

関連:
- `docs/Exp12_レビュー反映判断.md`
- `docs/Exp12_実験計画案.md`（旧ドラフト）
- `docs/Exp11_実験計画案.md`
- `docs/Exp11_結果考察.md`
- `docs/Exp11_考察.md`
- `docs/V1.7_基礎維持代謝仕様案.md`
- `AGENTS.md`

---

# 1. 主目的

Exp11 B1では、10,000 tick時点のbody_sizeが `bmr_core` 増加とともに明瞭に大型側へ移動した。

しかし10,000 tickでは後半driftが残り、次の2仮説を識別できなかった。

## H_EQ: 平衡変更

`bmr_core` が小型化の相対的な生理メリットを変え、body_sizeの進化的な安定領域そのものを大型側へ移す。

予測:
- `bmr_core>0` のbody_size低下は時間とともに減速する
- tick軸でもgeneration軸でも後半傾きが0へ近づく
- 正の `bmr_core` 条件はbody_size下限より上の内部領域で安定する
- 高い `bmr_core` ほど内部平衡は概ね大型側になる

## H_DELAY: 単なる遅延

`bmr_core` は主に世代交代を遅らせ、10,000 tickでは大型に見えただけで、進化世代を十分進めれば同じ小型側へ向かう。

予測:
- tick軸では高 `bmr_core` ほど低下が遅く見える
- generation軸へ変換すると条件差が縮む
- 長期でもgenerationあたりのbody_size低下が持続する
- 複数の正 `bmr_core` 条件が最終的に下限側へ向かう

Exp12の目的はこの2仮説を区別すること。

**Exp12では恒久 `bmr_core` 値を選定しない。**

---

# 2. Exp11からの重要な前提

Exp11 B1 10k時点body_size中央値:

```text
bmr_core=0.000 -> 0.2164
0.050          -> 0.2577
0.075          -> 0.2716
0.100          -> 0.3356
0.150          -> 0.4088
0.200          -> 0.4389
0.300          -> 0.6273
```

一方、late_driftはB1でまだ大きかった。

またExp11 snapshotの予備確認では、世代進行速度が `bmr_core` によって大きく変わりうる。したがってExp12では `max_generation` だけでなくgeneration中央値/Q90を正式に測定する。

---

# 3. 実験構成

## 3.1 主実験: B1 light-only / light specialist

Exp11 B1と同じ環境・表現型を使う。

```text
placement      = random
light          = vertical standard
chemical       = off
light_abs      = 2.0 fixed
chemical_abs   = 0.3 fixed
```

### bmr_core 7水準

```text
0.000
0.050
0.075
0.100
0.150
0.200
0.300
```

理由:
- `0.000`: V1.6相当baseline
- `0.050, 0.075, 0.100`: Exp11の遷移域を密に見る
- `0.150, 0.200`: 中高値域のshapeを分解する
- `0.300`: サイズ非依存BMRとなる理論上端対照

初版の `0.030` は10k時点でbaselineとの差が小さく、長期shape判別の情報効率が低いため除外する。

### seed

```text
seed = 1..8
```

```text
7 × 8 = 56 run
```

Exp11と同一seedを使い、first-10k再現性とsame-seed比較を可能にする。

---

## 3.2 Method positive control: B2 chem-only / chemical specialist

目的はB2のbmr値選定ではなく、**stationarity判定法が、Exp11ですでにdriftの小さかった環境を正しく認識できるか**の確認。

```text
placement      = vent
light          = off
chemical       = vent flux 16
light_abs      = 0.3 fixed
chemical_abs   = 2.0 fixed
```

対象:

```text
bmr_core = 0.000, 0.100, 0.300
seed     = 1..5
```

```text
3 × 5 = 15 run
```

---

## 3.3 総run数

```text
B1 = 56
B2 = 15
-------
計 = 71 run
```

B3はExp12に含めない。

---

# 4. 共通科学条件

Exp11から、run長と対象条件集合以外の科学条件を変更しない。

```text
ticks                  = 50,000
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

V1.7 BMR式、mutation、繁殖、死亡、資源供給、行動則等をExp11から変更しない。

観測・集計の追加はRNG系列と科学挙動を変えてはならない。

---

# 5. Phase 0 — 正式dispatch前のHARD GATE

Phase 0が1項目でも失敗したら71-run正式matrixを起動しない。

## P0-1 Config完全性

Exp12全Configについて:

- `bmr_core` が保存JSON→ロードConfigで一致
- body_sizeだけが進化ON
- 他13遺伝子がcanonical `GENE_NAMES - {body_size}` と完全一致
- B1/B2の環境・表現型・placementがExp11テンプレートと一致
- `ticks=50000`
- `stats_interval=20`
- `snapshot_interval=1000`

を機械検証する。

## P0-2 Simulation smoke test

代表条件:

```text
B1 bmr=0.000 seed1
B1 bmr=0.100 seed1
B1 bmr=0.300 seed1
B2 bmr=0.000 seed1
```

についてSimulation初期化と短tick実行が正常であること。

## P0-3 first-10k same-seed再現性 preflight

上記代表B1 3条件を10,000 tickまで実行し、Exp11正式artifactと比較する。

比較対象:

- `stats.csv` のtick<=10,000の科学数値列
- snapshot 1,000–10,000
- population / body_size / generation / Energy / Matter関連の保存値

パス・実行時刻・run名等の非科学メタデータは除外してcanonical化する。

**科学数値に1箇所でも不一致があればHARD STOP。**

## P0-4 保存則・決定性

- Matter保存
- Energy台帳
- 同一seed決定性
- 観測追加でRNGが変わらない

を既存test + Exp12用testで確認する。

## P0-5 runtime preflight

50kは科学条件として固定するが、GitHub Actions timeout内に安全に収まることをdispatch前に確認する。

実施:

1. Exp11 10k Actions実績から条件別wall-timeを取得
2. 必要なら代表条件を20kまでruntime pilotする
3. 50k worst-caseを保守的に予測する

基準:

```text
job timeout                 = 350 min
formal dispatch safety line = predicted worst-case <= 300 min
```

300分を超える場合:

```text
RUNTIME_PREFLIGHT_FAIL / REVIEW
```

として停止する。

**その場でticksを30k等へ短縮して正式実験を続けない。**

## P0-6 CI

実装・Config・summarizer・workflow・testsをmainへ入れる前にローカルtestを完了する。

main上でCI Greenを確認後のみ正式dispatchする。

---

# 6. 正式runのintegrity gate

Phase 0代表条件だけでなく、正式71 runすべてで最初の10kをExp11とsame-seed比較する。

各Exp12 runについて対応するExp11条件が存在するため:

```text
Exp12 tick 0..10,000 == Exp11 tick 0..10,000
```

を要求する。

不一致run:

```text
INTEGRITY_FAIL
```

同条件の科学解析には使用しない。

複数runで系統的に不一致が出たらExp12全体を停止して原因調査する。

---

# 7. 保存・測定指標

## 7.1 body_size

各snapshotで:

- mean
- median
- Q10 / Q25 / Q75 / Q90
- `p_021 = fraction(body_size <= 0.21)`
- `p_023 = fraction(body_size <= 0.23)`
- `p_025 = fraction(body_size <= 0.25)`
- `p_high = fraction(body_size >= 9.5)`

0.21だけを下限判定に使わない。

## 7.2 generation

各snapshotで:

- generation median (`g50`)
- generation Q90 (`g90`)
- max_generation (`gmax`)

`gmax` は診断値であり単独の進化機会指標にしない。

## 7.3 ecology / Matter

- population final / peak
- births / deaths / death causes
- free nutrient total / fraction
- total biomass
- biomass_fraction
- corpse matter
- Energy flow by source
- Matter conservation residual

---

# 8. Tick-space trajectory解析

snapshotごとのpopulation median body_sizeを `b(t)` とする。

正式late windows:

```text
W1 = 20,000–30,000
W2 = 30,000–40,000
W3 = 40,000–50,000
```

各window内のsnapshot `b(t)` にOLS直線を当て、傾き `s_i` を求める。

比較しやすいよう10kあたり相対変化へ正規化する。

```text
S_i = s_i * 10,000 / max(0.2, median_body_size_in_window)
```

解釈:

```text
S < 0 : 小型化方向
S > 0 : 大型化方向
|S|=0.05 : 10kあたり約5%変化
```

主要late stationarity sentinel:

```text
|S3| <= 0.05
```

ただしこれ単独では平衡判定しない。

---

# 9. 減速判定

平衡へ向かう途中をdelayと誤分類しないため、3windowの傾き形状を見る。

## 9.1 CLEAR_DECELERATION

小型化方向 (`S1,S2,S3<0`) で:

```text
|S2| <= 0.8 * |S1|
and
|S3| <= 0.8 * |S2|
```

なら `CLEAR_DECELERATION`。

この状態で `|S3|>0.05` の場合は**delay判定にせず**:

```text
CONVERGING_NOT_PROVEN
```

とする。

## 9.2 SUSTAINED_NEGATIVE_DRIFT

```text
S1 < -0.05
S2 < -0.05
S3 < -0.05
and
|S3| >= 0.70 * |S1|
```

なら、明確な減速がない持続的小型化として `SUSTAINED_NEGATIVE_DRIFT` とする。

この閾値は正式run開始後に変更しない。

---

# 10. 漸近平衡fit — 診断

各COMPLETE runについて10k–50kのsnapshot median trajectoryへ:

```text
b(t) = b_inf + A * exp(-(t-10,000)/tau)
```

を制約付きfitする。

制約:

```text
0.2 <= b_inf <= 10
A >= 0   # 小型化軌跡を対象
tau > 0
```

保存:

- `b_inf`
- `tau`
- RMSE
- normalized RMSE
- fit success/failure

fitは補助診断であり、単独で `EQUILIBRIUM_SHIFT_SUPPORTED` を出さない。

次を `FIT_WINDOW_INSUFFICIENT` として記録する:

- optimizer failure
- パラメータが境界へ不自然に張り付く
- `tau > 13,333 tick`（fit window 40kの1/3超）
- normalized RMSE > 0.25

`FIT_WINDOW_INSUFFICIENT` は科学失敗ではなく「50kでも漸近位置を十分拘束できない」の意味。

---

# 11. Generation-space trajectory解析

これがH_EQとH_DELAYを分ける主要解析の1つ。

各snapshotについて:

```text
x = generation median g50
 y = median body_size
```

としてtrajectoryを作る。

同じg50が連続する場合は同generation内の最後のsnapshotを代表にし、generation増加区間だけを用いる。

## 11.1 generation late slope

各runの観測 `g50` rangeの最後30%をlate generation windowとする。

その区間でbody_sizeをgenerationに対してOLS fitし、10 generationあたり相対変化:

```text
S_gen = slope_per_generation * 10 / max(0.2, median_body_size_late_generation_window)
```

を出す。

generation範囲が小さすぎる場合:

```text
late generation windowの幅 < 10 generations
```

なら `GENERATION_WINDOW_INSUFFICIENT`。

主要sentinel:

```text
|S_gen| <= 0.05 -> generation-space stationary candidate
S_gen < -0.05   -> generationあたり小型化が継続
```

## 11.2 matched-generation same-seed比較

B1各正 `bmr_core` とsame-seed `bmr_core=0` を:

```text
g50 = 10, 20, 30, ...
```

の共通到達generationで比較する。

snapshot間は線形補間する。

保存:

```text
Δb(g, seed, bmr) = b_positive_bmr(g) - b_bmr0(g)
```

共通generationが少なくても無理な外挿はしない。

これにより「tickだけ遅い」のか「同じ進化世代を経てもサイズ差が残る」のかを見る。

---

# 12. Matter coupling診断

30k–50kの1k snapshot差分を使う。

各seedで:

```text
Δbody_size vs Δfree_nutrient_fraction
Δbody_size vs Δbiomass_fraction
Δbody_size vs Δpopulation
```

のSpearman `rho` とp値を求める。

per-seed strong coupling:

```text
|rho| >= 0.60 and p < 0.05
```

同一指標・同一符号のstrong couplingがB1同bmr条件で4/8 seed以上なら:

```text
MATTER_COUPLED
```

を付与する。

これは `INTEGRITY_FAIL` ではない。

ただし `MATTER_COUPLED` 条件で平衡shiftが見えても、結論は:

> bmr_coreを含む生態フィードバック下で平衡が変化した

までとし、BMRの直接的サイズ選択だけへ単純帰属しない。

---

# 13. per-run科学分類

integrity OKかつCOMPLETE runのみ分類する。

## 13.1 `INTERIOR_EQUILIBRIUM`

すべて満たす:

```text
|S3| <= 0.05
|S_gen| <= 0.05
late median body_size > 0.23
late p_023 < 0.50
```

かつ `GENERATION_WINDOW_INSUFFICIENT` でない。

fitが成功していれば `b_inf` を併記するが必須条件にはしない。

## 13.2 `LOWER_BOUND_EQUILIBRIUM`

```text
|S3| <= 0.05
|S_gen| <= 0.05
and
(late median body_size <= 0.23 or late p_023 >= 0.50)
```

## 13.3 `DELAY_CONTINUES`

```text
SUSTAINED_NEGATIVE_DRIFT
and
S_gen < -0.05
```

を満たす。

つまりtickでもgenerationでも小型化が持続していることを要求する。

## 13.4 `CONVERGING_NOT_PROVEN`

以下のいずれか:

- `CLEAR_DECELERATION` だがまだ `|S3|>0.05`
- tickはstationary候補だがgeneration軸がまだ負
- generationはstationary候補だがtick軸がまだ負
- fitは有限漸近を示唆するがstationarity gate未達

これは**平衡変更否定ではない**。

## 13.5 `WINDOW_INSUFFICIENT`

- generation window不足
- trajectoryの符号が不安定
- fit不安定かつ傾き判定も一貫しない
- その他、上記4分類へ安全に入らない

のいずれか。

---

# 14. 条件単位判定 — B1

## 14.1 baseline (`bmr_core=0`) の長期小型化確認

8 seed中5 seed以上で:

```text
LOWER_BOUND_EQUILIBRIUM
or
late median <= 0.23
or
late p_023 >= 0.50
```

なら:

```text
BASELINE_LOWER_BOUND_SIGNAL = PASS
```

未達なら:

```text
BASELINE_WINDOW_INSUFFICIENT
```

とし、正bmrとの「下限から内部へ平衡が移った」という全体結論は保留する。

## 14.2 正bmr条件の平衡shift候補

各 `bmr_core>0` について8 seed中6 seed以上が:

```text
INTERIOR_EQUILIBRIUM
```

かつ `DELAY_CONTINUES` が1 seed以下なら:

```text
BMR_LEVEL_INTERIOR_EQ = PASS
```

## 14.3 delay条件

同bmrの8 seed中6 seed以上が:

```text
DELAY_CONTINUES
```

なら:

```text
BMR_LEVEL_DELAY = PASS
```

## 14.4 それ以外

```text
BMR_LEVEL_INCONCLUSIVE
```

後付けで5/8等へ緩和しない。

---

# 15. B2 method-control gate

B2 `bmr_core=0` の5 seed中4 seed以上が:

```text
|S3| <= 0.05
```

かつgeneration解析可能なseedでは `|S_gen|<=0.05` を概ね満たすことを期待する。

4/5未達なら:

```text
METHOD_CONTROL_FAIL / REVIEW
```

として、Exp12のstationarity classifier自体を再検討する。

B2 0.1 / 0.3は追加のsanity trajectoryとして報告するが、正式bmr選定には使用しない。

---

# 16. Exp12全体のSCIENTIFIC_VERDICT

優先順に判定する。

## A. integrity / method failure

```text
INTEGRITY_FAIL
METHOD_CONTROL_FAIL
RUNTIME_PREFLIGHT_FAIL
```

が全体判断を妨げる場合:

```text
SCIENTIFIC_VERDICT = INVALID_OR_METHOD_REVIEW
```

## B. 平衡変更支持

以下を満たす:

1. `BASELINE_LOWER_BOUND_SIGNAL = PASS`
2. 正bmrの少なくとも1水準で `BMR_LEVEL_INTERIOR_EQ = PASS`
3. B2 method control PASS
4. integrity OK

なら:

```text
SCIENTIFIC_VERDICT = EQUILIBRIUM_SHIFT_SUPPORTED
```

`MATTER_COUPLED` が付く場合は:

```text
EQUILIBRIUM_SHIFT_SUPPORTED_WITH_ECOLOGICAL_COUPLING
```

と注記する。

## C. 単なる遅延支持

正bmrの中心〜高値代表:

```text
0.100
0.200
0.300
```

のうち少なくとも2水準で `BMR_LEVEL_DELAY = PASS`、かつ `BMR_LEVEL_INTERIOR_EQ` が0水準なら:

```text
SCIENTIFIC_VERDICT = DELAY_SUPPORTED
```

## D. 50kでも判定不能

収束減速が多いがstationarityまで届かない、baselineが未収束、generation window不足などの場合:

```text
SCIENTIFIC_VERDICT = WINDOW_INSUFFICIENT / REVIEW
```

これは失敗ではなく正式な科学結果。

---

# 17. Actions実行設計

正式71 runを1回の `workflow_dispatch` で最初から登録する。

```text
max-parallel = 20
job timeout  = 350 min
```

ただしP0 runtime gate PASS後のみ。

run statusはExp11と同じ:

```text
COMPLETE
EXTINCT
POP_HALT
INCOMPLETE_RESOURCE
INTEGRITY_FAIL
```

- EXTINCT / POP_HALT = 科学的結果
- timeout / runner中断 / artifact欠落 = `INCOMPLETE_RESOURCE`
- 同一SHA・同一Configによる技術的再実行のみ許可
- scientific thresholdや候補値は正式dispatch後に変更しない

collectorは `if: always()` 等で完了済みartifactを可能な限り回収する。

---

# 18. Sonnet 5 実装要求

実装者は最低限、以下を用意する。

```text
tools/exp12_common.py
tools/make_exp12_configs.py
tools/check_exp12.py
tools/summarize_exp12.py
configs/exp12/*.json
.github/workflows/exp12.yml
tests/test_exp12_configs.py
tests/test_exp12_aggregation.py
```

必要ならtrajectory fit専用moduleを追加してよい。

## checker必須事項

- Config数・条件集合
- fixed genes canonical一致
- bmr_core round-trip
- seed / environment / path整合
- run completeness
- first-10k Exp11 canonical comparison
- 同一formal SHA / numeric environment

## summarizer必須出力

最低限:

```text
exp12_runs.csv
exp12_b1_by_seed.csv
exp12_b1_by_bmr.csv
exp12_b2_control.csv
exp12_tick_slopes.csv
exp12_generation_slopes.csv
exp12_asymptotic_fit.csv
exp12_matter_coupling.csv
exp12_verdict.txt
```

plot:

1. B1 body_size vs tick（bmr別、seed帯）
2. B1 body_size vs median generation
3. 20–30 / 30–40 / 40–50k normalized slope
4. fitted `b_inf` / `tau` diagnostics
5. B2 positive-control trajectories
6. Matter coupling diagnostic

---

# 19. テスト要求

最低限:

1. 71条件matrix件数テスト
2. B1 7値×8seed / B2 3値×5seed完全一致
3. fixed_genes canonical test
4. Simulation smoke test
5. nonzero bmr_core Config round-trip
6. snapshot CSV実形式fixtureでgeneration median/Q90/max集計
7. trajectory slopeの符号テスト
8. 減速trajectoryが `DELAY_CONTINUES` へ誤分類されない回帰テスト
9. sustained linear declineが `DELAY_CONTINUES` になるテスト
10. stationary interior / lower-bound fixture分類テスト
11. generation-window不足テスト
12. asymptotic fit success/failure/boundaryテスト
13. Matter coupling difference-correlationテスト
14. first-10k mismatchがINTEGRITY_FAILになるテスト
15. 欠落・重複artifactで集計を確定しないテスト

全testsを本番dispatch前に実行する。

---

# 20. 実装者が独自変更してはいけない事項

正式実行前であっても、本書の科学設計を「良さそうだから」という理由で独自変更しない。

特に:

- bmr_core水準
- seed数
- 50k tick
- B1/B2条件
- 5% stationarity sentinel
- 0.8/0.7 deceleration/drift閾値
- 6/8条件判定
- 0.23 lower-bound sentinel
- scientific verdictロジック

を変更したい場合は実装を止め、人間レビューへ戻す。

ただし、科学挙動を変えない純粋な実装詳細・コード整理・テスト追加・artifact整理は実装者判断で行ってよい。

---

# 21. 実行順序

```text
1. 本書・レビュー判断・AGENTSを読む
2. Exp11正式artifactへのアクセス確認
3. Exp12実装
4. ローカルtests / checker
5. P0 first-10k再現性
6. P0 runtime preflight
7. PR / CI Green
8. mainへマージ
9. 正式71-run workflow_dispatch
10. collector / integrity check
11. preregistered summarizerで判定
12. 結果・考察をGitHubへ保存
```

正式run開始後に結果を見て判定ロジックを修正しない。

---

# 22. Exp12終了時に答えること

Exp12の最終報告は最低限、次の4点を明示する。

1. `bmr_core` によりbody_sizeの**長期平衡が変化した証拠があるか**
2. 見かけの大型化を**世代交代遅延だけで説明できるか**
3. 50kでまだ収束していない条件はどれか
4. Matter制約との結合が結論へどの程度影響したか

そして、Exp12の結果だけで恒久値を勝手に採用しない。
