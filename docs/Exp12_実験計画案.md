# Exp12 実験計画案 — `bmr_core` が body_size の進化平衡を変えたのか、単に小型化を遅延させたのか

更新: 2026-09-02
状態: **レビュー前ドラフト / 未実装 / 未実行**

関連:
- `docs/Exp11_実験計画案.md`
- `docs/Exp11_結果考察.md`
- `docs/V1.7_基礎維持代謝仕様案.md`
- `AGENTS.md`

---

## 1. 背景

Exp11では、V1.7候補の縮小不能な基礎維持代謝 `bmr_core` を導入し、body_sizeのみを進化可能にした。

B1 light-only環境では、10,000 tick時点のbody_sizeが `bmr_core` 増加とともに系統的に大きくなった。

代表的なExp11 B1中央値:

```text
bmr_core=0.000 -> body_size median 0.2164
bmr_core=0.030 -> body_size median 0.2334
bmr_core=0.050 -> body_size median 0.2577
bmr_core=0.075 -> body_size median 0.2716
bmr_core=0.100 -> body_size median 0.3356
bmr_core=0.150 -> body_size median 0.4088
bmr_core=0.200 -> body_size median 0.4389
bmr_core=0.300 -> body_size median 0.6273
```

一方、Exp11は10,000 tick時点でもB1の `late_drift` が大きい。

```text
bmr_core=0.000 -> late_drift median 0.3952
bmr_core=0.050 -> late_drift median 0.3149
bmr_core=0.100 -> late_drift median 0.3055
bmr_core=0.150 -> late_drift median 0.2374
bmr_core=0.200 -> late_drift median 0.2438
bmr_core=0.300 -> late_drift median 0.1264
```

したがってExp11だけでは、観測された大型側へのシフトが次のどちらかを区別できない。

1. **平衡変更**: `bmr_core` によりbody_sizeの進化的な安定領域そのものが大型側へ移動した。
2. **単なる遅延**: 小型化速度が遅くなっただけで、十分長く走らせれば最終的には `body_size≈0.2` へ向かう。

Exp12はこの識別を目的とする。

---

# 2. 主目的

Exp12の主目的は、**`bmr_core` によりbody_sizeの長期進化平衡が実際に変化したかを判定すること**である。

具体的には、長期runにおいてbody_sizeの時間変化を追跡し、

- `bmr_core>0` 条件でbody_sizeが内部領域に収束するのか
- それとも時間とともに継続して下がり、最終的に下限側へ近づくのか

を判別する。

Exp12では**新しい世界パラメータは導入しない**。

Exp12はV1.7候補値を広く探索する実験ではなく、Exp11で観測された現象の意味を確定するための**長期検証実験**である。

---

# 3. Exp12で答える問い

## Q1. `bmr_core=0` では長期的にbody_size下限へ近づくか

Exp11の `bmr_core=0` は10,000 tick時点で `p_low>=0.50` を満たさなかったが、body_sizeはすでにかなり小さい。

Exp12では、より長期に追跡することで、現行BMR式に本当に小型化圧が存在するかを確認する。

## Q2. `bmr_core>0` ではbody_size低下が停止するか

各代表 `bmr_core` 条件について、後半区間のbody_size変化率が時間とともに0へ近づくかを確認する。

## Q3. 収束位置は `bmr_core` に応じて系統的に変わるか

単なる遅延でなければ、十分長期では代表値ごとに異なるbody_size領域へ収束することが期待される。

## Q4. 見かけの収束が「世代交代不足」によるものではないか

`bmr_core` 増加により個体が大型化すると、Energy容量・繁殖必要量・寿命等を通じて世代交代が遅くなる可能性がある。

そのためtickだけでなく `max_generation` を併記し、長期runでも進化機会が確保されているかを確認する。

---

# 4. 仮説

## H1: 平衡変更仮説

`bmr_core` がbody_sizeの選択圧そのものを変えているなら、

- `bmr_core=0` は長期的にbody_size下限方向へ進む
- `bmr_core>0` は値に応じた内部領域でbody_size低下が停止する
- 後半windowの傾きは時間とともに0へ近づく
- 高 `bmr_core` ほど収束body_sizeは大きい

と予測する。

## H2: 単純遅延仮説

`bmr_core` が主として世代時間を延長しただけなら、

- `bmr_core>0` でも十分長期ではbody_size低下が継続する
- tick基準では高 `bmr_core` 条件ほど低下が遅く見える
- 世代数基準でbody_sizeを比較すると条件差が縮小する
- 長期的には複数の `bmr_core` 条件が同じ小型領域へ向かう

と予測する。

---

# 5. 実験対象環境

## 5.1 主実験はB1のみ

Exp12の主問いは「Exp11 B1で観測された小型化抑制が平衡変更か遅延か」である。

したがって主実験は、Exp11の主選定環境であったB1 light-only / light specialistに限定する。

```text
placement      = random
light          = vertical standard
chemical       = off
light_abs      = 2.0 fixed
chemical_abs   = 0.3 fixed
```

理由:

1. Exp11で `bmr_core` に対するbody_size応答が最も明瞭だった
2. B2/B3まで長期化するとrun数と計算時間が大きく増え、主問いに対する情報効率が低い
3. Exp12で平衡変更が確認できた後、最終候補値に対してB2/B3長期確認を別途実施できる

Exp12ではB2/B3を主判定へ含めない。

---

# 6. `bmr_core` 代表値

Exp11の15水準をすべて再実行せず、形状を保持できる代表7水準へ絞る。

```text
0.000
0.030
0.050
0.075
0.100
0.150
0.300
```

選定理由:

- `0.000`: 現行式対照
- `0.030`: 低値域。Exp11では効果がまだ小さい
- `0.050`: 低〜中値域の代表
- `0.075`: 0.05と0.10の間の遷移領域
- `0.100`: Exp11でbody_sizeシフトが明瞭化した代表点
- `0.150`: 中高値域。内部領域への大型化が明瞭
- `0.300`: BMRがサイズ非依存になる理論上端対照

`0.200` はExp11で0.150と0.300の中間傾向を示しており、主問いに対する追加情報量より計算コストを優先して除外する。

**レビューで代表点の不足が指摘された場合のみ、0.200追加を検討する。実行開始後は追加しない。**

---

# 7. seed

Exp11 B1と同じseedを用いる。

```text
seed = 1..8
```

理由:

- Exp11とのsame-seed比較を可能にする
- seed間ばらつきが比較的大きいため、8 seedを維持する
- 新規seedを混ぜず、10,000 tickまでの挙動と長期挙動を直接比較しやすくする

総run数:

```text
7 bmr_core × 8 seed = 56 run
```

---

# 8. 実行時間

## 8.1 正式run長

```text
ticks = 50,000
```

とする。

10,000 tickではlate driftが残っていたため、Exp11の5倍まで延長する。

50,000 tickを1本の連続runとして実行し、途中の10k刻みを観測点として利用する。

```text
10,000
20,000
30,000
40,000
50,000
```

同じseed・同じ世界を複数の独立runとして各tickで終了させるのではなく、**50,000 tickまで1本で走らせる**。

これにより、追加runを増やさず長期trajectoryを取得できる。

## 8.2 snapshot

```text
stats_interval    = 20
snapshot_interval = 1,000
```

をExp11から維持する。

最低50 snapshot / runが得られ、5k〜10k windowの平均と傾き評価に十分な時間分解能を確保する。

---

# 9. 共通条件

Exp11 B1から、`ticks` と実験対象 `bmr_core` 集合以外を変更しない。

```text
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

V1.7コード本体、BMR式、生態ルール、mutation、繁殖、死亡、資源供給等はExp11から変更しない。

**Exp12実行前に、Exp11結果以後のコード変更が科学挙動へ影響していないことを確認する。**

---

# 10. run状態

Exp11と同じ分類を使う。

```text
COMPLETE             50,000 tick到達
EXTINCT              population=0
POP_HALT             population 10,000到達で安全停止
INCOMPLETE_RESOURCE  timeout / runner中断 / output欠落
INTEGRITY_FAIL       Config・環境・固定遺伝子・保存則等の整合性違反
```

EXTINCT / POP_HALTは科学的結果。
INCOMPLETE_RESOURCEは技術的不完了。
INTEGRITY_FAILは正式結果として無効。

COMPLETEでないrunでは、その後の未観測windowのstationarity判定はN/Aとする。

---

# 11. 主測定指標

## 11.1 body_size trajectory

各snapshotで:

- mean
- median
- Q10 / Q25 / Q75 / Q90
- `p_low = fraction(body_size <= 0.21)`
- `p_high = fraction(body_size >= 9.5)`

を保存・集計する。

主解析はmeanとmedianの両方を使う。片方だけで収束を判定しない。

## 11.2 10k block平均

各runについて以下を定義する。

```text
B1 = mean body_size over tick 10,000–20,000
B2 = mean body_size over tick 20,000–30,000
B3 = mean body_size over tick 30,000–40,000
B4 = mean body_size over tick 40,000–50,000
```

初期0–10,000はExp11との比較用区間として扱い、stationarity主判定には使わない。

## 11.3 block drift

各連続block間について:

```text
drift_12 = (B2 - B1) / max(0.2, abs(B2))
drift_23 = (B3 - B2) / max(0.2, abs(B3))
drift_34 = (B4 - B3) / max(0.2, abs(B4))
```

符号を保持する。

- 負: body_size低下
- 正: body_size増加
- 0付近: 定常

Exp11の `late_drift` は絶対値だったため方向を失っていた。Exp12では**signed drift**を主に使う。

併せて絶対値も報告する。

## 11.4 後半線形傾き

各runについて tick 20,000–50,000 のsnapshot mean body_sizeに対して単純線形回帰を行い、

```text
slope_tick = body_size change per 10,000 tick
```

として正規化して報告する。

回帰は状態記述のための診断であり、非線形trajectoryを直線モデルと断定しない。

## 11.5 max_generation

各10k checkpointおよびfinalで:

- `max_generation`
- 可能ならgeneration中央値 / 分布

を取得する。

少なくともfinal `max_generation` は必須。

same-seedで `bmr_core=0` と比較し、

```text
generation_ratio = max_generation(bmr_core=x) / max_generation(bmr_core=0)
```

を報告する。

これは「高bmr_coreでbody_size変化が小さいのは、単に進化世代数が少ないだけではないか」を診断するために使う。

## 11.6 生態健全性

Exp11と同じく:

- final / peak population
- births / deaths / death cause
- Energy flow by source
- free nutrient total
- total biomass
- corpse matter
- biomass_fraction
- Matter保存

を記録する。

これらは平衡/遅延の主判定には使わず、長期runで世界が別の制約状態へ壊れていないかを診断する。

---

# 12. 世代数基準の補助解析

tick基準だけでは、bmr_coreによる世代時間変化と選択圧変化を分離しにくい。

そこで補助解析として、各runのbody_size trajectoryをgeneration進行と対応付ける。

最低限:

- tick 10k / 20k / 30k / 40k / 50k時点の `max_generation`
- 各checkpointのmean / median body_size

を対応表として出す。

可能なら、snapshotごとの代表generation統計を追加し、body_size vs generation曲線を作る。

ただし `max_generation` は集団全体の代表世代時間ではなく極端値になり得るため、**generation基準の主判定をmax_generation単独では行わない**。

実装コストが小さい場合はsnapshot時にgeneration median / Q90を保存し、補助指標として使う。

---

# 13. 事前登録判定

Exp12では、「完全な数学的平衡」を証明するのではなく、50,000 tickの観測範囲で

- 安定化傾向が十分強いか
- 低下が依然として継続しているか

を分類する。

## 13.1 per-run stationarity

各COMPLETE runについて、後半2 blockのsigned driftを使う。

```text
abs(drift_23) <= 0.05
AND
abs(drift_34) <= 0.05
```

を満たし、さらに後半線形傾きが

```text
abs(slope_tick) <= 0.05 body_size / 10,000 tick
```

を満たした場合、

```text
STATIONARY_LIKE
```

と分類する。

この閾値は「厳密に平衡」を意味せず、50k観測範囲で変化が十分小さいという運用上の判定である。

## 13.2 persistent decline

以下を満たす場合:

```text
drift_23 < -0.05
AND
drift_34 < -0.05
AND
slope_tick < -0.05 body_size / 10,000 tick
```

```text
PERSISTENT_DECLINE
```

と分類する。

## 13.3 ambiguous

上記どちらにも当てはまらない場合:

```text
AMBIGUOUS
```

とする。

振動、seed依存、非単調変化を無理に平衡/遅延へ二値化しない。

---

# 14. 条件単位の判定

各 `bmr_core` について8 seed中:

## 14.1 equilibrium-supported

```text
STATIONARY_LIKE >= 6/8
PERSISTENT_DECLINE <= 1/8
```

かつfinal body_size medianが

```text
> 0.23
```

なら、

```text
EQUILIBRIUM_SHIFT_SUPPORTED
```

とする。

`>0.23` は単に0.2近傍で停止した条件を「大型側平衡」と誤認しないための最低限sentinelであり、恒久値選定の目標値ではない。

## 14.2 delay-supported

```text
PERSISTENT_DECLINE >= 6/8
```

なら、

```text
DELAY_SUPPORTED
```

とする。

特にfinal body_sizeが0.23以下へ接近している場合は強い遅延支持と解釈する。

## 14.3 mixed / unresolved

その他は:

```text
UNRESOLVED
```

とする。

---

# 15. Exp12全体の結論ルール

## Case A — `bmr_core` により明瞭な平衡変更

複数の `bmr_core>0` 条件で `EQUILIBRIUM_SHIFT_SUPPORTED` が成立し、かつ収束body_sizeが `bmr_core` とともに系統的に増える場合:

```text
SCIENTIFIC_VERDICT = EQUILIBRIUM_SHIFT_SUPPORTED
```

V1.7の設計意図「小型化圧そのものを弱め、内部領域を作る」は支持される。

次段階では、長期平衡位置・生態副作用・環境一般化を見て恒久 `bmr_core` を選定する。

## Case B — 高bmr_coreでも継続低下

代表的な `bmr_core>0` 条件の大半で `DELAY_SUPPORTED` の場合:

```text
SCIENTIFIC_VERDICT = DELAY_ONLY
```

V1.7の `bmr_core` は根本解決ではなく小型化速度を落としただけと判断し、別の生理設計を検討する。

## Case C — 世代数不足が主要因と疑われる

高bmr_coreほどtick基準では安定に見える一方、generation進行が極端に少なく、generation基準で低下傾向が揃う場合:

```text
SCIENTIFIC_VERDICT = GENERATION_LIMITED / REVIEW
```

50,000 tickでも平衡判定不能とし、run延長またはgeneration基準実験を検討する。

## Case D — seed間で挙動が分岐

stationary / decline / oscillatoryが大きく混在する場合:

```text
SCIENTIFIC_VERDICT = MULTISTABLE_OR_UNRESOLVED / REVIEW
```

単一平衡を仮定せず、trajectory・初期条件依存性を追加解析する。

---

# 16. `bmr_core=0` の扱い

Exp11では事前登録したsmall-size signalを0/8しか満たさず `CONTROL_NOT_REPRODUCED` になった。

Exp12ではこの基準をそのまま再利用しない。

理由は、Exp12の問いが「10,000 tick時点でp_low>=0.50か」ではなく、**長期的にどちらへ進んでいるか**だからである。

`bmr_core=0` は以下を見る。

- final body_size
- `p_low`
- drift_23 / drift_34
- slope_tick
- 8 seedのtrajectory一致性

50,000 tickでbody_sizeが0.2近傍へ近づき、低下傾向が継続するなら、Exp11の対照失敗は主として「10,000 tickが短かった」ことを示す。

逆に `bmr_core=0` 自体が内部領域で安定するなら、「現行世界に一方向の小型化圧がある」というV1.7導入前提そのものを再検討する。

---

# 17. Exp11とのsame-seed比較

Exp12の各runについて、同じ `bmr_core × seed` のExp11 B1 10,000 tick結果と比較する。

最低限以下を表にする。

```text
body_size@10k (Exp11)
body_size@20k
body_size@30k
body_size@40k
body_size@50k
max_generation@10k
max_generation@20k
max_generation@30k
max_generation@40k
max_generation@50k
```

Exp12の0–10k挙動がExp11 same-seedと大きく異なる場合は、コード・Config・数値環境差を疑い、正式解釈を停止する。

完全bitwise一致を要求するか、数値環境差を許容したfingerprint比較にするかは実装時に現在の再現性基盤へ合わせる。

---

# 18. 実行前integrity gate

正式dispatch前に以下を機械確認する。

1. 56 Configが存在
2. `bmr_core` が指定7水準のみ
3. seedが1..8で過不足なし
4. 全ConfigがB1環境である
5. body_sizeのみ進化ON
6. 他13遺伝子が完全固定
7. ticks=50,000
8. `memory_tau=10`
9. `response_gain=64`
10. `bmr_core` のJSON round-trip一致
11. Simulation初期化smoke test通過
12. 代表Configで短tick実走smoke test通過
13. collect側が実際のsnapshot CSV形式を読み取る回帰testあり
14. run探索が実際のディレクトリ階層に対して機能するtestあり
15. artifact欠落・重複を科学判定と分離する

Exp11で発生した

- fixed_genes名不整合
- snapshot形式読み違い
- runディレクトリ階層読み違い
- artifact取得漏れ

を再発させないことを明示的な実装要件とする。

---

# 19. Actions設計

56 runを1つのmatrixとして登録する。

```text
7 bmr_core × 8 seed = 56 jobs
max-parallel = 20
```

Exp11の旧実績を単純5倍した場合、50,000 tick/runはかなり長くなる可能性がある。

そのためworkflow実装時には、Exp11 B1の実測wall timeを取得してtimeoutを決める。

**timeout値を推測で固定しない。**

runner中断・timeoutは `INCOMPLETE_RESOURCE` とし、科学的失敗へ数えない。

技術的不完了jobのみ、同一SHA・同一Configで再実行可能とする。

collectorは全job終了後に一度だけ集約し、集計エラーがある場合は `SCIENTIFIC_VERDICT` を確定出力しない。

---

# 20. 出力物

実行後に最低限以下を生成する。

## CSV

- per-run summary
- per-snapshot body_size trajectory
- checkpoint summary (10k / 20k / 30k / 40k / 50k)
- block drift table
- generation comparison table
- ecological diagnostics

## plots

1. body_size mean vs tick — bmr_core別
2. body_size median vs tick — bmr_core別
3. same-seed trajectory small multiples
4. final body_size vs bmr_core
5. drift_23 / drift_34 vs bmr_core
6. slope_tick vs bmr_core
7. max_generation vs tick
8. body_size vs generation diagnostic
9. population vs tick
10. biomass_fraction vs tick

平均trajectoryだけでseed差を隠さない。

---

# 21. Exp12ではしないこと

- 新しいBMR式を試さない
- `bmr_core` 以外の世界パラメータを振らない
- body_size以外の遺伝子を進化させない
- Exp11の15水準フル探索を繰り返さない
- B2/B3を長期runしない
- populationを減らすことを目的にしない
- body_sizeを1.0へ戻すことを目的にしない
- 50k途中の結果を見て候補や判定式を変更しない
- CIを途中デバッグ目的で反復しない

---

# 22. Exp12後の意思決定

## `EQUILIBRIUM_SHIFT_SUPPORTED` の場合

次はExp13相当として、

1. 恒久候補 `bmr_core` を狭い範囲へ絞る
2. B2/B3を含む複数環境で長期健全性を確認
3. body_size以外の遺伝子を解放した場合にも同じ効果が残るか確認

へ進む。

## `DELAY_ONLY` の場合

`bmr_core` 単独ではV1.7の目的を満たさない。

BMR scaling、移動速度、繁殖コスト、表面積スケーリング等のどこが小型化圧の本体かを再分解する。

## `GENERATION_LIMITED / REVIEW` の場合

単純なtick延長ではなく、generation基準の比較実験または高速化した診断系を検討する。

---

# 23. Opus 5レビュー依頼事項

レビューでは特に以下を確認する。

1. **主問いに対して50,000 tick・7水準・8 seedが過不足ないか**
2. **代表 `bmr_core` の選び方にバイアスがないか**
3. **signed block drift + 後半slopeで平衡/遅延を区別する方法が妥当か**
4. **stationarity閾値 ±5% と slope閾値 0.05/10k が恣意的すぎないか**
5. **6/8 seedという条件単位判定が妥当か**
6. **max_generationだけでは世代交代診断として弱すぎないか。generation median/Q90保存を必須にすべきか**
7. **50kでなお遅い場合の停止/延長基準を事前登録すべきか**
8. **0.200を代表値へ追加すべきか**
9. **B2/B3をExp12から外す判断が妥当か**
10. **Exp11のsame-seed 0–10k再現性確認を正式gateに入れるべきか**
11. **長期run特有のpopulation halt / resource exhaustion / numerical driftへの追加監査が必要か**
12. **Exp12の結論ルールに、平衡変更と世代数不足を誤判定する構造的な穴がないか**

レビューでは、単なる文言改善ではなく、**科学的妥当性・反証可能性・計算コスト・再現性の観点から設計自体を批判的に確認すること**。
