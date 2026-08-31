# AI協働開発ガイドライン（AGENTS.md）

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を読むこと。

## 現在の参照順

1. `docs/次の実験計画.md` — 現在の司令塔
2. `docs/V1.6_行動則仕様.md` — V1.6実装の正本
3. `docs/Exp10_実験計画.md` — Exp10条件・停止条件の正本
4. `docs/Exp09_結果考察.md` — V1.5/Exp09の実測と解釈限界
5. `experiments/exp09_actions_20260831_085922/NOTES.md`
6. `docs/V1.6_Exp10_レビュー.md` — レビュー原文。採用内容は2・3を優先
7. `docs/V1.5_異種刺激比較仕様.md`
8. `docs/V1.4_総括.md`
9. `docs/実験結果保存方針.md`
10. `docs/バージョニング方針.md`

古い「Exp09未実行」「V1.5実装前」「次は直ちに長期混合進化」という記述より上記正本を優先する。

## 現在地

V1.5 / Exp09は完了済み。

- 本番: 5条件 × seed 1-5 × 5,000 tick = 25 run
- 実行commit: `c73b039`
- Actions run: `33375257275`
- score順位と実選択: 24,470,222 / 24,470,222一致
- 診断条件415項目Green
- Phase 0 31項目Green
- 単独source 4ケースが`v1.4-final`と完全一致

ただし追加監査で、感覚半径がセルサイズを下回り、V1.5個体が実質的に固着していると判明した。
Exp09が検証したのは異種刺激比較の算術であり、空間行動そのものではない。

## 次の作業

状態整理PRをreview / mergeした後、V1.6を実装しExp10を実行する。

```text
状態整理PR
→ v1.5-final確認
→ V1.6実装
→ Phase 0
→ Exp10 Phase A
→ 事前規則で1候補選定
→ Phase B 200 run
→ Green時のみPhase C
```

## V1.6の境界

V1.6は以下を不可分の1変更として扱う。

1. light / chemicalの**知覚だけ**を双線形補間で連続化
2. 現在刺激の時間変化でrandom walkのturn幅を変調

吸収・供給・損失などの物理はV1.5から変えない。

### 統合評価

```text
R_light = light / (light + light_stimulus_half)
R_chem  = chemical / (chemical + chemical_stimulus_half)

Q = (aL * R_light + aC * R_chem) / (aL + aC)
```

無効能力は分母・分子から除外し、両方無効なら`Q=0`。

### 短期記憶と移動

```text
delta_q = Q_now - Q_memory
alpha = 1 - exp(-1 / memory_tau)
Q_memory <- Q_memory + alpha * (Q_now - Q_memory)

turn_factor = 2 / (1 + exp(response_gain * delta_q))
sigma_eff = wander_turn_sigma * turn_factor
heading += Normal(0, sigma_eff)
```

- `delta_q=0`でbaseline random walk
- 改善中は直進しやすく、悪化中は曲がりやすい
- `response_gain=0`でbaseline軌跡と完全一致
- 速度は刺激で変更しない
- 一次EnergyのWTA target探索と`stay=True`を廃止
- 満腹時停止は維持
- nutrient / corpse / predationは今回変更しない

## Exp10

Exp10は進化実験ではなく行動則の診断・校正。

- Phase 0: 補間・Q・memory・turn・決定論・保存則
- Phase A: synthetic arenaで12候補 + gain 0 control
- Phase B: 5条件 × 2行動則 × 20 seed × 10,000 tick = 200 run
- Phase C: A/B Green時だけ同じ候補を延長

Green規則・候補値・停止条件は`docs/Exp10_実験計画.md`を変更せず使用する。
結果を見てパラメータ候補を追加しない。

## V1.6実装前に必ず行うこと

1. Exp09結果考察・NOTES・図がmainにあることを確認
2. `v1.5-final`がExp09実行commit `c73b039`を指すことを確認
3. V1.5再現手段を残す
4. V1.6最初の確定実装commitを新しいCI基準refへ設定

V1.6は移動原理を変えるためV1.5とのbit一致は要求しない。
ただし吸収物理、Matter / Energy保存、V1.6内部決定論は必須。

## 絶対に守る設計原則

1. 適応度を直接計算しない
2. 種クラスを作らない
3. 寿命値を直接作らない
4. コストは物理・生理則から導く
5. Matter保存とEnergy台帳を守る
6. 乱数は`Simulation.rng`だけを使い、決定性を壊さない
7. 想定外の戦略を許容する
8. 特定生態型へ直接ボーナスを与えない
9. 環境・世界ルールは原則1軸ずつ変更する
10. 遺伝子の存在と進化経路の成立を区別する
11. 比較するEnergy戦略は単独成立性を先に確認する
12. 行動に暗黙の知能・未来予測を導入しない

## 結果不変変更と世界変更

- V1.6は意図的な世界ルール変更
- 観測・図・解析追加は結果不変変更
- 観測追加はRNGを消費せず、生物・環境状態や分岐へフィードバックしない
- 世界境界では理由を記録し、CI基準refを明示的に更新する

## 実験結果の保存

正式実験は`docs/実験結果保存方針.md`に従う。

GitHubへ最低限保存:

- 結果考察
- 実測NOTES
- 集計プロット
- 代表GIF/PNG

全生データ・全画像はGoogle Drive / Actions artifactへ保存する。
文字サマリーだけで終了しない。

## 開発フロー

- 原則ブランチを切りPRで提出
- コード変更後は`uv run pytest tests`を全通し
- 結果不変変更では結果不変性も確認
- V1.6はPhase 0 Green前にExp10 Phase Aへ進まない
- Exp10の事前登録条件を生物学的結果に応じて事後変更しない

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
