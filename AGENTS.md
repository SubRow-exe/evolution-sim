# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と正本を必ず読むこと。

## 現在の参照順

1. `docs/次の実験計画.md` — 現在の司令塔
2. `docs/V1.4_総括.md` — V1.4最終判断・default
3. `docs/V1.5_Exp09_レビュー判断.md` — Claudeレビューへの人間の採否判断。レビュー原文より優先
4. `docs/V1.5_異種刺激比較仕様.md` — V1.5実装の正本
5. `docs/Exp09_実験計画.md` — Exp09条件の正本
6. `docs/Exp08_結果考察.md` — V1.4校正の実測
7. `experiments/exp08_actions_20260831_052756/NOTES.md`
8. `docs/実験結果保存方針.md`
9. `docs/バージョニング方針.md`
10. `docs/V1.4_一次エネルギー吸収仕様.md`
11. `docs/V1.3_化学資源モデル仕様.md`

Claude Codeレビュー原文に提案があっても、`docs/V1.5_Exp09_レビュー判断.md`で不採用とした案を独自に採用しない。
古い「V1.4 default未決定」「Exp08未実行」の記述より上記正本を優先する。

## 現在地

Exp08完了。V1.4の一次Energy/資源吸収則は妥当性確認を通過。

恒久defaultは人間判断で確定済み:

```text
light_uptake_coef = 2.0
chem_vent_flux = 16.0
chem_uptake = 0.5
```

`light_uptake_coef`は個体の光利用能力を1 tickあたりの実吸収上限へ変換する世界側係数。

`chem_vent_flux`はchemical噴出口1つが1 tickに供給するEnergy量。

## 小型化の判断

V1.4では環境直接吸収利益が`matter^(2/3)`、維持費の多くは身体量に強く依存する。

その結果、小型個体が単位身体量あたりの交換効率で有利になることは現時点では**仕様上の自然な選択圧として許容する**。

小型化を抑えるためだけの人工的ペナルティは入れない。

将来、温度・熱損失・備蓄・防御・捕食等から大型化の利点が自然に生じる余地を残す。

## V1.5実装前に必ず行うこと

1. `evosim/config.py`へV1.4恒久defaultを反映
   - `light_uptake_coef = 2.0`
   - `chem_vent_flux = 16.0`
   - `chem_uptake = 0.5`
2. 暫定defaultコメント・文書を更新
3. 全test / Energy / Matter / RNG / CI確認
4. 必要なCI基準更新を行う
5. **上記default反映済み状態を`v1.4-final` branchへ保存**
6. その後にV1.5を実装

Claudeレビューの「Exp08実行時mainをそのままv1.4-finalとし、default変更をV1.5側へ送る」案は採用しない。
V1.4を保存する前にV1.5行動則を混ぜない。

## V1.5の目的

現行行動は光とchemicalを

```text
ability × raw field value
```

で比較するが、光はflow、chemicalはstockで単位・範囲が違う。

V1.5では異種一次Energy刺激を無次元受容器応答へ変換する。

```text
response(x,K) = x / (x + K)
```

確定default:

```text
light_stimulus_half = 1.2
chemical_stimulus_half = 12.3
```

`chemical_stimulus_half=12.3`は典型的な完全13セルventの**生物不在平衡stockを基準にした固定値**。Exp08の占有vent stockへ合わせて引き下げない。生物がchemicalを利用するとstockと知覚刺激が低下し、離脱すれば回復する負のフィードバックは、stock型資源の自然な性質として残す。

score:

```text
light_score
= light_absorption × response(light, 1.2)

chemical_score
= chemical_absorption × response(chemical_stock, 12.3)
```

## V1.5実装スコープ

変更対象は**light vs chemicalという一次Energy源同士の比較**。

- light候補を独立抽出
- chemical候補を独立抽出
- 両方あるときだけ無次元response scoreで比較
- 片方だけなら従来のsource内選択を維持
- nutrient / corpse / predationの全面無次元化は今回しない
- V1.4の吸収則は変更しない

単独sourceでは「順位が同じ」だけでなく、同一Config・同一seedで`v1.4-final`と**決定的に完全一致**することを停止条件にする。

### tie

同score時にfield走査順だけで常にlightまたはchemicalが勝つ隠れbiasを作らない。

`stimulus_tie_eps`は`1e-9`程度の十分小さい値、または同等に厳しい相対許容差を用いる。
両score=0ならEnergy源による方向付けを行わず、V1.4と同じ挙動へ戻す。

未来予測や新しい固定source優先順位も導入しない。

詳細は`docs/V1.5_異種刺激比較仕様.md`と`docs/V1.5_Exp09_レビュー判断.md`を正本とする。

## 行動の絶対原則

**未来Energy収益を予測させない。**

禁止:

```text
候補セルごとの将来Energy獲得量を計算
→ 移動コスト等まで含め最適地点へ移動
```

維持する思想:

> 現在感じる刺激への反射的走光性・走化性。

V1.5の無次元化は「賢くする」ためではなく、異なる単位の刺激を感覚として比較可能にするため。

## Exp09

Exp09はV1.5比較則の診断。

進化競争はまだ評価しない。

### Phase 0

- response算術
- half-response
- 単調性
- source-only完全一致（`v1.4-final`基準）
- 等価刺激
- 表現型・光量ごとの**light/chemical選択交差点stockの事前計算**
- 能力差による切替
- 各診断表現型でlight選択・chemical選択の両側を検証
- tie biasなし
- 未来予測なし
- RNG / Energy / Matter健全性

### Phase A

synthetic arenaで:

- light-only
- chemical-only
- 等価刺激
- light specialist
- chemical specialist
- generalist

を直接検証。

各表現型について、刺激条件を交差点の両側へ置き、**lightを選ぶケースとchemicalを選ぶケースの双方**を確認する。

### Phase B

標準混合世界の短時間sanity check。

```text
Light-only control
Chemical-only control
Mixed / light specialist
Mixed / chemical specialist
Mixed / generalist
```

Pilot: 各条件seed1、500〜1,000 tick。

本番候補: 5条件 × seed1-5 × 5,000 tick = 25 run。

評価は行動選択回数、Energy flow、vent滞在、明暗帯滞在等。
単純な「vent滞在率が高い」を合格条件にせず、**選択時stockが理論交差点の上/下にあるかと実際のsource選択が一致すること**を優先する。

追加観測:
- 選択時のlight / chemical response score
- 選択時chemical stock
- 交差点予測との一致率
- Energy候補がcorpse / predation等に負けた回数（source別）

観測はRNG非消費・分岐不変とする。

Exp09から光/chemicalの進化的優劣を結論しない。

## 実験結果保存

`docs/実験結果保存方針.md`を必ず読む。

正式実験の結果確定時は文字サマリーだけで終了しない。

GitHubへ:
- 結果考察
- 実測NOTES
- 集計プロット
- 代表GIF/PNG

全生データ・全画像はGoogle Drive / Actions artifactへ保存する。

## 世界バージョン境界

V1.5の行動比較則は結果を変えるため世界ルール変更。

V1.5最初の意図的結果変更commitを新しいCI基準refへ設定する。

V1.4再現用に、恒久default反映済みの`v1.4-final`を必ず先に保存する。

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

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
