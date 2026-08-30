# Exp05 実験計画 — V1.1互換光場 vs V1.2高コントラスト光場

更新: 2026-08-30
状態: **本番完了 / 履歴用事前登録**

結果・考察: `docs/Exp05_結果考察.md`
詳細実装仕様: `docs/V1.2_V1.2.1_詳細実装仕様.md`

## 1. 目的

V1.1で確認された小型化・高光利用化への強い方向性が、**世界全体の光供給量を同一に保ったまま、光の空間偏在だけを強くした場合**にどう変わるか確認する。

V1.1終盤ではsweep群の光利用率が約90%に達していたため、総光量を減らさず、空間偏在の効果だけを切り分ける。

## 2. 比較条件

### Control
```text
light_pattern = vertical
総光量 = 1,248 E/tick
```

### Treatment
```text
light_pattern = high_contrast_vertical
light_hc_bright_frac = 0.20
light_hc_transition_frac = 0.50
light_hc_dark_floor = 0.0
light_hc_total_scale = 1.0
```

40×40:
```text
北8行  (20%): 最大光量plateau
中20行 (50%): 最大 → 0 の線形勾配
南12行 (30%): 完全暗部
総光量 = 1,248 E/tick
実効ピーク ≈ 1.733333 E/cell/tick
```

固定したもの:
- INITIAL_GENOME
- 無性生殖
- chemical資源・vent仕様
- nutrient構造
- 生理コスト式
- 繁殖仕様
- 突然変異仕様
- 初期個体数 / 世界サイズ

## 3. 実行条件

```text
seed 1-20
ticks 40,000
2条件 × 20 seed = 40 run
stats_interval=20
snapshot_interval=1000
GitHub Actions / 同一数値実行環境
同一seed対応比較
```

主sweep判定:
```text
top_lineage_frac >= 0.5
```

0.3 / 0.7は感度解析。

## 4. Pilot

```text
seed 1,2,3
2条件
5,000 tick
6 run
```

Pilotは実装健全性のみ確認し、全項目Greenで本番条件を変更せず進行した。

確認項目:
- crashなし
- Control/Treatment総光量一致
- Treatment帯構造 / peak一致
- snapshot / environment / PNG/GIF
- ControlのV1.1互換
- 観測ON/OFF結果不変

## 5. 主解析として事前登録した項目

### 進化
body_size / light_absorption / chemical_absorption / mutation_rate / reproduction_investment

### lineage
sweep率 / sweep tick / n_lineages / 同一seed対応

### resource
light / chemical / nutrient / corpse / predation flows / biomass / 光利用率

### spatial
```text
North:  y/H < 0.20
Middle: 0.20 <= y/H < 0.70
South:  y/H >= 0.70
```

band population / occupied_cells / centroid / distribution width / movement / local light / vent fraction / chemical_absorption

### visual
raw snapshot/environment + light背景PNG/GIF。

## 6. 実行後

本番は40 runすべて完了。
結果は `docs/Exp05_結果考察.md` に分離して記録した。

Exp05によって新たに、**完全暗部にchemical資源があってもchemical利用型が成立しない**という設計上の懸念が見つかった。

そのため、当初候補だった「次に光総量を振る」は保留し、Exp06でchemical利用経路の成立性を先に診断する。

正本: `docs/Exp06_実験計画.md`
