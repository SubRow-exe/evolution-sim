# Exp05 本番 — V1.1互換光場 vs V1.2高コントラスト光場

実行日: 2026-08-30
実行環境: GitHub Actions / ubuntu-24.04
Actions run: https://github.com/SubRow-exe/evolution-sim/actions/runs/33292936640
コード: `7e3065e` (main)
正本: `docs/Exp05_実験計画.md` / 手順: `docs/Exp05_実行手順.md` / Issue #24

## 1. 実行条件 (事前登録どおり・変更なし)

```text
Control  : configs/exp05_control.json    light_pattern=vertical
Treatment: configs/exp05_treatment.json  light_pattern=high_contrast_vertical
                                         20/50/30, dark_floor=0.0, total_scale=1.0
seed  : 1-20
ticks : 40,000
run数 : 2条件 × 20 seed = 40
stats_interval=20 / snapshot_interval=1000
```

総光供給量は双方 1,248 E/tick (Treatmentの実効ピーク 1.733333)。

## 2. 実行の健全性 — 全項目Green

| 項目 | 結果 |
|---|---|
| run完走 | 40/40 success。早期終了 (絶滅・max_population_halt) なし |
| 数値実行環境 | `check_env.py` / `health_check.py` ともに単一環境と判定 (環境キーの実値は `env_check.txt` を参照) |
| git SHA | 40 run すべて `7e3065e` |
| 光場・出力構造 (`check_pilot.py`) | 判定OK。総光量一致・帯構造・ピーク・snapshot 40枚・env NPZ 40個・PNG 40枚 + GIF・同一seedの初期世界一致 |
| health_check | 問題なし (停止条件に非該当) |
| 生データ | 467 MB (control 360.6 MB / treatment 369.3 MB、各 2,523 ファイル) を外部ストレージへ転送済み |

1 run の所要: control 12〜23分 / treatment 18〜50分。全体は約1時間35分。

## 3. 主要結果 (40,000 tick 時点)

### sweep 累積発生率 (主判定 top_lineage_frac >= 0.5)

| 条件 | 主判定 | share>=0.3 | share>=0.7 | sweep tick 中央値 |
|---|---|---|---|---|
| Control | **12/20 (60%)** | 13/20 (65%) | 11/20 (55%) | 25,810 |
| Treatment | **13/20 (65%)** | 17/20 (85%) | 10/20 (50%) | 22,200 |

同一seed対応 (2×2):

| | Treatment sweep | Treatment 未sweep |
|---|---|---|
| **Control sweep** | 8 (seed 1,2,4,9,12,14,17,20) | 4 (seed 3,6,11,18) |
| **Control 未sweep** | 5 (seed 5,7,10,16,19) | 3 (seed 8,13,15) |

不一致は 4 対 5。**sweep の発生率そのものに条件差は見られない。**

一方、両条件でsweepした8 seedでは Treatment の方が sweep が早い
(差の中央値 −8,600 tick、8 seed中6 seedで前倒し。最大 seed 17 の −22,720)。

### 最終時点の中央値 (seed 20件)

| 指標 | Control | Treatment |
|---|---|---|
| population | 3,100 (1,207〜3,830) | **1,800.5** (1,289〜2,840) |
| n_lineages | 54 (5〜76) | **23.5** (4〜47) |
| mean_body_size | 0.483 (0.339〜0.991) | **0.925** (0.405〜1.272) |
| mean_light_absorption | 2.880 (0.946〜4.590) | **4.035** (2.296〜4.738) |
| mean_reproduction_investment | 0.475 | 0.469 |
| mean_mutation_rate | 0.136 | 0.119 |

**総光量が同一でも、光を空間的に偏在させると個体数と系統数がほぼ半減し、
body_size と light_absorption の中央値が上がった。**

sweep群 vs 未sweep群 (中央値):

| | Control sweep | Control 未sweep | Treatment sweep | Treatment 未sweep |
|---|---|---|---|---|
| 個体数 | 3,351 | 1,303.5 | 2,065 | 1,422 |
| body_size | 0.412 | 0.932 | 0.798 | 1.089 |
| light_abs | 4.221 | 1.430 | 4.068 | 2.506 |
| 系統数 | 27.5 | 69 | 20 | 40 |

両条件とも「sweepした系統は小型・高光利用」という V1.1 と同じ方向。
ただし Treatment の未sweep群も light_abs 2.5前後まで上がっており、
Control の未sweep群 (1.4前後) より高い。

## 4. 現時点で言えること / 言えないこと

言えること (40,000 tick・20 seed の範囲で):
- 総光量を保ったまま空間偏在を強めても、sweep の累積発生率は変わらない (60% vs 65%、対応比較でも 4:5)
- sweep の時期は Treatment の方が早い傾向
- 定常個体数・系統数は Treatment で大きく下がる
- 形質の中央値は body_size・light_absorption ともに Treatment で高い

まだ言えないこと:
- 空間分布・行動指標 (3帯人口、occupied_cells、centroid、移動量、mean_local_light、vent滞在) の条件差
  → stats.csv / lineages.csv に記録済み。生データから解析する
- 資源フロー (光利用率、chemical/nutrient/corpse/predation) の条件差
  → 同上
- 目視 (light背景PNG/GIF 40 run分)
- 未sweep seed が 40,000 tick 以降に sweep するか (打ち切りデータ)

## 5. 保存物

- 生データ: `gdrive:evolution-sim/exp05_actions_20260830_061219/` に
  `exp05_control.tar.gz` (231 MB) / `exp05_treatment.tar.gz` (237 MB)
- チェックサム・マニフェスト・解析出力: Actions成果物 `exp05-summary` (90日保持)
  - `exp05_control/MANIFEST.md` / `exp05_treatment/MANIFEST.md` (run一覧・SHA256)
  - `analysis.txt` / `env_check.txt` / `structure.txt`
- 本NOTESの数値は collect ジョブの出力に基づく

## 6. 次の判断

`docs/Exp05_実験計画.md` §8 の候補A / Bのどちらへ進むかは、
§6 の主解析 (空間・行動・資源フロー・目視) を終えてから決める。

本NOTESの段階では「sweep率は不変、密度と多様性は低下、形質中央値は上昇」
という数値面の一次結果のみを確定させる。
