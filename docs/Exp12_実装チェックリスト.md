# Exp12 実装チェックリスト — Sonnet 5向け抜け漏れ防止

更新: 2026-09-02
状態: **Exp12実装時の必須監査項目**

> 本書は `docs/Exp12_実験計画確定.md` の科学設計を変更しない。目的は、Exp11実装時に実際に起きた実装漏れ・checker共倒れ・集計形式誤認・artifact回収漏れをExp12で再発させないこと。
>
> 2026-09-02 Exp12初回Phase 0で、過去Hosted Runner artifactとのbit完全一致をHARD GATEにすること自体が不適切と判明した。再現性に関する技術運用は `docs/数値再現性・Actions実行環境方針.md` を本書より優先する。
>
> 科学条件・閾値・判定ロジックは `docs/Exp12_実験計画確定.md` が正本。本書は**実装品質のHARD GATE**である。

---

# 1. Exp11/Exp12で実際に起きた失敗と再発防止

## 1.1 fixed_genes の手書き誤り

Exp11では、Config生成・checker・testが同じ誤った遺伝子名リストを共有し、誤Configを全員でOK判定した。

Exp12では:

- `fixed_genes` の期待値を独自の手書きリストから生成しない
- 実装側は `evosim.genome.GENE_NAMES` から `body_size` のみを除外して導出する
- checker/testは `set(GENE_NAMES) - {"body_size"}` と直接比較する
- `fixed_mask_from_names()` を実際に通す
- B1/B2代表Configで `Simulation()` 初期化 + 短tick実行まで行う

**generator内のローカル定数と比較するだけのtestは禁止。**

## 1.2 snapshot形式の誤認

Exp11ではsummarizerが架空のJSON snapshotを想定した一方、実出力は `snapshots/snap_*.csv` だった。

Exp12ではaggregation testを必ず**本番と同じ形式・名前・列**で行う。

最低限:

```text
snapshots/snap_00001000.csv
snapshots/snap_00002000.csv
...
```

を読むfixtureを使う。

さらに少なくとも1本のend-to-end testは:

```text
実際の Simulation / Recorder で短runを生成
-> 実際に生成された出力tree
-> Exp12 parser / summarizer
```

の順で通す。

**summarizerの都合で作った架空schemaだけを使うtestは禁止。**

## 1.3 runディレクトリ階層の誤認

Exp11ではcheckerが1階層を想定したが、実際のartifact展開後はseed runを含む2階層だった。

Exp12では、workflowが生成・展開する**実際のディレクトリtreeと同じfixture**でchecker/summarizerをテストする。

parserは固定深度を思い込みで決めず、`config.json` / manifest等の実在ファイルを基準にrunを同定する。

## 1.4 artifact回収のページネーション漏れ

Exp11再集計では `actions/download-artifact` 側で255個中199個しか取得できない事故があった。

Exp12では:

- formal collectorはartifact取得後に**期待run key集合と実取得run key集合を完全一致比較**する
- B1 56 + B2 15 = **71 run** の欠落・重複を機械検出する
- 多数artifactの取得はページネーションが保証される方法を使う。過去事故と同じ単一ページ前提を置かない
- `gh run download` またはページネーションを明示処理するAPI方式を優先する
- 過去Exp11 artifactを診断用に取得する場合も、取得できた集合を明示して「全件取れた」と思い込まない

**「download stepがsuccess」だけではformal artifactの完全取得とみなさない。件数・key一致までが成功条件。**

## 1.5 集計エラーを科学結果と誤認

Exp11ではsnapshot未検出が科学的FAILとして流れ、偽のverdictにつながった。

Exp12では:

- formal artifact欠落
- duplicate run
- snapshot欠落
- 必須列欠落
- CSV parse失敗
- current-run再現性reference不足
- unexpected run key

を `AggregationError` 相当の**技術的集計エラー**として扱う。

技術的集計エラーが1件でもある場合:

```text
summarizer 非0終了
exp12_verdict.txt に確定科学verdictを書かない
workflowをfailure扱い
```

とする。

過去Exp11 artifactの診断比較が取得不能・不一致であることだけではformal scientific verdictを失敗扱いにしない。診断未完了として明記する。

`WINDOW_INSUFFICIENT / REVIEW` 等の科学結果とは明確に分離する。

## 1.6 過去Hosted Runnerとのbit完全一致をHARD GATEにした誤り

Exp12初回Actions run `33585027312` では、現在のExp12代表runを過去Exp11 artifactとbit完全比較したため、3/4代表条件が不一致となりPhase 0で停止した。

科学コード・対応Configに差がなくても、Hosted Runnerを跨いだ過去runとのbit完全一致は保証できない。

以後:

- **現在SHA・現在runner内の同一条件同seed比較 = HARD GATE**
- **過去日時のartifactとの比較 = DIAGNOSTIC**

とする。詳細は `docs/数値再現性・Actions実行環境方針.md` を参照。

---

# 2. 実装対象の必須存在確認

最低限、以下が揃うこと。

```text
tools/exp12_common.py
tools/make_exp12_configs.py
tools/check_exp12.py
tools/summarize_exp12.py
configs/exp12/*.json
.github/workflows/exp12.yml
tests/test_exp12_configs.py
tests/test_exp12_aggregation.py
```

trajectory fitを別module化した場合、そのmoduleとtestも対象に含める。

実装完了時に `git diff --name-status` / repository treeを見て、**計画に書かれた成果物が実際に存在することを一つずつ確認する。**

---

# 3. Config / matrix HARD GATE

以下をコードでassertする。

```text
B1 bmr = [0.000, 0.050, 0.075, 0.100, 0.150, 0.200, 0.300]
B1 seed = 1..8
B1 jobs = 56

B2 bmr = [0.000, 0.100, 0.300]
B2 seed = 1..5
B2 jobs = 15

total jobs = 71
```

test側では、実装のmatrix定数をそのまま期待値として再利用せず、**事前登録した上記集合を独立oracleとして比較する。**

各Configについて:

- `ticks == 50000`
- `memory_tau == 10`
- `response_gain == 64`
- `stats_interval == 20`
- `snapshot_interval == 1000`
- `max_population_halt == 10000`
- `bmr_core` round-trip一致
- body_sizeのみ進化ON
- 他13 gene canonical固定
- environment / phenotype / placementがExp11対応条件と一致

を検証する。

---

# 4. Aggregation / classifier HARD GATE

`tests/test_exp12_aggregation.py` は最低限、以下を含む。

1. production-format snapshot CSVからbody_size分位点が正しく出る
2. production-format snapshot CSVからgeneration median/Q90/maxが正しく出る
3. workflowと同じrun directory treeからrunを全件発見できる
4. snapshot欠落で非0終了し、科学verdictを確定しない
5. 必須列欠落で非0終了し、科学verdictを確定しない
6. run欠落で非0終了
7. duplicate runで非0終了
8. unexpected run keyで非0終了
9. **current-run referenceとの** first-10k mismatch -> HARD STOP
10. current-run reference欠落 -> 技術エラーで停止
11. **historical Exp11 reference mismatchはdiagnosticでありformal verdictを直接failureにしない**
12. formal SHA / numeric environment混在をintegrity errorにする
13. tick slopeの符号・正規化
14. clear decelerationを `DELAY_CONTINUES` に誤分類しない
15. sustained negative driftを正しく分類
16. generation-space slope計算
17. asymptotic fit success / failure / boundary
18. Matter coupling difference-correlation
19. B2 method-control pass/fail
20. per-bmr 6/8集約
21. global verdictの各主要分岐
22. 技術エラーがあるとglobal scientific verdictを出さない

可能な限りtable-driven testにし、判定分岐を網羅する。

---

# 5. first-10k再現性 HARD GATE

HARD GATEは**過去Exp11 artifactとのbit一致ではなく、現在の実行環境内での再現性**に対して行う。

P0代表条件について:

```text
現在SHA / 現在runner / 現在numeric environment
Exp11相当の参照Config run
vs
Exp12 Config run
same scientific condition / same seed
```

を比較し完全一致させる。

比較器について:

- scientific列を明示列挙またはschemaから安全に選ぶ
- path / timestamp / artifact name等の非科学metadataだけを除外する
- snapshot CSV実形式を比較する
- float比較の許容差を勝手に広げない
- mismatch時に「どのrun / tick / file / columnが違ったか」を報告する

P0代表条件が現在環境内で一致しなければformal dispatchしない。

過去Exp11 artifactとのfirst-10k比較は別のdiagnosticとして残してよい。そこではcode / Config / numeric_environment差とdivergence開始点を併記し、bit mismatch単独でHARD STOPしない。

---

# 6. Workflow HARD GATE

`.github/workflows/exp12.yml` は最低限、次の段階を分離する。

```text
setup / static validation
-> Phase 0 current-run determinism gates
-> historical Exp11 comparison (diagnostic, optional)
-> runtime preflight
-> formal 71-run matrix
-> per-run artifact upload
-> collector (if: always())
-> completeness / SHA / numeric-environment integrity check
-> summarizer
-> final artifact upload
```

formal matrixはPhase 0 HARD GATE成功後だけ起動する。

collectorは、途中job failureがあっても完了済みartifactを可能な限り回収する。ただし不完全なまま科学verdictを確定しない。

正式run開始後は:

- SHA
- scientific Config
- numeric environment
- 判定ロジック

を固定する。

過去Exp11 artifactとのbit mismatchをformal workflow failure条件に含めない。

---

# 7. 実装完了時の「要求トレーサビリティ表」を必須化

Sonnet 5はPR作成前に、少なくとも以下の形式で自己監査する。

```text
Requirement | Implementation | Test | Result
----------------------------------------------
71 matrix   | exp12.yml ...  | test_xxx | PASS
fixed genes | ...            | ...      | PASS
real CSV    | ...            | ...      | PASS
...
```

対象は:

- `docs/Exp12_実験計画確定.md` の科学設計
- `docs/数値再現性・Actions実行環境方針.md` の技術amendment
- Phase 0
- 保存・測定指標
- tick-space解析
- generation-space解析
- asymptotic fit
- Matter coupling
- B2 method control
- classifier / verdict
- current-run first-10k integrity
- formal SHA / numeric environment integrity
- artifact completeness
- 本書の再発防止項目

**Implementation欄またはTest欄が空欄の要求が1つでもあれば、実装完了と宣言しない。**

この表はPR本文または `docs/Exp12_実装監査.md` に残す。

---

# 8. 二巡目レビューを必須化

ローカルtest Green後、すぐpushしない。

1. `docs/Exp12_実験計画確定.md` を先頭から再読
2. `docs/数値再現性・Actions実行環境方針.md` を再読
3. 本書を再読
4. `git diff` を先頭から再レビュー
5. 要求トレーサビリティ表を埋める
6. 未実装・未test・暗黙仮定を列挙
7. それらを解消
8. `uv run pytest tests -q`
9. `tools/check_exp12.py`
10. current-run first-10k preflight
11. その後にPRへpush

CIはこの二巡目レビューの代替ではない。

---

# 9. formal dispatch直前の最終チェック

以下がすべてYESの場合のみ正式71-runをdispatchする。

```text
[ ] 正本と技術amendmentと実装差分を再確認した
[ ] 必須ファイルが全て存在する
[ ] 71 matrix集合が完全一致する
[ ] fixed_genesをcanonical sourceから検証した
[ ] production-format end-to-end aggregation testが通った
[ ] 欠落/重複/parse errorでverdictを出さないtestが通った
[ ] current-run P0代表first-10kが完全一致した
[ ] 過去Exp11比較をHARD GATEにしていない
[ ] formal SHA / numeric environment整合性testが通った
[ ] runtime preflightが基準内
[ ] 全pytest Green
[ ] check_exp12.py Green
[ ] PR CI Green
[ ] main上の正式workflowを実行する
```

1項目でもNOなら正式dispatchしない。

---

# 10. Sonnet 5の完了報告

完了報告では必ず分けて記載する。

1. 実装したファイル
2. 要求トレーサビリティ表
3. ローカルtest結果
4. checker結果
5. current-run first-10k preflight結果
6. 過去Exp11 diagnostic比較結果
7. runtime preflight結果
8. GitHub CI結果
9. formal dispatchを実施したか / していないか
10. 未確認事項

「CI Greenだったので問題なし」の一文だけで完了扱いにしない。

---

# 11. 実行時間の見積もり / 実績報告

時間報告のためだけに新しいsimulation instrumentationを追加しない。

既存の:

- Actions job start/end
- workflow start/end
- `done: ... ticks in ...s`
- `phase0_timing.txt`

を使う。

formal dispatch前に:

- 代表条件の10k実測
- 50k単純換算
- 安全係数を含むworst-case
- max-parallel
- 前提 / 不確実性

を報告する。

formal完了後に:

- workflow全体wall-clock
- Phase 0時間
- formal matrix wall-clock
- run時間 median / P90 / max（取得できる範囲）
- collect時間
- 事前予測 vs 実績

を結果考察またはNOTESへ残す。

Exp12初回Phase 0の既存実測と現行安全係数では、B1 bmr=0.000 seed1から算出した50k保守的worst-caseは約208分である。詳細は `docs/数値再現性・Actions実行環境方針.md` を参照。
