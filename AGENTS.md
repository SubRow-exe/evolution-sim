# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と正本を必ず読むこと。

## 現在の参照順

1. `docs/次の実験計画.md` — 現在の司令塔
2. `docs/Exp11_実験計画案.md` — **Exp11事前登録の正本・人間判断確定**
3. `docs/V1.7_基礎維持代謝仕様案.md` — **V1.7実装仕様の正本・人間判断確定**
4. `docs/V1.7_Exp11_レビュー判断.md` — Claudeレビューへの採否。レビュー原文より優先
5. `docs/LUCA参照モデル方針.md`
6. `docs/Exp10_結果考察.md`
7. `experiments/exp10_phaseB_20260901/NOTES.md`
8. `docs/V1.6_行動則設計案.md`
9. `docs/実験結果保存方針.md`
10. `docs/バージョニング方針.md`

古いExp10中間報告、PRレビュー原文、過去の240-run案より上記を優先する。レビュー原文に別案があっても、人間判断済み正本を独自に変更しない。

---

## 現在地

```text
V1.4 / Exp08                         完了 / Green
V1.5 / Exp09                         完了 / Green
V1.6 / Exp10                         完了 / Green
V1.6行動原理                         GO
Exp10 Phase C                        deferred
LUCA-inspired参照方針                採用
V1.7 bmr_core / Exp11設計            確定
V1.7 / Exp11実装                     ← 次
```

### V1.7着手前の必須処理

Exp10採用値は:

```text
memory_tau    = 10
response_gain = 64
```

だが通常defaultの `response_gain` はまだ16。

V1.7へ混ぜず先に別commitで:

```text
response_gain 16 -> 64
-> tests / CI基準更新
-> v1.6-final保存
-> その確定commitからV1.7実装
```

を行う。

---

## V1.7 実装仕様

パラメータ名は**`bmr_core`に統一**する。

```text
BMR = bmr_core + (bmr_coef - bmr_core) * M^0.75
bmr_coef = 0.3
0 <= bmr_core <= 0.3
```

- `bmr_core=0` -> V1.6完全一致
- `M=1` -> BMR=0.3維持
- M<1では縮小不能core負担が相対的に重い
- M>1ではV1.6よりBMRが相対的に低くなりcore償却メリットが生じる。これは意図的
- 純加算式は検討済みだが、M=1 referenceの総BMRまで上げるため不採用
- `bmr_core` は遺伝子にしない

温度、body_size上下限、繁殖、吸収、行動、捕食、新規遺伝子はV1.7では変更しない。

### Config事故防止

非ゼロ `bmr_core` のJSON round-trip test、run summary/fingerprint、保存config、全45 Configの値一致checkerを必須とする。未知キーが黙って落ちて0として走ることを許容しない。

---

## Exp11 正式事前登録

候補15水準:

```text
0.000, 0.005, 0.010, 0.015, 0.020,
0.025, 0.030, 0.040, 0.050, 0.060,
0.075, 0.100, 0.150, 0.200, 0.300
```

Phase Bはbody_sizeのみ進化ON、他13遺伝子固定。

```text
B1 light-only / lightspec : 15 × seed1-8 = 120
B2 chem-only  / chemspec  : 15 × seed1-5 =  75
B3 mixed      / generalist: 15 × seed1-4 =  60
合計                         255 run
```

共通:

```text
ticks=10000
initial_population=100
initial_energy=50
initial_matter=0.8
memory_tau=10
response_gain=64
stats_interval=20
snapshot_interval=1000
max_population_halt=10000
```

placement:

```text
B1 random
B2 vent
B3 random
```

255 matrix jobを1回のworkflow_dispatchで登録し、`max-parallel=20`。途中結果で候補を削らない。

### 判定要点

- B1 `bmr_core=0`: `p_low>=0.50` が5/8以上で対照妥当
- B1 candidate per-seed Green:
  - COMPLETE
  - `p_low<0.25`
  - `p_high<0.25`
  - `max_generation >= max(5, ceil(0.5*g0))`
  - `late_drift<=0.10`
  - integrity OK
- 7/8以上で候補B1 Green
- **連続3候補B1 Green**で最小側をTRANSITION_ELIGIBLE
- B2 baseline healthy COMPLETE >=3/5、B3 >=3/4
- B2/B3 vetoは `bmr_core=0` baselineに対する重大悪化のみ
- vetoされない最小TRANSITION_ELIGIBLEを恒久値候補
- どれも選べなければ `NO_SELECTION / REVIEW`。後付け変更しない

詳細・正確な式は必ず `docs/Exp11_実験計画案.md` を参照する。

---

## Actions運用

正式dispatch前にV1.7実装・45 Config・`exp11.yml`・checker/summarizer/testsをmainへマージする。

run status:

```text
COMPLETE
EXTINCT
POP_HALT
INCOMPLETE_RESOURCE
INTEGRITY_FAIL
```

- EXTINCT / POP_HALT = 科学的結果
- timeout / runner中断 / output欠落 = INCOMPLETE_RESOURCE（同一SHA/Configで技術的再実行可）
- integrity violation = 正式解析から除外

job timeoutは350分を基準。collectorは可能な限り完了済み結果を保持する。

正式run開始後はGit SHA・数値環境・科学コード・Config生成則・判定ロジックを固定する。

---

## 小型化に関する絶対原則

**小型化を抑えるためだけの人工的ペナルティは入れない。**

V1.7 `bmr_core` はbody_sizeへ直接罰点を付けるものではなく、LUCA-inspired参照に基づく全生命共通の一般生理則として導入する。その結果としてサイズ選択圧が変わることを許容する。

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

- GitHub: 結果考察 / NOTES / 集計plot / 代表図 / README
- 全生データ・全画像: Google Drive / Actions artifact

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
