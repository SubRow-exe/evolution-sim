# Exp10 Phase B 実測 NOTES

更新: 2026-09-01

## 実行環境・コード

- **コード commit**: `287dc9b8`（Issue #41 再トライアル方針の修正を main へマージした SHA。
  全5バッチをこの同一 SHA で固定して実行）
- **数値実行環境キー**: `linux-x86_64-glibc2.39-py3.12.3-np2.5.2`（全 200 run 同一）
- **実行経路**: GitHub Actions（`.github/workflows/exp10.yml`）、ubuntu-24.04、
  20 並列、`workflow_dispatch` を条件ごとに 40 run ずつ 5 回起動
- **規模**: 5条件 × control/treatment × seed 1-20 × 10,000 tick = 200 run

## 実行バッチと Actions run

| バッチ | 条件 | Actions run | 結果 |
|---|---|---|---|
| B2 | b2_chem_only_chemspec (control+treatment) | 33477847738 | success |
| B1 | b1_light_only_lightspec | 33478255407 | success |
| B3 | b3_mixed_lightspec | 33479401980 | success |
| B4 | b4_mixed_chemspec | 33480561003 | success |
| B5 | b5_mixed_generalist | 33481282340 | success |

各 run の collect job が診断条件チェック（`check_exp10.py`）・要約
（`summarize_exp10_phaseB.py`）・健全性（`health_check.py`）・環境同一性
（`check_env.py --strict`）を実行し、すべて整合性 OK。

補足: 初回 B2 バッチ（run 33476692068 / 修正前 SHA `ebcc45b`）は、collect の
`check_exp10.py` が絶滅 run の空 snapshot で ValueError を投げて workflow failure に
なった。これは検証コードのバグ（データは正常）で、`if vals:` ガードを追加して修正し
（PR #47、SHA `287dc9b8`）、B2 を再実行した。正式結果は `287dc9b8` の再実行を採る。

## 行動則パラメータ（Phase A 選定・事前登録）

```
response_gain(control)   = 0.0
response_gain(treatment) = 64.0
memory_tau               = 10.0   (control/treatment 同一)
```

## 進化OFF の確認（機械的）

全条件・全 run・全期間で以下が分散0（`check_exp10.py` / `health_check.py`）:

```
body_size            = 1.0
mutation_rate        = 0.05
reproduction_investment = 0.4
(全14遺伝子。表現型2遺伝子 light/chemical_absorption は各条件の事前登録値で固定)
```

初回 Phase B の「個体数20倍・小型化」は再現せず、個体数は Exp09 相当
（最終 pop 中央値 16〜972）に戻った。

## 主要実測値（seed 中央値、20 seed / 条件）

| 条件 / 行動則 | 生存 | 最終pop | hi_q | vent滞在 | 移動 | \|dQ\| | sigma_eff | 光取得 | chem取得 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1 lightspec control | 20/20 | 784 | 0.591 | 0.000 | 0.782 | 7.5e-4 | 0.500 | 4,897,943 | 0 |
| B1 lightspec treatment | 20/20 | 766 | 0.607 | 0.000 | 0.782 | 7.4e-4 | 0.500 | 4,813,445 | 0 |
| B2 chemspec control | 18/20 | 16 | 1.000 | 0.742 | 0.696 | 3.45e-2 | 0.500 | 0 | 155,395 |
| B2 chemspec treatment | 20/20 | 68 | 1.000 | 0.842 | 0.753 | 3.11e-2 | 0.532 | 0 | 446,536 |
| B3 mixed lightspec control | 20/20 | 803 | 0.606 | 0.048 | 0.782 | 1.18e-3 | 0.500 | 4,988,937 | 60,841 |
| B3 mixed lightspec treatment | 20/20 | 782 | 0.627 | 0.077 | 0.781 | 1.19e-3 | 0.499 | 4,850,160 | 97,767 |
| B4 mixed chemspec control | 20/20 | 368 | 0.595 | 0.280 | 0.776 | 8.00e-3 | 0.500 | 1,754,743 | 529,872 |
| B4 mixed chemspec treatment | 20/20 | 310 | 0.687 | 0.439 | 0.792 | 7.48e-3 | 0.508 | 1,353,339 | 585,151 |
| B5 mixed generalist control | 20/20 | 972 | 0.594 | 0.098 | 0.778 | 2.71e-3 | 0.500 | 5,566,968 | 368,515 |
| B5 mixed generalist treatment | 20/20 | 962 | 0.624 | 0.139 | 0.783 | 2.77e-3 | 0.501 | 5,388,469 | 494,822 |

### 事前登録判定

- **§5.5（重要停止条件）**: b2_chem_only_chemspec treatment **20/20 生存 → クリア**。
- **§8-3（high-Q 改善、treatment−control）**: 全条件 20/20 seed が改善（方向 OK）。
  改善量中央値 B1 +1.64pp / B3 +2.57pp / B4 +10.14pp / B5 +3.60pp。
  +5pp 超は B4 のみ（他は REVIEW）。B2 は指標退化で評価対象外。
- **§8-4（generalist 両刺激統合）**: B5 treatment 20/20 seed で `dQ_light`/`dQ_chem`
  ともに非ゼロ → OK。
- **§8-7（供給側の物理）**: 全条件 control=treatment 光供給 12,480,000 → OK。

### vent 距離帯別滞在率（treatment 中央値）

| 条件 | d0-1 | d1-2 | d2-4 | d4+ |
|---|---:|---:|---:|---:|
| B1 light-only | 0.0026 | 0.0223 | 0.0950 | 0.8808 |
| B2 chem-only | 0.0826 | 0.5594 | 0.3572 | 0.0015 |
| B3 mixed lightspec | 0.0069 | 0.0506 | 0.0943 | 0.8497 |
| B4 mixed chemspec | 0.0442 | 0.2942 | 0.2481 | 0.4103 |
| B5 mixed generalist | 0.0124 | 0.0899 | 0.1290 | 0.7676 |

## 外部生データの保存先

- **Google Drive**: `gdrive:evolution-sim/exp10_actions_<stamp>/`（各バッチの
  `exp10_<condition>.tar.gz`、collect job が rclone で転送済み）
- **Actions artifact**: 各 run の `exp10-summary`（manifest・summary.txt・
  env_check.txt・health.txt・conditions.txt、90日保持）、および各 run の
  `exp10-<case>-seed<N>`（stats/snapshots/environment/spatial、90日保持）

Git には生データを入れない（`docs/実験結果保存方針.md` §1）。本ディレクトリには
結果考察・NOTES・集計プロット・代表 GIF/PNG のみを置く。

## 図の生成

`experiments/exp10_phaseB_20260901/make_figures.py` が Actions の summary（seed中央値）を
埋め込んで集計プロットを生成する。代表空間 GIF/PNG は同一 commit・同一数値実行環境で
seed1 をローカル再実行し `tools/render_spatial.py` で生成（決定論的に本番と一致）。
