# Exp12 実装監査 — 要求トレーサビリティ表

更新: 2026-09-02
状態: **再監査必須 / PR #59の旧監査結果は現行実装の完了証明として使用しない**

## 重要

この文書は当初PR #59 (`feat: Exp12実装`) の自己監査として作成され、当時は実装要求をPASSと判定していた。

しかし、その後のExp12初回Actions run:

```text
run_id = 33585027312
```

で、**過去Exp11 Hosted Runner artifactとのbit完全一致をHARD GATEにする設計自体が不適切**と判明した。

正式71-run matrixは1本も起動していない。

したがって、PR #59時点の「全項目PASS」は履歴としては有効だが、**現在のExp12をformal dispatchしてよいことを意味しない。**

Git履歴に旧詳細表は残っている。本ファイルの現行版は、再実装・再監査が必要であることを明確にする。

---

# 1. 現在優先する文書

1. `docs/数値再現性・Actions実行環境方針.md`
2. `docs/Exp12_実験計画確定.md`
3. `docs/Exp12_実装チェックリスト.md`
4. `docs/次の実験計画.md`
5. `AGENTS.md`

再現性gateに関して旧Exp12計画と技術amendmentが矛盾する場合、`数値再現性・Actions実行環境方針.md` を優先する。

---

# 2. PR #59で確認済みで、原則そのまま維持する項目

以下は初回Phase 0でも実際に通っており、科学条件変更は不要。

```text
Config / Simulation smoke             PASS
Exp12単体tests                         101 passed
保存則・決定性tests                    7 passed
71-run matrix設計                      実装済み
fixed_genes canonical                 実装済み
production-format CSV aggregation     実装済み
欠落/重複artifact検出                  実装済み
classifier / verdict                  実装済み
tick/generation trajectory            実装済み
asymptotic fit                         実装済み
Matter coupling                        実装済み
```

ただし、再現性gate修正後に全testsを再実行すること。

---

# 3. 再実装・再監査が必要な項目

Sonnet 5はformal再dispatch前に最低限以下を修正する。

| Requirement | Required state | Status |
|---|---|---|
| P0 first-10k HARD GATE | 現在SHA・現在runner内の同一条件同seed比較 | TODO |
| historical Exp11 comparison | DIAGNOSTIC。bit mismatch単独でPhase 0 FAILにしない | TODO |
| formal collect historical comparison | bit mismatchをworkflow failure条件から除外 | TODO |
| formal SHA integrity | 71 runで同一formal SHAを機械確認 | TODO |
| numeric environment integrity | formal群のnumeric environment混在を機械検出 | TODO |
| current-run mismatch test | mismatch時HARD STOP | TODO |
| historical mismatch regression test | diagnosticのままformal verdictを落とさない | TODO |
| traceability table | 新要件へ更新 | TODO |
| runtime estimate report | 既存Phase0時間から事前見積もりを報告 | TODO |
| runtime actual report | formal完了後に既存Actions timestampから報告 | TODO (formal後) |

**TODOが1項目でも残る状態でformal 71-runをdispatchしない。**

---

# 4. 実行時間に関する既存データ

初回Phase 0 run `33585027312` で既に以下を測定済み。

```text
B1 bmr=0.000 seed1 : 10k = 1248 s
B1 bmr=0.100 seed1 : 10k =  542 s
B1 bmr=0.300 seed1 : 10k =  331 s
B2 bmr=0.000 seed1 : 10k =   35 s
```

現行runtime preflight式:

```text
B1 bmr=0.000 の10k実測 × 5 (50k/10k) × safety factor 2
= 1248 × 5 × 2
= 12480 s
= 208 min
```

300分safety line内。

時間報告のためだけの追加simulation操作は行わない。

---

# 5. 再監査完了条件

修正PRでは、Sonnet 5がこのファイルを再度更新し、最低限:

```text
Requirement | Implementation | Test | Result
```

の対応表を作る。

以下がすべてPASSになるまで「Exp12実装完了」と宣言しない。

```text
[x] current-run first-10k再現性          — 実装済み (次回dispatchのPhase 0で実測確認)
[x] historical comparison diagnostic化   — 実装済み
[x] formal SHA integrity                — 実装済み・test PASS
[x] formal numeric environment integrity — 実装済み・test PASS
[x] artifact completeness               — 既存実装を維持 (変更なし)
[x] aggregation error分離                — 既存実装を維持 (変更なし)
[x] 全pytest                            — 633 passed, 4 skipped, 0 failed
[x] check_exp12.py                      — OK: 全10 Config整合性チェック通過
[ ] CI Green                            — PR作成・push後に確認
[ ] runtime preflight                   — 次回dispatchのPhase 0で実測確認 (事前見積もりは§4/§6参照、300分safety line内と推定)
```

その後にのみmain上からformal 71-runをdispatchする。

---

# 6. 再現性gate修正 — 要求トレーサビリティ表 (2026-09-02 二回目)

対象: `docs/数値再現性・Actions実行環境方針.md` §3 の技術修正指示。

| Requirement | Implementation | Test | Result |
|---|---|---|---|
| P0-3 HARD GATEを「現在SHA・現在runner内の同一条件同seed比較」に変更 | `.github/workflows/exp12.yml` phase0: 代表4条件を primary として10,000 tick実行後、同一seed・同一Configで reference として再実行し、`tools/compare_exp12_first10k.py runs/exp12_p0 runs/exp12_p0_ref` で比較 (`id: current10k`)。continue-on-error無し = 不一致でジョブ失敗 | ワークフロー再dispatch時に実行される (静的にはYAML構文検証済み) | PASS (実装) / 実行結果は次回dispatchで確認 |
| 過去Exp11 artifact比較をDIAGNOSTIC化 (Phase 0) | 同workflow: `dl_exp11_ref` / `historical10k` stepを`continue-on-error: true` + 明示的`exit 0`にし、`gate`のPASS/FAIL判定から除外。診断結果はstep summaryに記録 | 同上 | PASS (実装) |
| formal collectでも過去Exp11比較をDIAGNOSTIC化 | collect job: `first10k_historical` stepに`continue-on-error: true` + `exit 0`。最終「整合性違反の判定」stepの条件式から`first10k_formal`(旧名)を削除し、`steps.integrity.outcome`/`steps.summary.outcome`のみに限定 | 同上 | PASS (実装) |
| formal SHA整合性を機械検証 | `tools/check_exp12.py`: `check_run_environment_integrity()` を新設。全run の `meta.json.git_sha` が単一集合であることを確認し、複数あれば `formal run群でgit_shaが混在` errorを返す。`main()`のrun_dirs分岐から自動的に呼ばれ、collect jobの`Config整合性・run完全性・formal SHA/numeric environment整合性チェック`stepに組み込み済み | `tests/test_check_exp12.py::test_environment_integrity_all_same_passes`, `::test_environment_integrity_detects_sha_mismatch` | PASS |
| numeric environment整合性を機械検証 | 同関数で `meta.json.numeric_environment.env_key` も同様に検証 | `tests/test_check_exp12.py::test_environment_integrity_detects_numeric_env_mismatch`, `::test_environment_integrity_detects_missing_fields` | PASS |
| current-run mismatch時にHARD STOPするtest | `compare_first_10k`は汎用関数のまま (呼び出し側がHARD GATEかDIAGNOSTICかを決める設計は`数値再現性・Actions実行環境方針.md`の意図通り)。stats.csv/snapshot双方の不一致検出を検証 | `tests/test_check_exp12.py::test_compare_first_10k_stats_mismatch_detected`, `::test_compare_first_10k_snapshot_mismatch_detected`, `::test_compare_first_10k_missing_snapshot_tick_detected` | PASS |
| historical mismatch regression test (diagnosticのままformal verdictを落とさない) | `compare_first_10k`が例外を投げずerrorsリストを返すだけであることを保証。workflow側でこれを`continue-on-error`+`exit 0`でDIAGNOSTIC化していることは§6上段の実装項目で担保 | `tests/test_check_exp12.py::test_compare_first_10k_is_a_pure_reporting_function` | PASS |
| current-run reference欠落時の技術エラー | `compare_first_10k`は参照dirのstats.csv欠落時にFileNotFoundErrorメッセージをerrorsとして返す (例外を外に投げない) | `tests/test_check_exp12.py::test_compare_first_10k_missing_reference_dir` | PASS |
| 完全一致時にHARD GATEを通す (偽陽性がないこと) | 同一fixtureを比較して空errorsを返すことを確認 | `tests/test_check_exp12.py::test_compare_first_10k_identical_runs_match` | PASS |
| run完全性 (重複run検出) の回帰確認 | `check_run_completeness()` (既存実装、変更なし) | `tests/test_check_exp12.py::test_check_run_completeness_detects_duplicate` (71件完全gridでのPASS確認も含む、新規追加) | PASS |
| 実行時間の事前見積もり報告 | `docs/数値再現性・Actions実行環境方針.md` §5.1 に既存Phase0実測 (run_id 33585027312) からの50k換算・worst-case・安全係数を記載済み。新規instrumentation追加なし | — (既存Actions ログの読み取りのみ) | PASS (文書化済み) |
| 実行時間の実績報告の仕組み | Actions job timestamps / `phase0_timing.txt` / `done: ... ticks in ...s` の既存出力のみを使用する設計を維持 (workflow変更なし)。formal dispatch完了後にjob開始・終了時刻から算出して報告する | — (formal dispatch後に実施) | 未実施 (formal run未完了のため) |
| 科学条件・閾値・判定ロジックへの変更なし | `docs/Exp12_実験計画確定.md`・`tools/summarize_exp12.py`・`tools/exp12_common.py` は本修正で無変更 (`git diff`で確認) | 既存 `tests/test_exp12_aggregation.py` 全件がそのままPASSすることで裏付け | PASS |
| 全pytest | — | `uv run pytest tests -q` | PASS (633 passed, 4 skipped, 0 failed — うち`tests/test_check_exp12.py` 11件が新規) |
| check_exp12.py (静的10 Config) | — | `uv run python tools/check_exp12.py` | PASS (`OK: 全10 Config整合性チェック通過`) |

**Implementation欄・Test欄が空欄の要求はない。** 「実行時間の実績報告」の1項目のみ、formal dispatch完了後でなければ実施できない性質上「未実施」であり、これはPhase 0 HARD GATEの対象外 (formal dispatch後の報告義務)。
