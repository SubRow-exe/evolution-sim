# 数値再現性・GitHub Actions実行環境方針

更新: 2026-09-02
状態: **正式運用ルール**

## 目的

本シミュレーションはseedとConfigを固定しても、実行日・GitHub Hosted Runner・数値ライブラリ等が異なる過去runとのbit完全一致を常に保証できるとは限らない。

`math.sin/cos/atan2/hypot/exp/pow` 等の微小な浮動小数点差が行動へ入り、長期では個体配置・出生死亡・population等へ増幅されうる。このため、**同一実験内の決定性確認**と、**過去実験artifactとの再現確認**を同じ意味で扱わない。

本書はExp12 Phase 0で実際に発生した事例を踏まえ、今後の実験でも共通適用する。

---

# 1. Exp12 Phase 0で起きた事例

対象Actions run:

```text
Exp12 run_id = 33585027312
head SHA     = e042a682c887e6132e7bcc15e70ec28133a9e15d
実行日       = 2026-09-02
```

結果:

```text
P0-1 Config / Simulation smoke       PASS
Exp12 unit tests                     101 passed
保存則・決定性tests                  7 passed
P0-3 過去Exp11 first-10k完全一致     FAIL
P0-5 runtime preflight               skipped
正式71-run matrix                    未起動
```

P0-3では代表4条件のうち3条件で過去Exp11 artifactと不一致になった。

```text
B1 bmr=0.000 seed1 : tick 2380付近から差
B1 bmr=0.300 seed1 : tick 1560付近から差
B2 bmr=0.000 seed1 : tick 560付近から差
B1 bmr=0.100 seed1 : 比較PASS
```

最初に差が観測された列にはV1.6 temporal sensingの観測値 (`dq_*`, `turn_factor_*`, `sigma_eff_*` 等) が含まれた。その後軌跡自体も分岐し、例としてB1 bmr=0.000 seed1の10k最終populationは:

```text
Exp11 : 5852
Exp12 : 5968
```

となった。

一方、確認できた範囲では:

- Exp11正式run SHA `8da7311a...` からExp12 SHA `e042a682...` まで `evosim/` 科学コード変更なし
- 対応するB1 bmr=0.000 ConfigはGit blob SHAまで一致
- Ubuntu 24.04 runner image versionは同じ
- NumPy等主要数値依存も同系列
- Hosted Runnerの割当regionはExp11 `westus2`、Exp12 `eastus`

だった。

したがって、**過去日時・別Hosted Runnerでのbit完全一致をPhase 0のHARD GATEにする設計自体が強すぎた**と判断する。

なお、region差そのものを単独の根本原因と断定しない。重要なのは、Hosted Runner間の数値実行環境を完全同一とみなして過去artifactとのbit一致を要求してはいけない、という点である。

---

# 2. 再現性を3段階に分ける

## Level A — 同一formal実験内の完全性 / HARD GATE

同一formal実験群では以下を固定・検証する。

- Git SHA
- scientific Config
- seed
- Python / NumPy等のnumeric environment
- workflow / Config生成則
- 判定ロジック

同一formal実験内でこれらが混在した場合はintegrity violationとして扱う。

## Level B — 現在環境内の決定性 / HARD GATE

実装変更後のPhase 0では、**同じ現在のrunner・現在SHA・現在のnumeric environment内**で、同一科学条件・同一seedの参照runと対象runが一致することを確認する。

目的は:

- Config生成差
- parser / harness差
- 観測追加によるRNG干渉
- 非決定的な処理順
- 実装漏れ

を検出すること。

ここでの不一致はHARD STOP。

## Level C — 過去artifactとの再現性 / DIAGNOSTIC

過去日時・別Hosted Runnerのartifactとのfirst-10k比較は有用なので残すが、**bit不一致だけではINTEGRITY_FAILにしない。**

代わりに:

1. scientific code差分
2. Config差分
3. seed
4. numeric_environment
5. divergence開始tick
6. population / body_size / generation / Energy / Matter等の主要差

を診断として記録する。

同一条件なのに大きな系統差が出た場合は科学解釈上の注意事項として残す。

---

# 3. Exp12への技術的修正指示

`docs/Exp12_実験計画確定.md` の科学目的・71-run条件・判定閾値は変更しない。

ただし、同書の旧P0-3および正式runの「過去Exp11 artifactとのbit完全一致をHARD GATEにする」記述については、**本書を技術的amendmentとして優先する。**

Exp12を再dispatchする前にSonnet 5は以下を実装する。

### P0-3の変更

旧:

```text
現在のExp12 run == 過去Exp11 artifact
bit完全一致しなければHARD STOP
```

新:

```text
現在SHA / 現在runner内で
Exp11相当の参照Config run と Exp12 Config run を
同じ科学条件・同じseedで比較
-> bit完全一致をHARD GATE
```

過去Exp11 artifactとの比較は別stepでDIAGNOSTICとして実施・保存してよいが、単独ではPhase 0を落とさない。

### 正式71-run collectの変更

旧:

```text
全71 runを過去Exp11 artifactとbit比較
mismatch -> workflow failure / INTEGRITY_FAIL
```

新:

正式実験のHARD GATEは:

- 71 run完全性
- Config整合性
- formal SHA一致
- numeric environment整合性
- scientific出力欠落なし
- aggregation errorなし

とする。

過去Exp11 first-10k比較は診断表として残してよいが、過去runnerとの差だけでformal runを無効化しない。

### テスト

少なくとも:

- 現在環境内の同一条件・同seed完全一致 test
- Config差がある場合にHARD STOPするtest
- 過去reference mismatchがdiagnosticでありformal verdictを直接失敗させないtest
- formal SHA / numeric environment混在をintegrity errorにするtest

を追加する。

---

# 4. 将来の実験での原則

新しい実験を過去実験から延長するときは、最初に以下を判断する。

```text
比較したいのは
A. 同一環境内の決定性か
B. 過去artifactの歴史的再現性か
```

Aならbit完全一致をHARD GATEにできる。

BはHosted Runnerを跨ぐ限り原則diagnosticとし、科学コード / Config / numeric environmentを合わせて解釈する。

将来どうしても日時を跨いだbit完全再現が必要になった場合は、Hosted Runner任せではなく、より強く固定した実行環境を別途検討する。その必要がない実験では追加コストを負わない。

---

# 5. 実行時間の見積もりと実績報告

今後の正式実験では、**新しい計測処理を追加せず、すでにActions / simulation logに存在する時刻・run時間を利用して**以下を残す。

## 5.1 事前見積もり

formal dispatch前に最低限:

- 代表条件の実測tick数と所要時間
- そこからのformal run長への単純換算
- 既存の安全係数を用いたworst-case
- `max-parallel` を明記
- 見積もりの前提と不確実性

を記録する。

Exp12 run `33585027312` の既存Phase 0実測:

```text
B1 bmr=0.000 seed1 : 10k = 1248 s = 20.8 min
B1 bmr=0.100 seed1 : 10k =  542 s =  9.0 min
B1 bmr=0.300 seed1 : 10k =  331 s =  5.5 min
B2 bmr=0.000 seed1 : 10k =   35 s =  0.6 min
```

50kへの単純5倍換算:

```text
B1 bmr=0.000 : 約104 min
B1 bmr=0.100 : 約45 min
B1 bmr=0.300 : 約28 min
B2 bmr=0.000 : 約3 min
```

現行runtime preflightの安全係数2倍を使うと、B1 bmr=0.000基準の保守的worst-caseは:

```text
1248 s × 5 × 2 = 12480 s = 208 min
```

であり、300分のformal dispatch safety line内。

ただしpopulation変化によりtick単価が変化するため、単純5倍は予測値であり保証値ではない。

formal matrixは:

```text
71 run
max-parallel = 20
```

なので、全体wall-clock見積もりは各job時間の分布とActions schedulingに依存する。過度に精密な予測値は出さず、根拠付き概算として扱う。

## 5.2 実績報告

正式run完了後は既存Actions情報から最低限:

- workflow開始〜終了のwall-clock
- Phase 0所要時間
- formal matrix開始〜最終job終了のwall-clock
- run/job所要時間のmedian / P90 / max（取得できる範囲）
- collect所要時間
- 事前worst-case見積もりと実績最大jobの比較
- 予測差が大きかった場合の理由（population、POP_HALT、runner差等）

を結果考察またはNOTESに残す。

**時間報告のためだけにsimulationへ新規instrumentationを追加しない。** Actionsのjob timestamps、既存の `done: ... ticks in ...s`、既存 `phase0_timing.txt` 等を使う。

---

# 6. Exp12再開手順

Sonnet 5は次の順で進める。

```text
1. 本書を読む
2. docs/Exp12_実験計画確定.md を読む
3. docs/Exp12_実装チェックリスト.md を読む
4. P0-3 / formal collectの過去artifact bit-HARD-GATEを本書どおり修正
5. 回帰tests / 全tests / checker
6. 現在環境内の再現性Phase 0
7. runtime preflight（既存測定だけを使用）
8. CI Green
9. main上からExp12正式71-run dispatch
10. 終了後、科学結果に加えて予測時間 vs 実績時間を報告
```

現在の `exp12.yml` を修正せずそのまま再dispatchしてはいけない。
