# Exp11 Phase B 実測 NOTES

更新: 2026-09-02

## 実行環境・コード

- **シミュレーション実行コード commit**: `8da7311a38751c8b956d1a80d6d3129e6c33dfe4`
  (PR #52 マージ後の main。V1.7 `bmr_core` 実装 + Exp11 45 Config + `exp11.yml` 反映済み)
- **シミュレーション実行 Actions run**: [`33506955494`](https://github.com/SubRow-exe/evolution-sim/actions/runs/33506955494)
  (`workflow_dispatch`、ticks=10000、`.github/workflows/exp11.yml`、ubuntu-24.04、max-parallel=20)
- **規模**: 15 bmr_core候補 × 3環境 (B1=8 seed / B2=5 seed / B3=4 seed) = **255 run**
- **数値実行環境キー**: `linux-x86_64-glibc2.39-py3.12.3-np2.5.2` (全255 run同一。`tools/check_env.py --strict`で確認)
- **255 run全てCOMPLETE** (10,000 tick完走。EXTINCT/POP_HALT/INCOMPLETE_RESOURCEなし)

## collect側バグと再集計の経緯

初回collect (Actions run 33506955494 内の `collect` job) は、解析スクリプト自体の
バグ (Issue #53) により `SCIENTIFIC_VERDICT` を正しく算出できなかった。
シミュレーション本体は正常で、生データは無傷のままGitHub Actions artifact
(90日保持) およびGoogle Drive (rclone転送、`exp11_actions_20260901_145201`) に
保存済みだった。

バグ内容 (PR #54で修正):
1. `summarize_exp11.py` が snapshotを `tick_*.json` として探していたが、実際は
   `snapshots/snap_{tick:08d}.csv` (CSV形式)。これにより全runでsnapshot未検出
   →偽の `CONTROL_NOT_REPRODUCED` を出力していた。
2. `check_exp11.py` の実行済みrun探索が1階層のみで、実際の2階層構造
   (`runs/exp11/<条件key>/<seed run dir>/config.json`) を検出できていなかった。

修正版スクリプト (`check_exp11.py` / `summarize_exp11.py` / `tools/exp11_common.py`、
PR #54, `main` SHA `e7ec28f8a3dc0013e9285edcc51559da87f6d364`) で、
**シミュレーションを再実行せず**、既存255 runの生データを再集計する専用workflow
`.github/workflows/exp11_recollect.yml` を追加・実行した。

| recollect試行 | Actions run | 結果 |
|---|---|---|
| 1回目 | [33573000219](https://github.com/SubRow-exe/evolution-sim/actions/runs/33573000219) | `actions/download-artifact@v4` が255個中199個しか取得できず (B1低bmr_core側56 run欠落)。`summarize_exp11.py`が正しく集計エラーとして検出しSCIENTIFIC_VERDICT確定を拒否 (`UNDETERMINED`)。バグではなく想定どおりの安全側動作 |
| 2回目 (正式採用) | [33574028338](https://github.com/SubRow-exe/evolution-sim/actions/runs/33574028338) | ダウンロード手段を`gh run download` (PR #55) へ変更し、255個全て取得。整合性チェック・集計エラーなし。`SCIENTIFIC_VERDICT`確定 |

正式結果は2回目の再集計 (run 33574028338、main SHA `830aaaaae14e4be34e6393cb0d6289a8136eadbd`) を採る。

## 整合性チェック結果 (全てOK)

```
uv run python tools/check_exp11.py runs/exp11
-> OK: 全 45 Config 整合性チェック通過 / 実行済み 255 run 完全性チェック通過
```

- B1×15候補×8 seed / B2×15候補×5 seed / B3×15候補×4 seed が全て揃い、欠落・重複なし
- 各runの環境・bmr_coreがディレクトリ名・実験計画の想定と一致

## 事前登録判定結果 (`docs/Exp11_実験計画案.md` §11)

```
=== Exp11 Phase B 結果集計 (255 run 収集) ===

--- §11.1 B1 bmr_core=0 対照妥当性 ---
  seed1: COMPLETE p_low=0.440 ✗
  seed2: COMPLETE p_low=0.441 ✗
  seed3: COMPLETE p_low=0.458 ✗
  seed4: COMPLETE p_low=0.342 ✗
  seed5: COMPLETE p_low=0.237 ✗
  seed6: COMPLETE p_low=0.267 ✗
  seed7: COMPLETE p_low=0.427 ✗
  seed8: COMPLETE p_low=0.011 ✗
  small-size signal: 0/8 (必要: 5) -> CONTROL_NOT_REPRODUCED

--- §11.2 B1 candidate per-seed Green ---
  bmr_core=0.005 〜 0.300: 全候補 0/8 B1_FAIL

--- §11.3 TRANSITION_ELIGIBLE (連続 3 候補 B1 Green) ---
  TRANSITION_ELIGIBLE: []

--- §11.4 B2/B3 baseline viability ---
  B2 baseline healthy COMPLETE: 5/5 -> OK
  B3 baseline healthy COMPLETE: 4/4 -> OK

--- §11.5 B2/B3 environmental veto ---
  veto なし

--- §11.6 恒久値選定 ---
  理由: CONTROL_NOT_REPRODUCED

============================================================
SCIENTIFIC_VERDICT = NO_SELECTION / REVIEW
============================================================
```

## 事後診断 (事前登録判定とは別。候補選定には未使用)

`--diagnostics-csv exp11_diagnostics.csv` で255 run全ての per-run 指標を出力済み
(Actions artifact `exp11-recollect-result`、run 33574028338 に保存。90日保持)。

### B1 (light-only): bmr_core別 body_size中央値 (8 seed)

| bmr_core | body_size median |
|---:|---:|
| 0.000 | 0.2164 |
| 0.005 | 0.2153 |
| 0.010 | 0.2170 |
| 0.015 | 0.2187 |
| 0.020 | 0.2346 |
| 0.025 | 0.2328 |
| 0.030 | 0.2334 |
| 0.040 | 0.2492 |
| 0.050 | 0.2577 |
| 0.060 | 0.2556 |
| 0.075 | 0.2716 |
| 0.100 | 0.3356 |
| 0.150 | 0.4088 |
| 0.200 | 0.4389 |
| 0.300 | 0.6273 |

### B2/B3: bmr_core=0 baseline に対する final population 変化 (中央値)

| bmr_core | B2 final pop (baseline比) | B3 final pop (baseline比) |
|---:|---:|---:|
| 0.000 | 90.0 (1.00x) | 5544.5 (1.00x) |
| 0.005 | 84.0 (0.93x) | 4992.5 (0.90x) |
| 0.010 | 81.0 (0.90x) | 4731.0 (0.85x) |
| 0.015 | 81.0 (0.90x) | 4622.0 (0.83x) |
| 0.020 | 86.0 (0.96x) | 4826.5 (0.87x) |
| 0.025 | 85.0 (0.94x) | 4583.0 (0.83x) |
| 0.030 | 82.0 (0.91x) | 4472.5 (0.81x) |
| 0.040 | 88.0 (0.98x) | 4465.0 (0.81x) |
| 0.050 | 79.0 (0.88x) | 4018.0 (0.72x) |
| 0.060 | 84.0 (0.93x) | 4040.0 (0.73x) |
| 0.075 | 80.0 (0.89x) | 3463.0 (0.62x) |
| 0.100 | 79.0 (0.88x) | 2875.0 (0.52x) |
| 0.150 | 80.0 (0.89x) | 2455.0 (0.44x) |
| 0.200 | 76.0 (0.84x) | 1973.0 (0.36x) |
| 0.300 | 77.0 (0.86x) | 1568.0 (0.28x) |

環境別・bmr_core別のbody_size mean/median/p_low/p_high/late_drift/final・peak
population/biomass_fractionの全詳細 (n=8/5/4のmedian/range) は
`docs/Exp11_結果考察.md` の付録テーブル、および `exp11_diagnostics.csv`
(255行、Actions artifact) を参照。

## 外部生データの保存先

- **全255 runの生データ** (config.json/meta.json/stats.csv/snapshots/environment):
  Google Drive (`exp11_actions_20260901_145201`、初回collect時にrclone転送)
  および GitHub Actions artifact (`exp11-B*-bmr*-seed*`、90日保持、run 33506955494)
- **再集計結果** (summary.txt / integrity.txt / exp11_diagnostics.csv):
  GitHub Actions artifact `exp11-recollect-result` (run 33574028338、90日保持)

## 未実施

- 集計プロット・代表GIF/PNGの生成 (この記録では実施していない)
- 結果の解釈・考察 (本NOTESは事実の記録のみ)
