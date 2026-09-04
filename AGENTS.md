# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/次の実験計画.md` — **現在の司令塔**
2. `docs/V1.9_iLUCA再設計仕様.md` — **V1.9世界ルール設計の正本**
3. `docs/V1.8_総括.md` — **V1.8 close / 方針転換の正本**
4. `docs/環境因子追加・校正方針.md` — **プロジェクト全体の恒久設計原則**
5. `docs/バージョニング方針.md`
6. `docs/メインストリーム開発ストーリー.md`
7. `docs/Exp14_表現型プロベナンス訂正.md` — 履歴
8. `docs/V1.8_現状総括_Exp14結果.md` — 履歴
9. `docs/実験結果保存方針.md`
10. `docs/数値再現性・Actions実行環境方針.md`

過去の実験計画より、現在の人間判断・総括・司令塔を優先する。

---

# 2. 現在地

```text
V1.7                         CLOSED / bmr_core=.15
V1.8 mechanisms               COMPLETE
Exp13                         COMPLETE / scientific STOP
Exp14                         COMPLETE / phenotype provenance corrected
original Exp15                SUPERSEDED / DO NOT DISPATCH
V1.8 scientific phase         CLOSED
V1.9 design                   DRAFT / human decisions pending
V1.9 implementation           NOT STARTED
next formal experiment        NOT DESIGNED
```

**現在AIが勝手に行ってはいけないこと:**

- old Exp15 harnessの実装継続
- Exp15 preflight / formal dispatch
- V1.9 world-ruleコード実装
- parameter sweep / formal experiment設計

V1.9の3 human decisionsが確定し、仕様がFINALになるまでworld-rule実装は開始しない。

---

# 3. V1.8 close

V1.8ではday/nightと一次Energy density responseを実装したが、light-dependent phenotypeの崩壊を追う中で祖先モデル側の構造的欠落が判明した。

主な欠落:

```text
内部Energy状態依存の恒常性      なし
reserve容量                    world constant
繁殖Energy threshold            world constant
祖先light_absorption            >0
祖先predation                   >0
chemical                        Energy stockそのもの
```

そのため、夜を短くする・lightを増やす・energy_capacityを増やす等で生存を作る方向は採用しない。

V1.8のworking parameter未選定は未完了ではなく、人間判断による科学的打切り。
詳細: `docs/V1.8_総括.md`。

---

# 4. Exp14 provenance

Exp14は計画上light specialist `light_absorption=2.0`を意図したが、generator override欠落で実際の116 formal runは`INITIAL_GENOME.light_absorption=.3`だった。

維持する実測:

```text
116/116 final extinction
all deaths starvation
Generation 2 = 0
```

ただしV1.7/Exp13 light specialistとの定量比較や恒久parameter選定に使わない。

---

# 5. V1.9の目的

V1.9 = **より妥当なchemical-first iLUCA baselineの再構築**。

同時に、元ロードマップの「chemical-first祖先からphototrophy創発」を可能にする。

予定する主要変更:

```text
INITIAL light_absorption = 0
INITIAL predation_efficiency = 0
operational Energy + reserve の2-pool
内部Energy状態依存homeostasis
reserve_capacity gene
reproduction_threshold gene
chemical Energy stock -> H2-like substrate -> usable Energy
zero-start能力のgeneric additive mutation改善
```

V1.8 day/nightは残す。初期iLUCAにはlight routeがないため直接影響せず、phototrophy出現後に意味のある周期圧になることを狙う。

---

# 6. V1.9 homeostasis HARD RULE

未来情報を使わない。

```text
NG: 日没が近いから活動を止める
NG: 将来のEnergy収益を予測して貯蔵する
OK: 現在のoperational Energyが低いため活動を落とす
OK: 現在のEnergy不足をreserveから補う
```

starvation responseは現在の内部状態だけで決める。

`bmr_core`は不可避maintenance floorとして残し、無敵の休眠を作らない。

---

# 7. V1.9進化可能性

環境が要求する適応をworld constantだけに置かない。

V1.9で新たに進化可能にする候補:

```text
starvation_sensitivity
reserve_capacity
reproduction_threshold
```

fixed ancestor試験とevolution-ON試験を分離する。

固定祖先の絶滅だけを環境FAILとみなさない。evolution ONで適応できるなら正しい選択圧であり得る。

---

# 8. 校正原則

`docs/環境因子追加・校正方針.md`を恒久方針とする。

優先順位:

```text
自然に妥当な環境・基礎生理
> 長期進化
> 複数戦略の余地
> robustな成立域
> 精密parameter optimum
```

環境parameterを生存側へ調整する前に、その環境への応答が生物側で実現/進化可能か確認する。

---

# 9. V1.9設計の未決3点

実装前に人間判断が必要:

```text
Q1 CO2をexplicit fieldにするか
   推奨: V1.9ではH2 explicit + CO2 implicit

Q2 chemical-first initial populationをどこへ置くか
   推奨: vent/source habitat近傍

Q3 INITIAL corpse_digestionを0にするか
   推奨: 0
```

詳細: `docs/V1.9_iLUCA再設計仕様.md` §25。

---

# 10. 絶対設計原則

- 適応度関数を直接置かない
- 特定生態型への固定bonus/penaltyを置かない
- 将来を予測するAI的行動を入れない
- 保存則を破らない
- 観測/Recorderをsimulationへフィードバックしない
- 同seed決定性を守る
- zero-start形質へ個別special-case mutation bonusを入れない
- 歴史的experimentを現在仕様へ書き換えない
- 過去worldの再現はversion ref/tagから行う

---

# 11. V1.9実装前手順

```text
1. 3 human decisions確定
2. `docs/V1.9_iLUCA再設計仕様.md`をFINAL化
3. V1.8最終refを固定
4. 実装
5. unit/integration/conservation/determinism tests
6. fixed iLUCA scientific sanity
7. evolution-ON sanity
8. その後に初めてexperiment設計
```

formal experimentは人間の明示判断なしに開始しない。
