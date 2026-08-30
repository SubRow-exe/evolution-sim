# Exp06 実験計画 — 化学利用経路の成立性診断

更新: 2026-08-30
状態: **事前登録 / 未実行**

関連:
- `docs/Exp05_結果考察.md`
- `docs/V1.1_総括.md`

## 1. 背景

Exp05では完全暗部30%に化学噴出口と無機栄養が存在したにもかかわらず、暗部は早期に無人化し、chemical利用型の持続的な系統は成立しなかった。

これは以下の重大な懸念を生む。

> 現行モデルでは複数のEnergy戦略を競争させているつもりでも、通常祖先から持続的に進化可能なEnergy獲得経路が実質的に光利用しかない可能性がある。

この場合、V1.1で観測された光利用型優勢を「競争の結果」と解釈することはできず、モデル設計上の到達可能性の非対称として扱う必要がある。

Exp06はこの点だけを診断する。光総量0.75/0.50等の次の環境比較はExp06後まで保留する。

## 2. 現行仕様から分かっていること

- 初期 `light_absorption = 0.3`
- 初期 `chemical_absorption = 0.3`
- 無機栄養はMatter源でありEnergy源ではない
- nutrient吸収にはEnergyコストが必要
- 持続的な外部Energy流入は光とchemical vent
- ventは局所的
- 初期 `sensory_range = 0.4`
- 感覚距離 = 25 × sensory_range = 約10 wu
- 環境セル = 20 wu

したがって初期個体は隣接セルのventを十分探索できない。

またchemical uptakeは

```text
chem_uptake * chemical_absorption * matter * phi
```

であり、初期値0.3ではvent上でも維持費を安定して上回れない可能性が高い。

さらにchemical ventの持続供給規模自体も光より小さい。`chem_capacity=50`, `chem_regen=0.05` のロジスティック回復では、1 vent cellの理論最大回復はstock=25時の0.625 E/tick。4 vent・radius=2で重複がなければ約52セル、理論上限は約32.5 E/tick程度であり、V1.1の総光供給1,248 E/tickより大幅に小さい。

このためExp06では「能力不足」「ventへの接触/発見」「化学生態自体の成立性」を分離する。

## 3. 実験の問い

1. 光が完全に0でも、現行祖先からchemical依存集団は自然に維持・進化できるか。
2. 現行祖先をvent上へ強制配置すれば維持・進化できるか。
3. chemical利用能力を十分持つ個体なら、現行chemical資源・生理式だけで持続可能か。
4. chemical利用能力が十分でも、ランダム配置ではventへ到達できないか。

## 4. 比較条件 — 2×2診断

全条件で:

```text
light_pattern = uniform
light_max = 0.0
世界サイズ・chemical資源・nutrient・生理・繁殖・突然変異 = 現行V1.2と同じ
initial_population = 100
```

health checkで毎tickの総light供給=0、累積light flow=0を確認する。

### A. Ancestor / Random

```text
初期ゲノム = 現行祖先
初期配置 = 通常ランダム
```

目的: 「光0の現行世界」で通常祖先が自然にchemical系へ移行できるか。

### B. Ancestor / Vent

```text
初期ゲノム = 現行祖先
初期配置 = 全個体をvent cell上へ配置
```

目的: ventを見つけられない問題を除去しても、初期chemical_absorption=0.3からbootstrapできるか。

### C. Chem-adapted / Vent — positive control

```text
初期ゲノム = 現行祖先を基本とする
chemical_absorption = 2.0 に変更し固定
初期配置 = 全個体をvent cell上へ配置
```

目的: 現行chemical資源量・生理ルールの下で、chemical利用生態そのものが成立可能か。

`2.0`は次期バージョンの初期値候補ではない。初期0.3より十分高く、chemical uptakeが維持費を明確に上回り得る「診断用の正の対照」としてのみ使う。他遺伝子は現行祖先値のまま。

### D. Chem-adapted / Random

```text
初期ゲノム = Cと同じ
chemical_absorption = 2.0 に固定
初期配置 = 通常ランダム
```

目的: chemical代謝能力が十分ある状態でも、ventへの空間アクセス・探索がボトルネックになるか。

## 5. 実装上の原則

Exp06の診断用初期条件は**通常の世界ルール/デフォルト初期値を変更しない**。

- mainの `INITIAL_GENOME` を2.0へ書き換えない
- 通常の初期配置をvent配置へ変更しない
- Exp06専用の実験初期化/runnerで注入する
- 初期条件はtick 0のbirth記録より前に適用し、events/snapshotに正しい初期ゲノム・位置を残す
- chemical=2.0への上書き自体は乱数を消費しない
- B/Cは同一seedなら同じvent配置になること
- A/Dは同一seedなら同じランダム配置になること
- vent配置では `world.chem_mask=True` のセルだけを使用し、セル内位置は決定的に `Simulation.rng` から生成する
- C/Dではchemical_absorptionを2.0へ上書き後、以後の世代でも2.0に固定する
- 通常Config・既存seedの科学結果不変をCIで確認する

診断支援コードはdefault通常実行を完全に不変に保つこと。恒久的な初期パラメータ変更はExp06結果後に別バージョン/別実験として判断する。

## 6. 実行条件

初回:

```text
seed: 1-10
ticks: 10,000
4条件 × 10 seed = 40 run
stats_interval = 20
snapshot_interval = 1000
GitHub Actions / 同一数値実行環境
```

10 seedにする理由:
- 今回は効果量推定より「成立/不成立・ボトルネックの位置」の診断が主目的
- all-darkでは個体数が低くなる可能性が高く、10k tickで長期維持を確認する

### 事前規定の追加seed

いずれかの条件で結果が混在し、10 seedで診断が曖昧な場合のみ、その条件をseed 11-20まで追加する。

追加判断は以下のようなケースに限定する:
- 生存と絶滅がseed間で混在
- chemical系への移行が一部seedだけで発生
- 10k時点で増加/減少傾向が判別不能

結果を見て都合よく条件値・chemical_absorption=2.0・tick数を変更しない。

## 7. 主評価項目

### 生存・繁殖
- extinction有無 / extinction tick
- population時系列
- births / deaths
- 10k時点population
- 5k→10kで集団が維持/増加/減少のどれか

### chemical利用
- flow_chemical
- chemical stock / influx
- vent_cell_frac
- mean chemical_absorption
- chemical_absorptionの分布
- ancestor条件で `chemical_absorption >= 0.5 / 1.0 / 1.5` に到達した系統の有無・時刻

### 空間
- vent占有セル
- 個体のvent滞在割合
- centroid / occupied cells
- GIF / chemical背景可視化

### 他経路
- light flow = 0であることをhealth check
- corpse / predationは補助的Energy移転として記録するが、持続的外部Energy源とは解釈しない

## 8. 判定ロジック

### ケース1: C (Chem-adapted/Vent) も絶滅

現行chemical資源量・供給速度・生理コストの組合せでは、chemical依存生態そのものが標準初期個体群から成立しにくい。

次に見直す候補:
- chem_capacity / chem_regen / vent面積・数
- chemical uptakeと維持費の収支
- initial_populationと局所carrying capacity

この場合、V1.1の光優勢を「複数Energy戦略間の競争結果」とは解釈しない。

### ケース2: Cは生存、B (Ancestor/Vent) は絶滅

chemical生態は成立可能だが、現行祖先のchemical_absorption=0.3から到達するまでに進化上の谷がある可能性が高い。

次に見直す候補:
- 初期chemical_absorption
- 変異幅 / standing variation
- chemical能力の収支曲線

### ケース3: Bは生存/進化、A (Ancestor/Random) は絶滅

代謝経路は祖先から到達可能だが、ventへの接触・探索が主要ボトルネック。

次に見直す候補:
- sensory_range
- vent密度 / 面積
- 移動・探索ルール

### ケース4: Cは生存、D (Chem-adapted/Random) は絶滅

完成したchemical能力があっても資源発見・占有が困難。空間アクセスの問題が強い。

### ケース5: Aでも持続的chemical集団が成立

chemical進化経路そのものは閉じていない。Exp05暗部無人化は、光のある領域との競争、人口動態、vent配置、局所carrying capacity等を再検討する。

## 9. Exp06後の判断

Exp06が終わるまで、光総量0.75 / 0.50実験は保留する。

結果を受けて次の実験で初めて、必要なら以下を1軸ずつ見直す。

- 初期chemical_absorption等の初期ゲノム
- chemical資源量/回復速度/vent配置
- sensory_range / 探索能力
- 変異幅

複数項目を同時に調整しない。

## 10. 過去実験の扱い

Exp03〜05の観測結果そのものは保持する。

ただしExp06完了まで、以下の強い解釈は保留する:

> 「複数のエネルギー利用戦略が十分に進化可能な世界で、光利用型が競争に勝った」

もしchemical経路が設計上実質的に閉じていたと判明した場合、V1.1総括の光利用優勢に関する解釈を修正し、モデル設計上の制約として明記する。
