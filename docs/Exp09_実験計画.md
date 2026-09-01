# Exp09 実験計画 — V1.5 異種一次Energy刺激比較則の診断

更新: 2026-08-31
状態: **実行完了 / Green（2026-08-31）**

実測の正本は `docs/Exp09_結果考察.md` と
`experiments/exp09_actions_20260831_085922/NOTES.md`。
本書は事前登録の条件・判定基準の正本として、実行後も内容を変更しない。

正本:
- `docs/V1.4_総括.md`
- `docs/V1.5_Exp09_レビュー判断.md`
- `docs/V1.5_異種刺激比較仕様.md`
- 本書

## 1. 問い

V1.5で導入する

> 光とchemicalを無次元受容器応答へ変換して比較する行動則

が、実装どおり・意図どおりに働くか。

Exp09は**光とchemicalの進化競争を評価する実験ではない**。

## 2. 用語

- 無次元受容器応答:
  単位の違う刺激を0〜1の共通尺度へ変換した値。
- `light_stimulus_half`:
  光刺激の応答が0.5になる光量。V1.5 defaultは1.2。
- `chemical_stimulus_half`:
  chemical刺激の応答が0.5になるstock。V1.5 defaultは12.3。
- 交差点stock:
  ある光量・個体能力の組合せで、light scoreとchemical scoreが等しくなるchemical stock。これよりchemical stockが高ければchemical側、低ければlight側が一次Energy候補として優勢になる。
- specialist（専門型）:
  片方の一次Energy利用能力を高く、もう片方を低く固定した診断個体。
- generalist（両用型）:
  light / chemical能力を同程度に固定した診断個体。

## 3. 事前登録するV1.5式

```text
response(x,K) = x / (x + K)

light_score
= light_absorption
× response(light, 1.2)

chemical_score
= chemical_absorption
× response(chemical_stock, 12.3)
```

V1.5の一次Energy源選択はこのscoreで行う。

吸収量そのものはV1.4の吸収式を変更しない。

`chemical_stimulus_half=12.3`は、典型的な完全13セルventの生物不在平衡stockを基準とする固定値である。Exp08で生物が占有したventの実測stockへ合わせて引き下げない。

生物がchemicalを利用するとstockと刺激が下がり、離脱すれば回復する負のフィードバックはstock型資源の自然な性質として残す。

## 4. Exp09で固定する世界default

V1.4で確定した値を使う。

```text
light_uptake_coef = 2.0
chem_vent_flux = 16.0 E/tick/vent
chem_uptake = 0.5
n_vents = 4
vent_radius_cells = 2
chem_loss_frac = 0.10
```

Exp09中に生物学的結果を見て変更しない。

## 5. Phase 0 — 決定論テスト

進化runの前に算術と行動選択を直接テストする。

必須項目:

1. `response(0,K)=0`
2. `response(K,K)=0.5`
3. x増加に対して単調増加
4. `0 <= response < 1`
5. light-only / chemical-onlyの単独source Configで、同一seedなら`v1.4-final`と決定的に完全一致
6. light=1.2 / chemical=12.3 / 両ability同値なら同一response score
7. 各診断表現型・代表光量についてlight/chemical scoreの**交差点stockを事前計算**
8. 交差点の下側でlight、上側でchemicalへ理論どおり選択が反転
9. 各診断表現型についてlight選択ケースとchemical選択ケースを最低1件ずつ確認
10. exact tieでfield走査順によるsource固定biasがない
11. `stimulus_tie_eps`は1e-9程度の十分小さい値または同等に厳しい相対許容差
12. 両score=0ではEnergy源による方向付けを行わずV1.4相当の挙動へ戻る
13. 未来の吸収量、Energy容量、移動後収益をscore計算に使わない
14. V1.5比較処理が不要な追加乱数を消費しない
15. V1.4の吸収式・Energy/Matter台帳を変更しない
16. 観測追加がRNG・個体状態・行動分岐へ影響しない

Phase 0がGreenでなければ本番診断へ進まない。

### 交差点の扱い

Phase 0で事前に、少なくとも以下の表現型について標準光の明部・中間・暗部等で交差点stockを表にする。

```text
light specialist:    light_absorption=2.0, chemical_absorption=0.3
chemical specialist: light_absorption=0.3, chemical_absorption=2.0
generalist:          light_absorption=1.0, chemical_absorption=1.0
```

Exp08の占有vent stockの実測範囲も参考値として併記するが、その値へKを再校正しない。

## 6. Phase A — synthetic arena診断

短い人工arenaで、進化・人口動態を介さず選択則そのものを見る。

### A1 light-only

光勾配のみ。

期待:
- `v1.4-final`と同じ行動結果

### A2 chemical-only

chemical勾配のみ。

期待:
- `v1.4-final`と同じ行動結果

### A3 等価刺激 / tie

```text
light = 1.2
chemical = 12.3
light_absorption = chemical_absorption
```

期待:
- 受容器response scoreが同値
- light/chemicalどちらかをsource種類だけで固定優先しない

### A4 光専門型

```text
light_absorption = 2.0
chemical_absorption = 0.3
```

標準的な等価刺激でlightを選ぶケースに加えて、光を十分弱くするなどして理論交差点を超え、chemicalを選ぶケースも必ず作る。

### A5 chemical専門型

```text
light_absorption = 0.3
chemical_absorption = 2.0
```

chemicalを選ぶケースだけでなく、chemical stockを交差点未満に落とすなどしてlightを選ぶケースも作る。

### A6 両用型の環境依存切替

```text
light_absorption = 1.0
chemical_absorption = 1.0
```

lightを固定しchemical stockを交差点の下→上へ振り、理論的なscore交差点で選択先が切り替わることを確認する。

### Phase Aの判定

実測行動が事前計算したscore順位と一致すること。

生存率や最終populationは判定材料にしない。

## 7. Phase B — 短時間の混合世界sanity check

実際の40×40標準世界でvertical lightとchemical ventを同居させる。

進化効果を混ぜないため、診断する`light_absorption` / `chemical_absorption`は全世代で固定する。必要なら他遺伝子も固定して行動則の因果を明確にする。

### 条件

1. Light-only control
   - lightあり / chemical source 0
   - light specialist
2. Chemical-only control
   - light 0 / chemicalあり
   - chemical specialist
3. Mixed / light specialist
4. Mixed / chemical specialist
5. Mixed / generalist

代表形質:

```text
light specialist:    light_absorption=2.0, chemical_absorption=0.3
chemical specialist: light_absorption=0.3, chemical_absorption=2.0
generalist:          light_absorption=1.0, chemical_absorption=1.0
```

### 規模

Pilot:

```text
5条件 × seed1 × 500〜1,000 tick
```

本番候補:

```text
5条件 × seed1-5 × 5,000 tick = 25 run
```

Exp09は行動則診断なので、長期進化runは行わない。

Pilotで実装不備がなければ本番条件を生物学的結果に応じて変更しない。

## 8. 必須観測量

既存のpopulation / Energy flowに加え、Exp09では行動選択を直接観測する。

最低限:

- lightを一次Energy候補として選んだ回数
- chemicalを一次Energy候補として選んだ回数
- tie回数
- random walkへ戻った回数
- 選択時のlight response score
- 選択時のchemical response score
- 選択時のchemical stock
- 理論交差点の上/下と実際のsource選択が一致した回数・率
- light由来Energy flow
- chemical由来Energy flow
- ventセル滞在率
- 明部/暗部の滞在率
- vent中心までの距離分布または平均距離
- 一次Energy候補がcorpse / predation等の既存刺激に負けた回数（light由来 / chemical由来を区別）

これらは観測専用で進化ロジックへフィードバックせず、RNGも消費しない。

## 9. Phase Bの期待パターン

これは「合格させるためのpopulation目標」ではなく行動則のsanity check。

最優先の判定は:

> **その時点のchemical stockが事前計算した交差点より上ならchemical、下ならlightというscore順位と実際の一次Energy候補選択が一致すること。**

その上で参考として:

- light specialistは標準条件ではchemical specialistよりlight選択率が高い
- chemical specialistは交差点を超えるstockではchemicalを選ぶ
- generalistは一方へ固定されることを要求せず、局所stockと光量の組合せに応じて理論式どおり切り替わるかを見る
- stock消費→離脱→stock回復→再誘引の反復が出ても、交差点式と整合するなら直ちに異常扱いしない
- light-only / chemical-only controlは`v1.4-final`と完全一致

特定のsource選択率やvent滞在率（例50%）を合格条件にはしない。

## 10. 停止条件

以下は実装不備として停止:

- Phase 0算術不一致
- 単独source Configが`v1.4-final`と完全一致しない
- 交差点の理論順位と人工arenaの選択結果が一致しない
- 各診断表現型で交差点の両側を通しても選択が反転しない
- exact tieがsource走査順で常に一方へ偏る
- fixed geneが世代中に変化
- Energy / Matter保存異常
- source排他条件の破れ
- Config名と実値不一致
- 数値実行環境またはcommit混在
- 観測追加がRNG系列や進化ロジックを変える

絶滅・低population・vent滞在率の低さはそれだけでは実装異常としない。

## 11. Exp09では結論しない

- 光とchemicalのどちらが進化的に優れるか
- 通常祖先がどちらへ専門化するか
- specialistとgeneralistの長期共存
- chemical bootstrap
- 動物的進化
- nutrient / corpse / predationを含む全刺激の完全比較則

Exp09はV1.5の**比較メカニズムそのものの妥当性検証**である。

## 12. Exp09後

Exp09がGreenなら、次の段階で初めて通常祖先を光+chemical混合世界へ置き、

- light専門化
- chemical専門化
- generalist
- 空間ニッチ分化

が自然に生じるかを長期進化runで調べる。

この次実験の条件はExp09結果を見てから別途事前登録する。

長期混合進化を解釈するときは、chemicalがstock消費により知覚刺激を下げる性質と、`chem_uptake=0.5`による収支側の差の両方を初期条件として明示する。

## 13. 保存

`docs/実験結果保存方針.md`に従う。

GitHubへ:
- `docs/Exp09_結果考察.md`
- `experiments/<exp09_id>/NOTES.md`
- 集計プロット
- 代表GIF/PNG

全runの生データ・全画像はGoogle Drive / Actions artifactへ保存する。
