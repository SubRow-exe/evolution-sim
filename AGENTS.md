# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/V1.9_現状ステータス.md` — **現在地・確定事項・残設計課題の正本**
2. `docs/次の実験計画.md` — **現在の司令塔**
3. `docs/V1.9_iLUCA再設計仕様.md` — **V1.9世界ルール設計の詳細draft**
4. `docs/V1.8_総括.md` — **V1.8 close / 方針転換の正本**
5. `docs/環境因子追加・校正方針.md` — **プロジェクト全体の恒久設計原則**
6. `docs/バージョニング方針.md`
7. `docs/メインストリーム開発ストーリー.md`
8. `docs/Exp14_表現型プロベナンス訂正.md` — 履歴
9. `docs/V1.8_現状総括_Exp14結果.md` — 履歴
10. `docs/実験結果保存方針.md`
11. `docs/数値再現性・Actions実行環境方針.md`

過去の実験計画より、現在の人間判断・総括・ステータス正本を優先する。

---

# 2. 現在地

```text
V1.7                         CLOSED / bmr_core=.15
V1.8 mechanisms              COMPLETE
Exp13                        COMPLETE / scientific STOP
Exp14                        COMPLETE / phenotype provenance corrected
original Exp15               SUPERSEDED / DO NOT DISPATCH
V1.8 scientific phase        CLOSED
V1.9 design                  IN PROGRESS / major human decisions pending
V1.9 implementation          NOT STARTED
next formal experiment       NOT DESIGNED
```

**現在AIが勝手に行ってはいけないこと:**

- old Exp15 harnessの実装継続
- Exp15 preflight / formal dispatch
- V1.9 world-ruleコード実装
- parameter sweep / formal experiment設計

`docs/V1.9_現状ステータス.md` の主要設計課題P1〜P5が整理され、V1.9仕様がFINALになるまでworld-rule実装は開始しない。

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

現時点で確定している主要方向:

```text
INITIAL light_absorption = 0
INITIAL predation_efficiency = 0
operational Energy + reserve の2-pool化
内部Energy状態依存homeostasis
reserve_capacity gene
reproduction_threshold gene
starvation_sensitivity gene
chemical Energy stock -> H2-like substrate -> usable Energy
H2 explicit / CO2 implicit
zero-start能力が将来立ち上がれるmutation設計を再検討
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

V1.9で新たに進化可能にする方向:

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

# 9. V1.9設計の残課題

実装前に人間判断が必要な主要課題は `docs/V1.9_現状ステータス.md` のP1〜P5。

```text
P1 Operational Energy + Reserve 詳細仕様
P2 starvation response適用範囲
P3 reproduction strategy詳細
P4 H2 environment / initial spawn詳細
P5 zero能力から新能力を出現させるmutation設計
```

低優先候補:

```text
corpse / Matter recycling
initial corpse_digestion
```

CO2については **V1.9では H2 explicit / CO2 implicit** で確定済み。

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
1. Opus 5等でV1.9現状ステータスをレビュー
2. P1〜P5のhuman decisions確定
3. `docs/V1.9_iLUCA再設計仕様.md`をFINAL化
4. V1.8最終refを固定
5. 実装
6. unit/integration/conservation/determinism tests
7. fixed iLUCA scientific sanity
8. evolution-ON sanity
9. その後に初めてexperiment設計
```

formal experimentは人間の明示判断なしに開始しない。
