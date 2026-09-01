# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と正本を必ず読むこと。

## 現在の参照順

1. `docs/次の実験計画.md` — 現在の司令塔
2. `docs/Exp11_実験計画案.md` — **レビュー中の次実験。未承認・未実装**
3. `docs/V1.7_基礎維持代謝仕様案.md` — **レビュー中の次世界ルール。未承認・未実装**
4. `docs/Exp10_結果考察.md` — Exp10正式結果・V1.6最終判断
5. `experiments/exp10_phaseB_20260901/NOTES.md` — Exp10正式Phase B実測
6. `docs/LUCA参照モデル方針.md` — 今後の祖先・基準生物の現実側アンカー
7. `docs/V1.6_行動則設計案.md` — 現行行動則
8. `docs/Exp10_実験計画案.md` — Exp10事前登録
9. `docs/実験結果保存方針.md`
10. `docs/バージョニング方針.md`

古い中間報告・過去レビューより、上記の新しい正本を優先する。

## 現在地

```text
V1.4 / Exp08                       完了 / Green
V1.5 / Exp09                       完了 / Green
V1.6 temporal biased random walk   実装済み
Exp10 Phase 0 / A / 正式B          完了 / Green
V1.6行動原理                       人間判断でGO
Exp10 Phase C                      deferred
Exp10                              完了
LUCA-inspired参照方針              採用
V1.7 / Exp11                       レビュー中・未実装 ← いま
```

Exp10正式Phase Bは、初回の進化OFF実装漏れを修正後、全14遺伝子固定で200 runを最初から再実行した。
旧B1/B2は正式結果ではなくreference / exploratory扱い。

正式結果の要点:

- chemical-only treatment 20/20生存（重要停止条件クリア）
- treatmentは評価可能な全条件でhigh-Q側へ一貫して偏る
- vent条件でvent滞在増加
- generalistはlight / chemical双方を行動へ統合
- Energy / Matter / 固定表現型 / 数値環境の整合性OK
- V1.6は「生存ボーナス」ではなく環境・表現型に応じた空間選択則として機能

現行参照値:

```text
memory_tau    = 10
response_gain = 64
```

ただし2026-09-01時点の `evosim/config.py` 通常defaultは `response_gain=16` のまま。
V1.7へ入る前にV1.6確定処理として64へ反映し、CI基準更新後 `v1.6-final` を保存する。
この処理はV1.7 / Exp11の変更軸へ混ぜない。

## Exp10 exploratoryで見えた小型化

進化OFF実装漏れ中の旧B1で:

```text
mean_body_size 約1.0 -> 約0.226
population     約300 -> 約6,500
```

を観測した。Matterは保存されており、同じ総Matterが多数の小型個体へ分割された。

これはExp10正式結論には使わないが、

- 現行世界に強い小型化選択圧がある可能性
- 個体数増大で計算コストが急増する

という次の設計課題を示すexploratory evidenceとして保持する。

## V1.7レビュー案

小型化を止めるためのbody_size下限変更やpopulation制御を直接入れない。

候補:

```text
BMR = C_core + (bmr_coef - C_core) * M^0.75
```

`C_core` は細胞生命に共通する縮小不能な基礎維持代謝として扱い、遺伝子にはしない。

重要な性質:

- `C_core=0` でV1.6完全一致
- `M=1` でBMR=0.3を維持
- 小型化しても基礎維持費が0へ消えない
- 大型側への過剰選択も起こり得るため上下境界を両方検証

**この案はまだ人間承認前。PR #50レビュー完了まで実装しない。**

## Exp11レビュー案

15 `C_core`:

```text
0.000, 0.005, 0.010, 0.015, 0.020,
0.025, 0.030, 0.040, 0.050, 0.060,
0.075, 0.100, 0.150, 0.200, 0.300
```

Phase Bはbody_sizeのみ進化ON、他13遺伝子固定。

```text
B1 light-only / lightspec   15 × seed1-8 = 120
B2 chem-only / chemspec     15 × seed1-4 = 60
B3 mixed / generalist       15 × seed1-4 = 60
合計                         240 run
```

全run 10,000 tick、`max_population_halt=10,000`、tau=10 / gain=64明示。
240 jobを1回のworkflow_dispatchで最初から登録し、途中の人間判断を要求しない。

選定は「平均サイズ1へ戻す」「population最小」ではなく、
**上下body_size境界への張り付きと重大な生態破綻を避ける最小C_core**。
詳細は `docs/Exp11_実験計画案.md`。

## LUCA-inspired参照方針

LUCAそのものを再現しない。

- 現実から構造・因果・スケーリング・比率を主に借りる
- 未校正のEnergy / Matter / tickへSI絶対値を直接移植しない
- LUCAらしさへ適応度を与えない
- 地球史どおりの進化結果を直接指定しない
- 現実的な初期・基礎ルールを置いた後の進化は自然選択へ任せる

## 行動の絶対原則

**未来Energy収益を予測させない。**

禁止:

```text
候補地点ごとの未来Energy獲得量を予測
→ 移動コストまで含め最適地点へ移動
```

維持する思想:

> 現在感じる刺激への局所的・反射的な応答。

V1.6一次Energy行動はtemporal biased random walkであり、`dQ`から方向を直接求めない。

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
14. 科学的STOP/REVIEWと実行失敗を区別する

## 実験結果保存

`docs/実験結果保存方針.md`を必ず読む。

正式実験は文字サマリーだけで終了しない。

GitHub:
- 結果考察
- 実測NOTES
- 集計プロット
- 代表GIF/PNG

全生データ・全画像はGoogle Drive / Actions artifactへ保存する。

## 世界バージョン境界

世界ルール変更前に直前バージョンを `vX.Y-final` として保存する。
詳細は `docs/バージョニング方針.md`。

V1.7は生理コストを変更するため世界ルール境界。
Exp11実装前にV1.6を確定して `v1.6-final` を保存する。

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
