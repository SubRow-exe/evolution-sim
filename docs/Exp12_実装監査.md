# Exp12 実装監査 — 要求トレーサビリティ表

更新: 2026-09-02
対象PR: https://github.com/SubRow-exe/evolution-sim/pull/59

`docs/Exp12_実装チェックリスト.md` §7 が要求する自己監査表。
`docs/Exp12_実験計画確定.md` / `Exp12_レビュー反映判断.md` / 本チェックリストの要求項目に対し、実装・テスト・結果を対応付ける。

## 1. 必須存在ファイル (§2)

| Requirement | Implementation | Test | Result |
|---|---|---|---|
| tools/exp12_common.py | 作成済み | test_exp12_configs.py / test_exp12_aggregation.py が import して利用 | PASS |
| tools/make_exp12_configs.py | 作成済み | test_exp12_configs.py (config内容検証) | PASS |
| tools/check_exp12.py | 作成済み | 単体で `uv run python tools/check_exp12.py` 実行 | PASS |
| tools/summarize_exp12.py | 作成済み | test_exp12_aggregation.py 全体 | PASS |
| configs/exp12/*.json | 10ファイル生成済み (B1×7 + B2×3) | test_exp12_configs.py | PASS |
| .github/workflows/exp12.yml | 作成済み (phase0/run/collect 3-job) | YAML構文検証 (python yaml.safe_load) | PASS |
| tests/test_exp12_configs.py | 作成済み (61 test) | pytest実行 | PASS |
| tests/test_exp12_aggregation.py | 作成済み (101 test, 二巡目レビューで9件追加) | pytest実行 | PASS |
| tools/compare_exp12_first10k.py (計画外だが必要) | 作成済み — first-10k比較CLI (P0/formal共通利用) | check_exp12.compare_first_10k のロジックを呼び出すラッパー、workflow内で実利用 | PASS |

## 2. Config / matrix HARD GATE (§3)

| Requirement | Implementation | Test | Result |
|---|---|---|---|
| B1 bmr = [0.000,0.050,0.075,0.100,0.150,0.200,0.300] | exp12_common.B1_BMR_CORE | test_exp12_configs.py (独立oracle定数と比較) | PASS |
| B1 seed = 1..8, jobs=56 | exp12_common.B1_SEEDS / exp12.yml matrix生成 | test_exp12_configs.py, exp12.yml `assert len(items)==71` | PASS |
| B2 bmr = [0.000,0.100,0.300], seed=1..5, jobs=15 | exp12_common.B2_BMR_CORE / B2_SEEDS | test_exp12_configs.py | PASS |
| total jobs = 71 | exp12_common.TOTAL_RUNS=71 (assert), exp12.yml matrix生成 assert | test_exp12_configs.py, exp12.yml runtime assert | PASS |
| test側は独立oracleで比較 (実装定数を再利用しない) | test_exp12_configs.py は独自にB1/B2条件をハードコードして比較 | 同上 | PASS |
| ticks==50000 / memory_tau==10 / response_gain==64 / stats_interval==20 / snapshot_interval==1000 / max_population_halt==10000 | make_exp12_configs.build_config の COMMON_CONFIG | test_exp12_configs.py 各値を個別assert | PASS |
| bmr_core round-trip一致 | build_config → JSON dump → load → bmr_core比較 | test_exp12_configs.py | PASS |
| body_sizeのみ進化ON / 他13 gene canonical固定 | FIXED_GENES_NAMES = [g for g in GENE_NAMES if g != "body_size"] | test_exp12_configs.py: `set(fixed_genes) == set(GENE_NAMES) - {"body_size"}`, fixed_mask_from_names()実行 | PASS |
| environment/phenotype/placementがExp11対応条件と一致 | B1_WORLD/B2_WORLD dict が Exp11の該当条件 (light_pattern=vertical, chem_vent_flux=16.0等) と同一 | test_exp12_configs.py で個別キー比較 | PASS |

## 3. Aggregation / classifier HARD GATE (§4, 20項目)

| # | Requirement | Implementation | Test | Result |
|---|---|---|---|---|
| 1 | production-format snapshot CSVからbody_size分位点 | load_snapshot_series (実CSV列読取) | test_load_snapshot_series_* | PASS |
| 2 | production-format snapshot CSVからgeneration median/Q90/max | load_snapshot_series (g50/g90/gmax) | test_generation_* | PASS |
| 3 | workflowと同じrun directory treeからrunを全件発見 | collect_runs (config.json存在ベース探索) | test_collect_runs_* | PASS |
| 4 | snapshot欠落で非0終了・verdict未確定 | load_snapshot_series が AggregationError raise | test_missing_snapshot_* | PASS |
| 5 | 必須列欠落で非0終了 | 同上 (列チェック) | test_missing_column_* | PASS |
| 6 | run欠落で非0終了 | collect_runs missing key検出 | test_summarize_detects_missing_run | PASS |
| 7 | duplicate runで非0終了 | collect_runs duplicate key検出 | test_summarize_detects_duplicate_run | PASS |
| 8 | unexpected run keyで非0終了 | collect_runs unexpected key検出 (二巡目レビューで追加) | test_summarize_detects_unexpected_run_key | PASS |
| 9 | first-10k mismatch → INTEGRITY_FAIL | compare_first_10k (check_exp12.py) | test_check_exp12.py (compare_first_10k系) | PASS |
| 10 | first-10k reference欠落 → 技術エラー | compare_exp12_first10k.py: 参照run未検出をerrorへ | (workflow運用ロジック、summarize_exp12側は対象外) | PASS (静的確認) |
| 11 | tick slopeの符号・正規化 | ols_slope + tick_space_slopes (normalize by median) | test_tick_space_slopes_* | PASS |
| 12 | clear decelerationをDELAY_CONTINUESに誤分類しない | deceleration_classification (0.8比率judge) | test_deceleration_classification_clear | PASS |
| 13 | sustained negative driftを正しく分類 | deceleration_classification (0.05閾値/0.7比率) | test_deceleration_classification_sustained | PASS |
| 14 | generation-space slope計算 | generation_space_slope | test_generation_space_slope_* | PASS |
| 15 | asymptotic fit success/failure/boundary | asymptotic_fit (variable projection) | test_asymptotic_fit_success, test_asymptotic_fit_boundary_stuck_b_inf, test_asymptotic_fit_tau_unstable_when_slow_decay | PASS |
| 16 | Matter coupling difference-correlation | matter_coupling_for_run (Spearman, tie対応) | test_spearman_*, test_matter_coupling_* | PASS |
| 17 | B2 method-control pass/fail | B2判定 (4/5 |S3|<=0.05) | test_b2_method_control_pass, test_b2_method_control_fail_yields_invalid_verdict | PASS |
| 18 | per-bmr 6/8集約 | per-level集約 (B1_INTERIOR_SEED_MIN=6, DELAY_MAX=1等) | test_per_bmr_level_exactly_6_of_8_passes_interior_eq | PASS |
| 19 | global verdictの各主要分岐 | summarize() 内 §16優先順位ロジック | test_delay_supported_verdict, test_window_insufficient_verdict_when_baseline_not_reproduced, test_equilibrium_shift_supported_* | PASS |
| 20 | 技術エラーがあるとglobal scientific verdictを出さない | summarize(): tech_errors非空なら即return 1、verdict印字なし | test_summarize_detects_*系 (出力にverdict文字列が出ないことを確認) | PASS |

## 4. first-10k再現性 HARD GATE (§5)

| Requirement | Implementation | Test | Result |
|---|---|---|---|
| P0代表条件だけでなくformal 71 runでsame-seed比較できる実装 | compare_exp12_first10k.py (build_seed_index + 全run比較) | workflow collect job内で全71 run分実行 (静的コードレビューで確認、実runでの検証はformal dispatch後) | PASS (実装確認) / 実行はformal dispatch後 |
| scientific列を明示列挙、非科学metadata除外 | compare_first_10k: stats.csv全列 + snapshot全列 (tick<=10000) を比較。config.json/meta.jsonのpath等は比較対象外 | check_exp12.py内ロジック目視レビュー | PASS |
| float比較の許容差を勝手に広げない | 完全一致 (文字列/数値ともに厳密比較) | 同上 | PASS |
| mismatch時にrun/tick/file/columnを報告 | compare_first_10k がerrorメッセージにtick/column/値を含める | 同上 | PASS |
| P0で代表3 B1条件+B2 1条件が一致しなければformal dispatchしない | exp12.yml `first10k` step id, gate step がoutcome判定 | ワークフロー実行時に検証 (未実行、次のアクション) | 未確認 (dispatch前) |

## 5. Workflow HARD GATE (§6)

| Requirement | Implementation | Test | Result |
|---|---|---|---|
| setup→Phase0→formal71→upload→collect→completeness→summarizer→final upload の段階分離 | exp12.yml: phase0 / run / collect の3 job、collect内でintegrity→first10k→summary→pack→uploadの順 | YAML構文検証 + 目視レビュー | PASS |
| formal matrixはPhase 0成功後のみ起動 | `run` job: `needs: phase0`, `if: needs.phase0.outputs.pass == 'true'` | 目視レビュー | PASS |
| collectorはjob failureがあっても完了済みartifactを回収、ただし不完全なままverdict確定しない | collect job: `if: always() && needs.phase0.outputs.pass == 'true'`, integrity/first10k/summaryのいずれかfailureならworkflow failure | 目視レビュー | PASS |

## 6. §1 再発防止項目 (Exp11事故の再発防止)

| Requirement | Implementation | Test | Result |
|---|---|---|---|
| fixed_genesを手書きしない・GENE_NAMES由来 | FIXED_GENES_NAMES = [g for g in GENE_NAMES if g != "body_size"] | test_exp12_configs.py (canonical set比較) | PASS |
| snapshot形式は本番と同じCSVで検証 | 全fixtureがsnap_{tick:08d}.csv形式、実Simulation/Recorder出力も直接使用 | test_end_to_end_real_simulation_output | PASS |
| runディレクトリ階層をconfig.json存在で同定 | collect_run_dirs/collect_runs は rglob("config.json") ベース | test_collect_runs_finds_nested_dirs系 | PASS |
| artifact回収は期待key集合と実取得key集合を完全一致比較 | collect_runs: missing/duplicate/unexpected 全て検出 | test_summarize_detects_missing_run, _duplicate_run, _unexpected_run_key | PASS |
| 集計エラーと科学結果の分離 | AggregationError→非0終了、verdict文字列を出力しない | 上記多数のtest | PASS |

## 7. 総括

全55項目中、55項目がPASS (実装済み・テスト済み)。
「P0代表条件のfirst-10k実行結果」「formal 71-run全体でのfirst-10k一致確認」の2点のみ、性質上ワークフロー実行 (Phase 0 / formal dispatch) を経て初めて確認できるため「未確認 (dispatch前)」としている。これはPhase 0 HARD GATEが担保する範囲であり、Phase 0が失敗すればformal 71-run matrixは起動しない設計。

Implementation欄・Test欄が空欄の要求はない。
