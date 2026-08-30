# Exp05 実験計画 — V1.1互換光場 vs V1.2高コントラスト光場

更新: 2026-08-30
状態: **事前登録済み / pilot・本番とも実行完了 (主解析は一部未実施)**

詳細実装仕様: `docs/V1.2_V1.2.1_詳細実装仕様.md`

## 1. 目的

V1.1で確認された小型化・高光利用化への強い方向性選択が、**世界全体の光供給量を同一に保ったまま、光の空間偏在だけを強くした場合**にどう変わるかを確認する。

V1.1終盤ではsweep群の光利用率が約90%に達していたため、Exp05では総光量を減らさない。これにより、世界全体のエネルギー不足と空間偏在の効果を混同しない。

Exp05は「多様性が増えたか」を成功条件にしない。

## 2. 実装前提

1. #19 V1.2 高コントラスト静的光環境
2. #23 V1.2.1 空間分布・行動範囲・PNG/GIF
3. 全CI Green
4. `vertical` ControlがV1.1互換
5. 観測ON/OFFで科学結果不変
6. pilot 6 runが実装健全性を満たす

V1.1最終コードは `v1.1-final` に保存済み。

## 3. 比較条件

同一V1.2.1コード上で光場だけ変更する。

### Control

```text
light_pattern = vertical
```

V1.1互換。既定40×40では総光量:

```text
1,248 E/tick
```

### Treatment

```text
light_pattern = high_contrast_vertical
light_hc_bright_frac = 0.20
light_hc_transition_frac = 0.50
light_hc_dark_floor = 0.0
light_hc_total_scale = 1.0
```

40×40では:

```text
北 8行  (20%) : 最大光量plateau
中20行  (50%) : 最大 → 0 の線形勾配
南12行  (30%) : 完全暗部
```

総光量は正規化によりControlと一致:

```text
Treatment = 1,248 E/tick
```

Treatment実効ピークは約:

```text
1.733333 E/cell/tick
```

V1.1最大1.2の約1.44倍。

### 固定するもの

- INITIAL_GENOME
- 無性生殖
- 成熟年齢なし / 繁殖クールダウンなし
- 化学資源量・vent仕様
- 無機栄養構造
- 生理コスト式
- 突然変異仕様
- 初期個体数
- 世界サイズ
- その他光場以外のConfig

## 4. 本番条件 — 実行完了 (2026-08-30)

実行結果: `experiments/exp05_actions_20260830_061219/NOTES.md`
Actions run 33292936640 / コード `7e3065e` / 40 run 完走・健全性Green。
事前登録どおりの条件で実行し、途中での条件変更は行っていない。


```text
seed: 1-20
ticks: 40,000
2条件 × 20 seed = 40 run
stats_interval = 20
snapshot_interval = 1000
GitHub Actions / 同一数値実行環境
同一seed対応比較
```

主sweep判定:

```text
top_lineage_frac >= 0.5
```

0.3 / 0.7は感度解析。

## 5. Pilot — 完了 (2026-08-30)

```text
seed: 1,2,3
ticks: 5,000
2条件 × 3 seed = 6 run
```

結果: **全項目Green。本番条件は変更しない。**
記録: `experiments/exp05_pilot/NOTES.md`
判定ツール: `uv run python tools/check_pilot.py runs/exp05_pilot --ticks 5000`

Pilotは実装健全性だけ確認する。

- crashなし
- Control/Treatment総光量一致
- Treatmentが8行明部・20行遷移・12行暗部
- Treatment最大光量が設計値
- snapshot / environment NPZ / 空間指標出力
- PNG/GIF生成
- Control互換
- 観測ON/OFF不変性Green

確認済み (pilot実測):

| 項目 | 結果 |
|---|---|
| 6 run の 5,000 tick 到達・絶滅なし | OK |
| 総光供給量 Control = Treatment | 双方 1,248.000000 E/tick |
| Treatment 帯構造 | 北8行plateau / 中20行単調減少 / 南12行完全暗部 |
| Treatment 実効ピーク | 1.733333 (= 1.2 × 13/9) |
| Control が V1.1 と同一結果 | `verify_vs_ref.py --ref origin/v1.1-final` 全ケース一致 |
| snapshot / env NPZ / 空間指標 / PNG / GIF | OK |
| 観測ON/OFF不変性・全テスト | 42 passed / 4 skipped |

pilotは `linux-x86_64-glibc2.39-py3.12.3-np2.5.2` で実行した。
本番はActions (ubuntu-24.04) で環境キーが変わるため、pilotの数値と本番結果を直接比較しない。

暗部無人化、大量死、進化方向等の生物学的結果を理由に条件を変更しない。
仕様を変えるならpilotを破棄し再事前登録する。

## 6. 主解析

### 進化
- body_size
- light_absorption
- chemical_absorption
- mutation_rate
- reproduction_investment

### lineage
- top_lineage_frac
- n_lineages
- sweep率 / sweep tick
- 同一seed 2×2対応

### 資源
- light / chemical / nutrient / corpse / predation flows
- total_biomass
- 光利用率 = 区間flow_light / 区間light_supply

### 空間
Treatment設計zoneと同じ位置をControlにも適用:

```text
North:  y/H < 0.20
Middle: 0.20 <= y/H < 0.70
South:  y/H >= 0.70
```

確認:
- band population / fraction
- occupied_cells
- centroid
- mean_radius_from_centroid
- mean_move_per_org_tick
- mean_local_light
- vent_cell_frac
- mean_chemical_absorption

### 目視
全40 runでraw snapshot + environment dataを保存。
light背景PNG/GIFを標準成果物とする。
chemical/nutrientは後処理可能にする。

## 7. 解釈原則

以下はいずれも意味のある結果:
- 明部に高光利用型が集中
- 暗部が無人化
- 明暗で住み分け
- chemical利用増加
- 高光利用型が暗部まで再席巻
- sweep率のみ変化
- 空間差は出るが形質平均は同じ

## 8. Exp05後

V1.2は「光環境を振る」系列として続ける。

次は結果を見て以下のどちらかを選ぶ。

### A. 総光量を維持したまま、さらに勾配を強くする
- bright域をさらに狭める
- dark域をさらに広げる
- `light_hc_total_scale=1.0` は維持

### B. Exp05の空間shapeを固定し、総光量だけ変える
- `light_hc_total_scale` を例 0.75 / 1.25 に変更

一度にshapeと総量を同時変更せず、因果を切り分ける。
