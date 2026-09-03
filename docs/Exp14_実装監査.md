# Exp14 実装監査 — 要求トレーサビリティ表

更新: 2026-09-03
状態: **formal dispatch前の自己監査 (docs/Exp14_実装チェックリスト.md 準拠、HARD GATE)**

対象ブランチ: `claude/pr-50-v1.6-exp11-iuhnzm`

正本:
1. `docs/Exp14_レビュー判断.md`
2. `docs/Exp14_実験計画確定.md`
3. `docs/Exp14_実装チェックリスト.md`
4. `AGENTS.md`

Opus 5レビュー原文 (`docs/Exp14_Opus5レビュー.md`, branch `claude/review-v1-7-exp11-kflr82`)
は独自採用せず、`docs/Exp14_レビュー判断.md`が確定した採否のみを実装する。

---

# 要求トレーサビリティ表

| Requirement | Implementation | Independent Test | Result |
|---|---|---|---|
| A0-A6 (Phase A 7 arms定義) | `tools/exp14_common.py::PHASE_A_ARMS`/`PHASE_A_BASELINE`, `tools/make_exp14_configs.py::build_phase_a` | `tests/test_exp14_configs.py::test_phase_a_arm_deltas_applied`, `test_phase_a_all_genes_fixed` | PASS |
| A6は energy_capacity だけでなく initial_energy も連動 (fill fraction保存) | `PHASE_A_ARMS["A6"]` (energy_capacity=200, initial_energy=100を両方明示) | `tests/test_exp14_common.py::test_a6_preserves_initial_fraction_not_just_capacity` | PASS |
| Phase A A2/A3/A4/A6 R_ref順序 (A2<A0, A3≈A0, A4<A0, A6<A0) | `tools/exp14_common.py::r_ref`/`r_ref_for_arm`/`reference_maintenance_rate` (実装と同じBMR/organ/sense/membrane/resist/move式) | `tests/test_exp14_common.py::test_r_ref_orderings_required_by_checklist` | PASS |
| R_refはlight_maxを直接使わない | `RRefInputs`にlight_max fieldなし | `tests/test_exp14_common.py::test_r_ref_does_not_use_light_max_directly` | PASS |
| Phase A 7×3×2000=21 | `tools/exp14_common.py::PHASE_A_JOBS` (独立算出assert) | `tests/test_exp14_common.py::test_phase_totals_116`, `tests/test_exp14_configs.py::test_all_jobs_full_totals_116_no_dupes` | PASS |
| Phase B 5×5×3=75 grid、period/energy_capacity | `tools/exp14_common.py::PHASE_B_PERIODS/PHASE_B_CAPACITIES`, `tools/make_exp14_configs.py::build_phase_b` | `tests/test_exp14_configs.py::test_phase_b_grid_covers_all_cells` | PASS |
| Phase B initial_energy = 0.5*energy_capacity (generator導出、手書きしない) | `tools/exp14_common.py::phase_b_initial_energy` | `tests/test_exp14_common.py::test_phase_b_initial_energy_derived_not_hardcoded`, `tests/test_exp14_configs.py::test_phase_b_initial_energy_matches_derivation` | PASS |
| Phase C C1-C4 mutable/fixed genes (canonical GENE_NAMES由来) | `tools/exp14_common.py::PHASE_C_MUTABLE_GENES`/`phase_c_fixed_genes`, `tools/make_exp14_configs.py::build_phase_c` | `tests/test_exp14_common.py::test_phase_c_fixed_genes_derived_from_canonical_gene_names`, `tests/test_exp14_configs.py::test_phase_c_mutable_genes_not_fixed` | PASS |
| Phase C 4×5=20 | `tools/exp14_common.py::PHASE_C_JOBS` | `tests/test_exp14_common.py::test_phase_totals_116` | PASS |
| formal total = 21+75+20=116 (generator側とcheckerで独立算出) | `tools/exp14_common.py::TOTAL_RUNS`, `tools/make_exp14_configs.py::all_jobs` (assert), `tools/check_exp14.py::expected_run_keys` (別経路で116を再構成) | `tests/test_exp14_configs.py::test_all_jobs_full_totals_116_no_dupes`, `tests/test_check_exp14.py::test_expected_run_keys_count` | PASS |
| FULL/COMPACT tick定義 (A=2k/5k or 3k/20k or 10k) | `tools/exp14_common.py::FULL_TICKS`/`COMPACT_TICKS`/`PROFILES` | `tests/test_exp14_configs.py::test_all_jobs_compact_also_116` (両profileで116生成できることを確認) | PASS |
| runtime予測: ≤9h→FULL / else COMPACT / COMPACT>10hならformal未開始 | `tools/exp14_runtime_report.py::choose_profile`/`predict_profile` | `tests/test_exp14_runtime_report.py` (FULL選定/COMPACT選定/formal_auto_start_blocked の3ケース) | PASS |
| preflight/formal構造分離 (Exp13再発防止) | `.github/workflows/exp14.yml`: `preflight` job (`if: inputs.mode=='preflight'`) はreport-onlyで終了。formal job群 (`formal_phase_a/b/c/collect`) は `if: inputs.mode=='formal'` のみで起動し、`needs: preflight` を一切持たない (preflight成功からformalへ繋がるjob依存が構造的に存在しない) | 目視監査 (workflowファイルにpreflight->formalのneeds/if連鎖が無いことを確認)。CI上の自動testはYAML構文検証 (`python3 -c "import yaml; ..."`) | PASS |
| 昼夜観測: sunset/dawn population, daytime peak/night minimum | `tools/exp14_common.py::cycle_observation_from_rows` (既存stats.csvのpopulation/light_cycle_factor列から事後計算。simulation/recorder新規stateなし) | `tests/test_exp14_common.py::test_cycle_observation_from_rows_detects_transitions` | PASS |
| 昼夜観測: daylight_births_cum, night_starvation_deaths_cum | `tools/exp14_common.py::daylight_births_and_night_starvation` (既存events.csvとevosim.daynight.daylight_factorから事後計算) | `tests/test_exp14_common.py::test_daylight_births_and_night_starvation` | PASS |
| Energy/capacity mean/median/p10/p90 | `evosim/recorder.py::Recorder.stats` (energy_frac_* 4列追加、読み取り専用集計) | `tests/test_exp14_observation_noninterference.py::test_energy_frac_and_trait_percentile_columns_present` | PASS |
| Phase C trait quantiles (body_size/reproduction_investment/movement_power p10/p90) | `evosim/recorder.py::Recorder.stats` (p10_*/p90_* 6列追加) | `tests/test_exp14_observation_noninterference.py::test_energy_frac_and_trait_percentile_columns_present` | PASS |
| lineage persistence | 追加実装なし。既存 `n_lineages` (lineage_idは`_try_reproduce`で親から継承のみ、新規発生は初期個体群生成時のみ) がそのまま系統存続数を表す | `evosim/simulation.py::_try_reproduce`のlineage_id継承ロジックを読解確認 (既存`tests/test_conservation.py`等が既にn_lineages計算を回帰カバー) | PASS (追加実装不要と結論) |
| 観測非干渉 (RNG/state/update order不変) | 追加列はすべて既存stats.csv/events.csv/Config由来の事後計算 (exp14_common.py) か、recorder.stats()内の読み取り専用集計 (energy_frac/trait percentile)。simulation.pyへの変更なし | `tests/test_exp14_observation_noninterference.py::test_recorder_on_off_same_seed_identical_trajectory` (recorder ON/OFFで同一seed軌跡・RNG消費が一致) | PASS |
| late window N/A semantics (Exp13バグ修正) | `tools/exp14_common.py::late_window_metric` (final_tick<windowでNoneを返す)、`tools/summarize_exp14.py::summarize_phase_a_run` | `tests/test_exp14_common.py::test_late_window_metric_na_when_final_tick_below_window`, `tests/test_summarize_exp14.py::test_late_window_na_never_registers_as_pass` (early-extinction runでlate_population_meanがNoneのまま誤PASSしないことを確認) | PASS |
| 判定基準 SURVIVES_SHORT(3/3)/MARGINAL(2/3)/COLLAPSE(0-1/3) | `tools/exp14_common.py::classify_phase_a_arm` | `tests/test_exp14_common.py::test_classify_phase_a_arm` | PASS |
| 科学STOP(EXTINCT/POP_HALT/SCIENTIFIC_STOP_REVIEW)と技術FAIL(INCOMPLETE_RESOURCE/INTEGRITY_FAIL)の分離 | `tools/summarize_exp14.py::run_status` (population==0→EXTINCT [scientific]、meta.incomplete_resource→INCOMPLETE_RESOURCE [technical] 等を明確に分岐) | `tests/test_summarize_exp14.py::test_run_status_extinct_is_scientific_not_technical`, `test_run_status_incomplete_resource_marker`, `test_run_status_missing_files_is_integrity_fail` | PASS |
| artifact完全性 (期待116 key、欠落/重複/想定外検出) | `tools/check_exp14.py::expected_run_keys`/`check_run_key_completeness` | `tests/test_check_exp14.py::test_check_run_key_completeness_detects_missing_and_unexpected`, `test_check_run_key_completeness_detects_duplicate` | PASS |
| formal SHA/numeric environment整合性 | `tools/check_exp14.py::check_run_environment_integrity` (Exp13と同じロジックを踏襲) | `tests/test_check_exp14.py::test_environment_integrity_detects_sha_mismatch` | PASS |
| current-run決定性比較 (first-Nk×2) | `tools/check_exp14.py::compare_first_nk` | `tests/test_check_exp14.py::test_compare_first_nk_identical_match`、preflight workflow内で実runを使って実行 (`.github/workflows/exp14.yml` preflight job) | PASS (静的test) / 実測はpreflight実行後 |
| Config generator静的整合性 (116件・fixed_genes・bmr_core・density response) | `tools/check_exp14.py::check_generated_configs` | `tests/test_check_exp14.py::test_check_generated_configs_full_ok` | PASS |
| runtime total estimate (Exp14全体wall-clock) | `tools/exp14_runtime_report.py::predict_profile`/`choose_profile` (setup/collect/safety factor/wave数を含む) | `tests/test_exp14_runtime_report.py` | PASS (計算ロジック) / 実測値はpreflight完走後にユーザーへ報告 |

**Implementation/Test列が空欄の行はない。**「lineage persistence」は要求分析の結果「既存`n_lineages`列で充足済み・追加実装不要」と結論した行であり、これは実装チェックリスト.md該当項目が求める独立検証(既存ロジックの読解確認+既存回帰testでのカバー確認)を満たす。「current-run決定性比較」「runtime total estimate」の実測部分のみ、preflight完走後でなければ算出できない性質上「実施予定」であり、これは本チェックリストがpreflight後・formal dispatch前の実施を明示的に要求している項目と整合する(Exp13の`docs/V1.8_Exp13_実装監査.md`と同じ扱い)。

---

# 設計判断の記録 (レビュー判断からの逸脱がないことの確認)

- R_refの入力に`repro_energy_frac`を「定常的に維持しうる貯蔵水準の代理」として使う設計は、`docs/Exp14_実験計画確定.md`§3の「実装の維持コスト構造を使う」要求と、`docs/Exp14_レビュー判断.md`§2の「R_refは診断専用・cross-arm順序比較のみ」という位置づけの両方を満たすように設計した。A5 (initial_energyのみ変更) はR_refに影響しない設計とし、これは"A5は steady-state reserve ではなく tick-1 初期条件だけを単離するarmである"という`Exp14_実験計画確定.md`§5 A5節の意図と整合する。
- 昼夜観測 (sunset/dawn population, daytime peak/night minimum, daylight_births_cum, night_starvation_deaths_cum) はすべて **simulation.py/recorder.pyへ新規stateを追加せず**、既存stats.csv/events.csv/Configからの事後計算として実装した。これにより「観測コードはRNG/state/update orderを変更してはいけない」(AGENTS.md §9) という制約への抵触リスクをそもそも構造的に排除している。
- Energy/capacity分布とPhase C対象形質のpercentileのみ、個体間分布という性質上stats.csv単体で復元できないため`Recorder.stats()`へ読み取り専用集計として追加した。RNG消費・個体状態変更・simulation update orderへの影響がないことは`tests/test_exp14_observation_noninterference.py`で確認した。
- Opus 5レビュー原文 (`docs/Exp14_Opus5レビュー.md`) の提案そのものは実装に直接使用していない。すべて`docs/Exp14_レビュー判断.md`が確定した採否 (M1-M3, S1-S5) を通じてのみ反映している。

---

# ローカルテスト結果

```
uv run pytest tests -q
uv run python tools/check_exp14.py --profile FULL
uv run python tools/check_exp14.py --profile COMPACT
uv run python tools/make_exp14_configs.py --profile FULL --check
```

(詳細な合否件数はPR本文/CI結果に記載する。)

# 未確認事項

- Exp14 preflight (`.github/workflows/exp14.yml`, `mode: preflight`) のGitHub Actions実行結果
- preflight実測に基づくFULL/COMPACT選定・Exp14全体wall-clock予測のユーザー報告 (このセッションで実施予定)
- formal 116 runの実測結果 (別dispatchで、ユーザーの明示的な開始判断後)
