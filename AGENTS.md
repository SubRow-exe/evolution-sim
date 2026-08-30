# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数のAIアシスタントと人間が共同開発する。コードを変更する前に、本書と現在の司令塔ドキュメントを必ず読むこと。

## 現在の作業方針の参照順

1. `docs/次の実験計画.md` — 現在地と直近順序
2. **`docs/V1.3_化学資源モデル仕様.md` — V1.3実装の正本**
3. **`docs/Exp07_実験計画.md` — Exp07条件・判定の正本**
4. `experiments/exp06_actions_20260830_104921/NOTES.md` — Exp06実測結果
5. `docs/Exp06_実験計画.md`
6. `docs/Exp05_結果考察.md`
7. `docs/V1.1_総括.md`
8. `docs/バージョニング方針.md`
9. `docs/V1.2_V1.2.1_詳細実装仕様.md`

古い「次はlight total_scaleを0.75/0.50へ振る」「現行chem_regenを増やす」案より上記正本を優先する。

## 現在の短期順序

```text
V1.1保存済み
→ V1.2 / V1.2.1 / V1.2.2 実装済み
→ Exp05完了
→ Exp06完了: 4条件すべて0/10生存
→ chemical source式のモデル不整合を確認
→ PR #36でExp06結果とV1.3/Exp07方針を確定
→ V1.2最終状態を v1.2-final (branch + tag) として保存
→ V1.3 chemical sourceモデル実装  ← 次
→ unit / Energy conservation tests
→ Exp07 Pilot 9 run
→ Exp07 240 run × 60k
→ chemical成立/到達/探索の順に判定
→ 成立後に光+chemical同居実験
```

## Exp06で確定した解釈

Exp06は全条件light=0で、以下を各10 seed実行した。

```text
A Ancestor / Random
B Ancestor / Vent
C Chem2.0 / Vent
D Chem2.0 / Random
```

全条件0/10生存。positive controlのCも全滅した。

したがって、以下は支持されない:

> 「複数の一次Energy戦略が十分に成立可能な世界で、光利用型が競争に勝った」

Exp03-05の観測事実・sweep・同じ光利用経路内での比較は保持するが、光利用優勢の原因をEnergy戦略間競争の勝利とは解釈しない。

## V1.3 chemicalモデルの定義

chemicalは、海底熱水噴出孔・冷湧水等から供給される還元性物質が持つ利用可能化学自由Energyの粗視化量。

旧式:

```text
regen = r * stock * (1-stock/K)
```

は自己増殖資源型であり廃止する。

新構造:

```text
地質source S（一定・生物消費と独立）
        ↓
局所chemical stock C
   ↓              ↓
生物吸収 U     環境損失 L
               混合/流出/希釈/酸化等
```

1 tickの環境更新:

```text
L = chem_loss_frac * C
C1 = C - L
C2 = C1 + chem_source_flux
```

その後、生物がC2から吸収する。

stockに上限 (capacity) は置かない。source全量が流入し、一次損失だけで
有限化する。生物不在の平衡は `S / chem_loss_frac`。
capacityでクリップすると欠けvent/重複セルで実効sourceがseed依存に
最大10.8%失われるため廃止した。

sourceはstock=0でも毎tick一定量供給される。生物は局所stockを低下させられるが地質source自体を枯渇させられない。

## V1.3 Config

```text
chem_vent_flux = 8.0      # 暫定default。旧モデル最大供給規模≈32.5 E/tickに近い世界総32を基準化
chem_loss_frac = 0.10
chem_uptake = 0.5
n_vents = 4
vent_radius_cells = 2
```

旧 `chem_regen` / `chem_min_stock` / `chem_capacity` はConfigから削除する。

`chem_vent_flux`は1 ventの総source。各ventの円盤セル数に関係なく、そのventの総sourceは常に設定値とする。

`chem_source_flux[ix,iy]` fieldを作り、vent端/重複でも:

```text
sum(chem_source_flux) == n_vents * chem_vent_flux
```

を保証する。

初期stock (更新式の不動点):

```text
chem_source_flux / chem_loss_frac
```

旧`chem_regen`/`chem_min_stock`は通常V1.3経路で使わない。

## Energy台帳

chemical external sourceは`energy_in_cum`。

`chem_loss_frac * stock` は`energy_out_cum`。
capacity clippingを廃止したのでoverflow項は無い。

保存則を必ずテストする。

## Exp07

全条件light=0。目的は光との競争ではなく、V1.3 chemical source単独の成立性。

振る世界パラメータは`chem_vent_flux`のみ:

```text
4, 8, 12, 16, 24, 32, 48, 64 E/tick/vent
```

各fluxで:

```text
C chem2.0固定 / vent
B ancestor / vent
D chem2.0固定 / random
```

```text
8 flux × 3条件 × 10 seed = 240 run
120,000 tick
```

Pilotはflux 4/16/64 × C/B/D × seed1 = 9 run / 5k。

### 判定順

1. Cでchemical生態のecological viability境界
2. C成立域でBを見て祖先からの進化bootstrap
3. C成立域でDを見てvent探索/空間access

Bは生存/絶滅の二値で読まない。祖先の収支上、chemical吸収だけで黒字化するには
`chemical_absorption ≈ 0.9` (実効1.0前後) が必要で、初期値0.3の約3倍である。
`>= 0.5 / 0.9 / 1.2 / 1.5 / 2.0` の到達seed数と初回tickを見る。

高fluxで`max_population_halt`へ達した場合はscientific resultとして記録する。

## V1.3/Exp07で変更しないもの

- lightモデル
- chemical_absorption初期値/意味
- chem_uptake
- initial_population
- sensory/movement
- 生理/繁殖/mutation
- vent数/半径
- nutrient
- corpse/predation

## 当面残す懸念

1. chemical diffusion/advection/plume未実装
2. chemical uptakeの逐次処理順bias
3. chem_loss_frac=0.10の実時間校正なし
4. vent上100個体の局所過密
5. tickの現実時間未定義

Exp07はlineage sweepや最終最適形質の強い結論には使わない。

## バージョニング

- `V1.1 → V1.2 → V1.3`: 世界ルール変更
- `V1.2 → V1.2.1 → V1.2.2`: 観測・解析・実行基盤等の結果不変変更

V1.3はchemicalを人工的にbuffするためではなく、Exp06で見つかった**地質sourceとしてのモデル定義不整合を修正**する世界ルール変更。

## プロジェクトの絶対原則

1. 適応度を直接計算しない
2. 種クラスを作らない
3. 寿命値を直接作らない
4. コストは具体的な物理・生理則から導く
5. Matter保存・Energy台帳を守る
6. 乱数系列と決定性を守る
7. 想定外の戦略を許容する
8. 特定生態型に直接ボーナスを与えない
9. 原則1軸ずつ変更する
10. 「遺伝子がある」ことと「その進化経路が成立可能」を区別する
11. 比較するEnergy戦略は、まず単独で持続可能か確認する

## 開発フロー

- V1.3実装前に`v1.2-final`を保存
- 原則branch + PR
- `uv run pytest tests`
- Energy conservation test
- source fieldのseed/edge/overlap test
- Pilotで実装健全性のみ確認
- 生物学的結果を見てExp07の事前登録条件を変更しない
- 意味のある結果は`experiments/`とdocsへ保存

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
