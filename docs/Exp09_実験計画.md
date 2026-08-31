# Exp09 実験計画 — V1.5 異種一次Energy刺激比較則の診断

更新: 2026-08-31
状態: **事前登録 / V1.5実装前**

正本:
- `docs/V1.4_総括.md`
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
4. 0 <= response < 1
5. light-onlyで最良lightセルの順位がV1.4と同じ
6. chemical-onlyで最良chemicalセルの順位がV1.4と同じ
7. light=1.2 / chemical=12.3 / 両ability同値なら同一response score
8. 同じ刺激ならlight能力を上げればlight側、chemical能力を上げればchemical側へ切り替わる
9. light=1.2固定・両ability同値ならchemical stockが12.3を跨ぐところで理論どおり選択が切り替わる
10. exact tieでfield走査順によるsource固定biasがない
11. 未来の吸収量、Energy容量、移動後収益をscore計算に使わない
12. V1.5比較処理が不要な追加乱数を消費しない
13. V1.4の吸収式・Energy/Matter台帳を変更しない

Phase 0がGreenでなければ本番診断へ進まない。

## 6. Phase A — synthetic arena診断

短い人工arenaで、進化・人口動態を介さず選択則そのものを見る。

### A1 light-only

光勾配のみ。

期待:
- V1.4と同じ最良light方向を選ぶ

### A2 chemical-only

chemical勾配のみ。

期待:
- V1.4と同じ最良chemical方向を選ぶ

### A3 等価刺激

```text
light = 1.2
chemical = 12.3
light_absorption = chemical_absorption
```

期待:
- 受容器response scoreが同値
- light/chemicalどちらかをsource種類だけで固定優先しない

### A4 光専門型

例:

```text
light_absorption = 2.0
chemical_absorption = 0.3
```

等価環境刺激ではlightを選ぶ。

### A5 chemical専門型

```text
light_absorption = 0.3
chemical_absorption = 2.0
```

等価環境刺激ではchemicalを選ぶ。

### A6 両用型の環境依存切替

```text
light_absorption = 1.0
chemical_absorption = 1.0
```

lightを固定しchemical stockを低→高へ振り、理論的なscore交差点で選択先が切り替わることを確認する。

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
- light由来Energy flow
- chemical由来Energy flow
- ventセル滞在率
- 明部/暗部の滞在率
- vent中心までの距離分布または平均距離

これらは観測専用で進化ロジックへフィードバックしない。

## 9. Phase Bの期待パターン

これは「合格させるためのpopulation目標」ではなく行動則のsanity check。

- light specialistはchemical specialistよりlight選択率が高い
- chemical specialistはlight specialistよりchemical選択率・vent滞在率が高い
- generalistは一方へ固定されず、局所刺激条件に応じて選択が変わる
- light-only / chemical-only controlでV1.5無次元化が単独source内の方向選択を壊さない

特定のsource選択率（例50%）を合格条件にはしない。

## 10. 停止条件

以下は実装不備として停止:

- Phase 0算術不一致
- 単独sourceでtarget cell順位が意図せず変わる
- exact tieがsource走査順で常に一方へ偏る
- fixed geneが世代中に変化
- Energy / Matter保存異常
- source排他条件の破れ
- Config名と実値不一致
- 数値実行環境またはcommit混在

絶滅・低populationはそれだけでは実装異常としない。

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

## 13. 保存

`docs/実験結果保存方針.md`に従う。

GitHubへ:
- `docs/Exp09_結果考察.md`
- `experiments/<exp09_id>/NOTES.md`
- 集計プロット
- 代表GIF/PNG

全runの生データ・全画像はGoogle Drive / Actions artifactへ保存する。
