# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と正本を必ず読むこと。

## 現在の参照順

1. `docs/次の実験計画.md` — 現在の司令塔
2. `docs/数値再現性・Actions実行環境方針.md` — **Exp12初回Phase 0を受けた技術amendment。再現性gateはこれを優先**
3. `docs/Exp12_実験計画確定.md` — **Exp12事前登録・科学設計・判定の正本**
4. `docs/Exp12_実装チェックリスト.md` — **実装品質HARD GATE**
5. `docs/Exp12_レビュー反映判断.md` — Opus 5レビューへの採否
6. `docs/Exp11_考察.md` — Exp12へ進む科学的理由
7. `docs/Exp11_結果考察.md` — Exp11正式実測値・正式判定
8. `docs/V1.7_基礎維持代謝仕様案.md` — V1.7 `bmr_core` 実装仕様
9. `docs/LUCA参照モデル方針.md`
10. `docs/実験結果保存方針.md`
11. `docs/バージョニング方針.md`

`docs/Exp12_実験計画案.md` はレビュー前の旧ドラフト。科学条件・閾値・判定ロジックは `Exp12_実験計画確定.md` を優先する。

ただし、同書の旧P0-3および正式run first-10kにある「過去Exp11 artifactとのbit完全一致をHARD GATE」とする部分は、実運用で成立しないことが確認されたため `docs/数値再現性・Actions実行環境方針.md` を優先する。

レビュー原文に別案があっても、反映判断・確定正本・技術amendmentをAIが独自変更しない。

---

## 現在地

```text
V1.4 / Exp08                         完了 / Green
V1.5 / Exp09                         完了 / Green
V1.6 / Exp10                         完了 / Green
V1.7 bmr_core                        実装済み
Exp11 Phase B                        255 run完了
Exp11 formal verdict                 NO_SELECTION / REVIEW
Exp11 collect修正・正式再集計       完了
Exp11考察                            完了
Exp12 Opus 5レビュー                 完了・反映済み
Exp12事前登録                        確定
Exp12実装                            完了
Exp12初回Phase 0                     過去artifact bit比較で安全停止
Exp12 formal 71 run                  未起動
P0-3 / collect再現性gate修正         ← 現在
```

---

# Exp12の目的

Exp11 B1では `bmr_core` 増加に伴い10k時点のbody_sizeが大型側へ系統的に移動したが、late driftが残っていた。

Exp12は:

```text
平衡変更
vs
単なる進化速度・世代交代の遅延
```

を50k長期runで識別する。

**Exp12は恒久 `bmr_core` 値を選定する実験ではない。**

---

# Exp12 正式構成

## B1主実験

```text
bmr_core = 0.000, 0.050, 0.075, 0.100, 0.150, 0.200, 0.300
seed     = 1..8
56 run
```

Exp11 B1と同じlight-only / light specialist。

## B2 method positive control

```text
bmr_core = 0.000, 0.100, 0.300
seed     = 1..5
15 run
```

Exp11 B2と同じchem-only / chemical specialist。

```text
総計 = 71 run
```

共通:

```text
ticks=50000
initial_population=100
initial_energy=50
initial_matter=0.8
body_sizeのみ進化ON
他13遺伝子固定
memory_tau=10
response_gain=64
stats_interval=20
snapshot_interval=1000
max_population_halt=10000
```

B3はExp12へ含めない。

詳細は必ず `docs/Exp12_実験計画確定.md` を参照する。

---

# Exp12再現性gate — 技術amendment

2026-09-02のExp12初回Actions run `33585027312` では、過去Exp11 artifactとのfirst-10k bit完全一致をHARD GATEにしたためPhase 0で停止した。正式71 runは1本も起動していない。

今後は再現性を分ける。

## HARD GATE

```text
現在SHA / 現在runner / 現在numeric environment内で
同一科学条件・同一seedが完全再現すること
```

これによりConfig差、harness差、RNG干渉、非決定性を検出する。

## DIAGNOSTIC

```text
過去日時・別Hosted RunnerのExp11 artifactとのbit比較
```

は記録するが、bit mismatch単独でformal runを無効化しない。科学コード差、Config差、numeric environment、divergence開始点を合わせて報告する。

正式71 runのintegrityは:

- 71 run完全性
- Config整合性
- formal SHA一致
- numeric environment整合性
- 出力完全性
- aggregation errorなし

で判定する。

詳細は `docs/数値再現性・Actions実行環境方針.md`。

**現在mainの `exp12.yml` を再現性gate修正前のまま再dispatchしてはいけない。**

---

# Exp12 Phase 0 HARD GATE

正式71-run dispatch前に以下を全て通す。

1. Config完全性
2. Simulation smoke
3. 現在環境内の代表条件first-10k完全再現
4. Matter保存 / Energy台帳 / 決定性 / RNG非干渉
5. runtime preflight
6. CI Green

runtime基準:

```text
job timeout = 350 min
predicted worst-case 50k <= 300 min を正式dispatch目安
```

超える場合、run長をAI判断で短縮せず `RUNTIME_PREFLIGHT_FAIL / REVIEW` として停止する。

---

# Exp12解析の絶対要点

単純な「後半傾きが負」だけでdelayと判定しない。

## Tick-space

```text
20–30k
30–40k
40–50k
```

の3windowで正規化傾き `S1/S2/S3` を測り、減速を明示的に判定する。

```text
|S3| <= 0.05
```

はlate stationarity sentinelだが単独判定には使わない。

低下が連続していても傾きが明確に弱まる場合は `CONVERGING_NOT_PROVEN` とし、`DELAY_CONTINUES` へ入れない。

## Generation-space

各snapshotで:

```text
generation median
Q90
max_generation
```

を計算する。

body_size vs median-generation trajectoryを作り、late generation slope `S_gen` を測る。

`max_generation` 単独で進化機会を判定しない。

## 漸近平衡fit

```text
b(t) = b_inf + A * exp(-(t-10000)/tau)
```

を診断として実施するが、fit単独で科学結論を出さない。

## Lower-bound sensitivity

```text
p_021
p_023
p_025
```

を併記する。0.21だけで長期平衡を判定しない。

## Matter coupling

30–50kのsnapshot差分でbody_sizeとMatter/ecology指標のSpearman相関を計算し、所定条件で `MATTER_COUPLED` を付ける。

詳細な閾値・式・verdictロジックは正本を読むこと。AIが簡略化しない。

---

# Exp12 run科学分類

主分類:

```text
INTERIOR_EQUILIBRIUM
LOWER_BOUND_EQUILIBRIUM
DELAY_CONTINUES
CONVERGING_NOT_PROVEN
WINDOW_INSUFFICIENT
```

全体verdict:

```text
EQUILIBRIUM_SHIFT_SUPPORTED
EQUILIBRIUM_SHIFT_SUPPORTED_WITH_ECOLOGICAL_COUPLING
DELAY_SUPPORTED
WINDOW_INSUFFICIENT / REVIEW
INVALID_OR_METHOD_REVIEW
```

判定閾値を結果確認後に変更しない。

---

# Exp12実装修正の最低要件

既存実装に対して、formal再dispatch前に最低限:

- P0-3をcurrent-run同一環境比較へ変更
- historical Exp11 comparisonをdiagnosticへ降格
- formal collectorからhistorical bit mismatchによるfailureを除去
- formal SHA / numeric environment整合性をHARD GATE化
- 対応回帰tests
- 要求トレーサビリティ表更新

を行う。

`docs/Exp12_実装チェックリスト.md` の全項目を満たすこと。

---

## Actions・CI・push運用

CIは最終的な独立確認であり、途中実装のデバッグ手段として繰り返し使用しない。

- PRへpushするたび通常CIが自動実行されることを前提とする
- 細かな途中経過ごとにpushせず、論理的に一まとまりの変更単位までローカルで完成させる
- push前に変更範囲に対応するテストをローカルで実行する
- Pythonコード、Config、集計処理、workflow、依存関係を変更した場合は、原則としてpush前に `uv run pytest tests -q` を通す
- シミュレーション結果の不変性に関係する変更では、現在の再現性方針に従って検証する。過去Hosted Runner artifactとのbit mismatch単独を失敗条件にしない
- ローカルテスト失敗中の状態をCIで原因調査する目的だけでpushしない
- CI failure修正は原因と影響範囲をローカルで確認し、関連修正をまとめてから再pushする
- 新Exp、コアロジック、Config、出力形式、集計、CIを変更した場合は、本番dispatch前にCI Greenを必須とする
- Markdown、結果考察、静的plotだけの変更はまとめてpushし、文言修正ごとの連続pushを避ける
- CIを省略するために科学コードと文書変更を不自然に混在させない

AIは作業完了報告時に:

1. ローカルで実行したテスト
2. GitHub CI状態
3. Phase 0結果
4. runtime preflight見積もり
5. formal dispatch状態
6. 未確認事項

を分けて記載する。

正式run開始後はGit SHA・数値環境・科学コード・Config生成則・判定ロジックを固定する。

run status:

```text
COMPLETE
EXTINCT
POP_HALT
INCOMPLETE_RESOURCE
INTEGRITY_FAIL
```

- EXTINCT / POP_HALT = 科学的結果
- timeout / runner中断 / artifact欠落 = INCOMPLETE_RESOURCE
- formal内のSHA / Config / numeric environment等のintegrity violation = 正式解析から除外
- 過去runとのbit mismatch単独はINTEGRITY_FAILにしない
- 技術的不完了だけ同一SHA/Configで再実行可

---

## 実行時間の見積もり・実績報告

正式実験では、時間報告のためだけの新規instrumentationを追加しない。

既存Actions timestamps、job duration、`done: ... ticks in ...s`、`phase0_timing.txt` を使う。

formal dispatch前に:

- 代表run実測
- formal ticksへの換算
- safety factor込みworst-case
- max-parallel
- 前提 / 不確実性

を報告する。

Exp12初回Phase 0実測から、B1 bmr=0.000 seed1の50k保守的worst-caseは現行式で約208分。300分safety line内。

formal終了後は:

- workflow wall-clock
- Phase 0時間
- formal matrix wall-clock
- run時間 median / P90 / max（取得できる範囲）
- collect時間
- 予測 vs 実績

をNOTESまたは結果考察へ残す。

---

## 小型化に関する絶対原則

**小型化を抑えるためだけの人工的ペナルティは入れない。**

V1.7 `bmr_core` はbody_sizeへ直接罰点を付けるものではなく、LUCA-inspired参照に基づく全生命共通の一般生理則として扱う。その結果としてサイズ選択圧が変わることを許容する。

`max_population_halt` は計算安全停止であり、生態ルールとして個体を殺したり繁殖を抑えたりしない。

---

## LUCA-inspired参照方針

LUCAそのものを再現しない。

- 現実から構造・因果・スケーリング・比率を主に借りる
- 未校正のEnergy / Matter / tickへSI絶対値を直接移植しない
- LUCAらしさへ適応度を与えない
- 地球史どおりの進化結果を直接指定しない
- 現実的な初期・基礎ルールを置いた後の進化は自然選択へ任せる

---

## プロジェクト絶対原則

1. 適応度を直接計算しない
2. 種クラスを作らない
3. 寿命値を直接作らない
4. コストは物理・生理則から導く
5. Matter保存・Energy台帳を守る
6. 乱数系列と決定性を意識する
7. 想定外戦略を許容する
8. 特定生態型へ直接ボーナスを与えない
9. 原則1軸ずつ変更する
10. 遺伝子の存在と進化経路の成立を区別する
11. 比較するEnergy戦略は単独成立性を先に確認する
12. 行動に暗黙の知能・未来予測を勝手に導入しない
13. 実験結果を見て同じ実験の候補・閾値を後付け変更しない
14. 科学的STOP/REVIEWと実行失敗・技術的不完了を区別する

---

## 実験結果保存

`docs/実験結果保存方針.md`に従う。文字サマリーだけで正式実験を閉じない。

- GitHub: 結果考察 / NOTES / 集計plot / 代表図 / README / 実行時間の予測実績比較
- 全生データ・全画像: Google Drive / Actions artifact

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
