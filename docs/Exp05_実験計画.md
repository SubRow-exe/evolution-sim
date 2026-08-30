# Exp05 実験計画 — V1.1互換光場 vs V1.2高コントラスト光場

更新: 2026-08-30
状態: **事前登録済み / 未実行**

詳細実装仕様: `docs/V1.2_V1.2.1_詳細実装仕様.md`

## 1. 目的

V1.1で確認された小型化・高光利用化への強い方向性選択が、**世界全体の光供給量を同一に保ったまま空間分布だけを高コントラスト化**したとき、どのように変化するかを確認する。

Exp05は「多様性を出すこと」を成功条件にしない。
V1.1の単一的な進化圧を1軸だけ揺さぶったときに、進化方向・資源利用・lineage動態・空間分布に何が新しく起きるかを観察する探索比較実験とする。

## 2. 実装前提

Exp05本番は以下が完了してから開始する。

1. **V1.2**: 高コントラスト静的光環境 (#19)
2. **V1.2.1**: 空間分布・行動範囲・PNG/GIF可視化 (#23)
3. 全CI Green
4. V1.1互換光場 `vertical` が同一コード上で利用できる
5. 観測ON/OFFで乱数系列・科学結果が変わらないことを確認済み
6. 3 seed × 2条件 × 5,000 tickのパイロットが実装健全性を満たす

V1.1最終コードは `v1.1-final` ブランチに保存済み。

## 3. 比較条件

**同一のV1.2.1コード上で、光場だけを変更する。**

| 条件 | light_pattern | 意味 |
|---|---|---|
| Control | `vertical` | V1.1互換光場 |
| V1.2 | `high_contrast_vertical` | 明所50%・遷移30%・完全暗部20% |

### 光供給量

既定40×40世界・`light_max=1.2`では両条件とも:

```text
1,248 E/tick
```

とする。

Treatment既定値:

```text
light_hc_bright_frac = 0.50
light_hc_transition_frac = 0.30
light_hc_dark_floor = 0.0
```

したがってExp05は**光の総量ではなく空間配置だけの差**を比較する。

### 固定するもの

以下は両条件で同一とする。

- INITIAL_GENOME
- 無性生殖
- 成熟年齢なし / 繁殖クールダウンなし
- 化学資源量・vent仕様
- 無機栄養構造
- 生理コスト式
- 突然変異仕様
- 初期個体数
- 世界サイズ
- その他、光場以外のConfig

## 4. 実行条件

### 本番

- seed: **1–20**
- ticks: **40,000**
- 2条件 × 20 seed = **40 run**
- GitHub Actions / 同一数値実行環境
- 同一seed対応比較
- `stats_interval = 20`
- `snapshot_interval = 1000`

40,000 tickとする理由:
- V1.1ではselective sweepが主に17k tick以降で観測された
- 初期適応だけでなく、sweep発生率・時期まで比較可能にする

### 本番前パイロット — 条件固定

```text
seed: 1,2,3
ticks: 5,000
条件: Control + high_contrast
合計: 6 run
```

目的は実装健全性確認のみ。

確認:
- crashしない
- Control/Treatment総光量が一致
- Treatmentが20行明部・12行遷移・8行暗部になっている
- snapshot / environment NPZ / 空間指標が正常出力
- light背景PNG/GIFが生成可能
- Control `vertical` がV1.1互換
- 観測ON/OFF不変性テストGreen

Treatmentで大量死・暗部無人化等が起きても、正しいモデル帰結なら望む結果に合わせてパラメータを変更しない。
数式実装ミス・総量不一致・zone境界ミス・出力不備のみ修正対象とする。

生物学的な結果を理由に仕様変更する場合はパイロットを破棄し、Exp05条件を再事前登録する。

## 5. 主解析

### A. 進化方向

- body_size
- light_absorption
- chemical_absorption
- mutation_rate
- reproduction_investment
- 必要に応じその他主要形質

確認:
- V1.2でも高光利用・小型化へ同程度に収斂するか
- 進化速度が変わるか
- 暗部の存在でchemical利用等の代替経路が立ち上がるか

### B. lineage動態

- top_lineage_frac
- n_lineages
- sweep発生率
- sweep tick

主sweep判定はV1.1と同じ `top_lineage_frac >= 0.5`。
0.3 / 0.7は感度確認とする。

### C. 資源利用

- light flow
- chemical flow
- nutrient flow
- corpse利用
- predation
- total_biomass

### D. 空間分布・行動

地理帯をControl/Treatmentで共通固定する。

```text
North:  y/H < 0.50
Middle: 0.50 <= y/H < 0.80
South:  y/H >= 0.80
```

Treatmentでは明部 / 遷移 / 暗部に対応する。

確認:
- 各bandの個体数・割合
- lineageごとの占有セル数
- lineage重心
- 平均移動距離/tick
- centroidからの平均距離
- mean local light
- vent cell滞在割合
- chemical_absorption

### E. 目視解析

全runでraw snapshot + environment dataを保存する。
標準成果物としてlight背景PNG/GIFを生成する。
chemical/nutrient GIFはraw dataから後処理可能とする。

見る点:
- 系統がどこから拡大するか
- 明所/暗所で分布が分かれるか
- sweepが空間的にどう広がるか
- 定住/広域移動などの行動差が見えるか

## 6. 同一seed対応比較

各seedについてControlとV1.2を対応させる。

```text
Control sweep     → V1.2 sweep
Control sweep     → V1.2 no-sweep
Control no-sweep  → V1.2 sweep
Control no-sweep  → V1.2 no-sweep
```

形質・人口・資源利用・空間指標も同一seed差分を主に見る。

## 7. 解釈原則

以下はいずれも意味のある結果。

- 明所に光利用型が集中し、暗部がほぼ無人
- 明暗で異なる系統/戦略が住み分ける
- 暗部でchemical利用が増える
- 高光利用型が結局暗部まで席巻する
- sweep率だけが変化する
- 空間差は生まれるが形質平均はほぼ同じ

「多様性が増えたか」だけでV1.2を評価しない。

## 8. Exp05後

結果をレビューして、次の**世界ルール変更 V1.3**を決める。
候補:
- 化学エネルギー供給量・配置
- 無機栄養の空間偏在/複数化
- 成熟期間/繁殖クールダウン
- 時間的光変動
- 温度等の新環境軸
- 初期ゲノム到達距離バイアス

有性生殖は変更規模が大きいため後段候補とする。
