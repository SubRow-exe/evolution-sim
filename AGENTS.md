# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数のAIアシスタントと人間が共同開発する。コードを変更する前に、本書と現在の司令塔ドキュメントを必ず読むこと。

## 現在の作業方針の参照順

1. `docs/次の実験計画.md` — 現在地と直近順序
2. **`docs/Exp07_結果考察.md` — Exp07結果と新たに検出した設計課題**
3. **`docs/V1.4_一次エネルギー吸収仕様.md` — V1.4実装の正本**
4. **`docs/Exp08_実験計画.md` — V1.4校正実験の正本**
5. `docs/V1.3_化学資源モデル仕様.md`
6. `docs/Exp07_実験計画.md`
7. `docs/V1.1_総括.md`
8. `docs/バージョニング方針.md`

古い「次は光総量0.75/0.50」「V1.3のまま光+chemicalを直接競争」「chem_regenを増やす」案より上記を優先する。

## 現在の短期順序

```text
V1.1-1.2保存/実験済み
→ Exp06: 旧chemicalではpositive controlまで全滅
→ V1.3: 地質source + 局所stock + 環境損失へ修正
→ Exp07 240 run × 120k 完了
   - C: flux8以上で10/10成立
   - B: 全80/80絶滅
   - D: flux8以上で10/10到達
→ Exp07後監査で光吸収上限欠落を設計ミスとして確認
→ Exp07結果/考察を正本化
→ V1.3最終状態を v1.3-final 保存       ← 次
→ V1.4 一次Energy吸収則実装
→ unit / Energy / Matter保存テスト
→ Exp08 Phase0ベンチ
→ Exp08 PhaseA/B 90 run × 60k
→ light/chemicalのdefault校正
→ 原生生物的な異種刺激比較則を確定
→ 光+chemical同居診断
```

## Exp07で確定したこと

全条件light=0。

### C — chemical_absorption=2.0固定 / vent

- `chem_vent_flux=8`以上で10/10が120,000 tick維持
- flux4は9/10絶滅、唯一の生存も最終5個体

したがってV1.3 chemical sourceモデルは完成chemical型の持続生態を成立させられる。

### B — 通常祖先 / vent

- 全8 flux × 10 seed = 80/80絶滅
- 多くは約150 tick
- `chemical_absorption>=0.5`へ到達したrunなし

source不足ではなく、通常祖先からchemical利用型への進化bootstrapが成立していない。

### D — chemical_absorption=2.0固定 / random

- flux8以上で10/10が120k到達
- 多くのrunで最終個体の90%以上がvent cell

完成chemical型はrandom配置から少なくとも一部ventへ到達・定着可能。
ただし4 ventsすべてを必ず占有するわけではなく、vent間探索は弱い可能性がある。

## V1.1-Exp05の解釈

保持:
- 高光利用化・小型化が実際に観測された
- lineage sweepは多因子
- mutation_rate等のExp04結果
- 光利用経路内部での比較

撤回/保留:

> 複数の一次Energy戦略が対等に成立可能な世界で、光利用型が競争に勝った。

Exp06でchemical環境側の不整合、Exp07後監査で光吸収側の不整合が見つかったため支持されない。

## V1.4で直す根本問題

### 1. 光の個体吸収上限

旧光は:

```text
weight = light_absorption × matter × health
```

をセル光量の分配比率にしか使わない。

1匹なら低 `light_absorption` でもセル光をほぼ全取得する。

V1.4では:

```text
light_demand
= light_uptake_coef
× light_absorption
× effective_surface
× health
```

を個体の最大要求量にする。

`light_uptake_coef`は「光吸収速度係数」。恒久defaultはExp08で校正する。

### 2. 有効表面積

```text
effective_surface = matter^(2/3)
```

を導入する。

意味:
- matterを概ね体積とみなす
- 同形状なら体積8倍で表面積4倍
- 環境との直接交換は体積そのものではなく接触面で律速

将来形状遺伝子を入れたら差し替える暫定近似。

### 3. chemical

V1.3環境source式は維持。

生物側のみ:

```text
chemical_demand
= chem_uptake
× chemical_absorption
× effective_surface
× health
```

へ変更する。

stock不足時はセル内全個体の需要比で同時配分し、リスト順biasを廃止する。

### 4. nutrient

無機栄養も環境からの直接吸収なので `effective_surface` を使う。
Matter同化コスト/保存則は維持。

### 5. tick内処理

個体ごとの「移動→吸収」を逐次行わず、少なくとも:

```text
全個体が行動/移動
→ post-move hash再構築
→ light/chemical/nutrientの全需要を計算
→ セル内需要比例配分
```

とする。

光とchemicalで参照する位置時点を統一する。

## 行動ルールの原則

**未来のEnergy収益を予測させない。**

禁止:

```text
各セルで次tick得られるEnergyを計算
→ 最も儲かる場所へ移動
```

これは原始生物として高度すぎる。

維持する思想:

> 現在感じる刺激への反射的な走光性/走化性。

ただし現行は光供給値とchemical stockをraw値で直接比較しており単位が異なる。
これはExp08では各source単独なので主判定を妨げないが、**最初の光+chemical同居実験前に必ず修正**する。

半飽和型受容器等の無次元刺激化が候補だが、勝手に係数を追加・確定しない。

## V1.4で変更しないもの

- mutation
- reproduction
- basic metabolic cost / organ_upkeep
- movement/sensoryの基本構造
- `chem_uptake=0.5`
- chemical source/stock/loss式
- vent数/半径
- corpse/predation
- 日照時間変動

吸収利益側と維持費を同時に変更しない。

## chemical絶対量

V1.3 `chem_vent_flux=8`でも完成型は成立。

恒久default候補:

```text
16-24 E/tick/vent
```

理由:
- 世界総量はV1.1光より十分小さい
- 典型13セルventで約1.23-1.85 E/tick/cell
- V1.1光0.4-1.2 E/tick/cellに対し局所高密度を作れる

ただしExp08まで確定しない。

## Exp08

### Phase 0 — 決定論ベンチ

- matter 0.5/0.8/1/2/4/8
- absorption 0.3/1/2/5
- light_uptake_coef 1.0/1.5/2.0
- 1/5/20/100個体の密度競争
- list順を変えて配分不変

### Phase A — 光単独

```text
vertical light
chemical=0
light_uptake_coef = 1.0 / 1.5 / 2.0
```

- L0: ancestor light_abs≈0.3固定
- L2: light_abs=2.0固定

60 run × 60k。

### Phase B — chemical単独

```text
light=0
chem_abs=2.0固定 / vent
chem_vent_flux = 8 / 16 / 24
```

30 run × 60k。

合計90 run + Phase0。

Exp08では光/chemical競争、祖先chemical bootstrap、動物的進化について結論しない。

## バージョニング

- V1.3: chemical環境sourceメカニズム修正
- V1.4: 生物の一次Energy/資源直接吸収メカニズム修正

V1.4実装前に `v1.3-final` branchを保存する。

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
10. 「遺伝子がある」ことと「進化経路が成立可能」を区別する
11. 比較するEnergy戦略はまず単独で持続可能か確認する
12. 行動に暗黙の知能・未来予測を勝手に導入しない

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
