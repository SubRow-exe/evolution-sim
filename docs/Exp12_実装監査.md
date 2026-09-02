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
[ ] current-run first-10k再現性
[ ] historical comparison diagnostic化
[ ] formal SHA integrity
[ ] formal numeric environment integrity
[ ] artifact completeness
[ ] aggregation error分離
[ ] 全pytest
[ ] check_exp12.py
[ ] CI Green
[ ] runtime preflight
```

その後にのみmain上からformal 71-runをdispatchする。
