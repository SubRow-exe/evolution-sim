# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と正本を必ず読むこと。

## 現在の参照順

1. `docs/次の実験計画.md`
2. `docs/V1.4_一次エネルギー吸収仕様.md` — V1.4実装の正本
3. `docs/Exp08_実験計画.md` — Exp08条件の正本
4. `experiments/exp07_actions_20260830_160556/NOTES.md` — Exp07実測
5. `docs/Exp07_結果考察.md`
6. `docs/V1.3_化学資源モデル仕様.md`
7. `docs/V1.1_総括.md`
8. `docs/バージョニング方針.md`

古い以下の案は採用しない。
- 光総量0.75/0.50を次に振る
- V1.3のまま光+chemicalを直接競争させる
- Exp08旧案のlight coef 1.0/1.5/2.0 × L0/L2全組合せ
- tick全体を一気に全面フェーズ化する

## 現在地

Exp07完了:

```text
C chem2/vent: flux8以上で10/10成立
B ancestor/vent: 全80/80絶滅、chem_abs>=0.5到達0
D chem2/random: flux8以上で10/10成立
```

chemical環境自体は成立可能。通常祖先からchemical型へのbootstrapは未成立。

Exp07後監査で、光に個体吸収上限が無い等の生物側設計ミスを検出したためV1.4へ進む。

## V1.4で必ず実装するもの

### 1. 有効表面積

```text
A_eff = matter^(2/3)
```

light/chemical/nutrientの環境直接吸収へ共通適用。

### 2. 光個体吸収上限

```text
raw_light_demand
= light_uptake_coef
× light_absorption
× A_eff
× health
```

Energy空き容量でcap。

セル供給不足時は需要比例配分。

暫定Config default:

```text
light_uptake_coef = 2.0
```

恒久defaultはExp08で決定。

### 3. chemical公平配分

V1.3 source/stock/lossは変更しない。

```text
raw_chemical_demand
= chem_uptake
× chemical_absorption
× A_eff
× health
```

Energy空き容量でcap。stock不足時は需要比例配分。個体リスト順の先着biasを廃止。

`chem_uptake=0.5`はExp08では固定。

### 4. nutrient公平配分

```text
raw_nutrient_demand
= nutrient_uptake
× nutrient_absorption
× A_eff
× health
```

公平配分前に:
- Matterを取り込める余地
- 現在Energyで同化コストを払える量

でcapする。

Matter保存・Energy非負を必ず守る。

### 5. tick処理は最小限の再構成

```text
環境更新
→ 全個体が従来思想で行動決定
→ 全個体移動
→ post-move hash再構築
→ light/chemical/nutrient需要計算・セル公平配分
→ 以降は可能な限り現行逐次順
   corpse → predation → 生理/修復 → 死亡 → 繁殖 → 記録
```

死亡/繁殖まで全面フェーズ化しない。

副作用としてcorpse/predationはpost-move hashを参照し、遭遇率が変わり得る。V1.4世界境界として記録する。

## 行動原則

**未来Energy収益を予測させない。**

禁止:

```text
候補セルごとの将来Energy収益を計算
→ 最も得な場所へ移動
```

維持する思想:

> 現在感じる刺激への反射的走光性/走化性。

光供給値とchemical stockのraw比較は単位が異なるが、Exp08は各source単独なのでV1.4実装時には変更しない。

最初の光+chemical同居前に、未来予測ではない無次元受容器応答として別途設計する。

## lightとchemicalの相対スケール

`light_uptake_coef`と`chem_uptake`は同種の「遺伝するabsorption能力→実吸収速度」の変換係数だが、同じ数値に強制しない。

`chem_uptake=0.5`でも、matter0.8 / chemical_absorption=5なら個体ceilingは約2.15 E/tickであり、V1.1明部光最大約1.2を超え得る。

よってExp08前にchemicalを人工的にbuffしない。

chemical供給候補:

```text
chem_vent_flux = 8 / 16 / 24
```

16/24は「flux8が不成立だから」ではなく、世界総量は小さいままvent局所供給密度を光帯と同等以上にする事前設計候補。

## Exp08

### Phase0

必須ベンチ:
- matter 0.5/0.8/1/2/4/8
- absorption 0.3/1/2/5
- light coef 1/1.5/2/3/4
- light/chemical ceilingを同一表に出す
- 維持費/修復/初期Energy/繁殖閾値
- 1/5/20/100個体の公平配分
- nutrient Energy/Matter cap
- shuffleにSimulation.rngを使わない

### Phase A 光単独

光単独でも乱数消費維持のため:

```text
n_vents=4
chem_vent_flux=0.0
```

L0:

```text
light_absorption≈0.3固定
light_uptake_coef = 1.0 / 1.5 / 2.0 / 3.0 / 4.0
5 × 10 seed = 50 run
```

L2 positive control:

```text
light_absorption=2.0固定
light_uptake_coef=2.0固定
10 seed
```

Phase A合計60 run × 60k。

### Phase B chemical単独

```text
light=0
chemical_absorption=2.0固定 / vent
chem_uptake=0.5
chem_vent_flux=8/16/24
3 × 10 seed = 30 run
60k
```

Exp08総計90 run + Phase0。

条件は生物学的結果を見て同一Exp08内で変更しない。

## 実装テスト必須

1. matter1→surface1 / matter8→surface4
2. 低light_abs単独個体が全光を取得しない
3. light総取得=min(supply,total demand)
4. light配分が個体順不変
5. chemical配分が個体順不変
6. chemical総取得<=stock
7. nutrient各個体取得<=事前demand
8. nutrient総取得=min(stock,total demand)
9. nutrient同化後Energy非負
10. Matter保存
11. Energy台帳保存
12. light/chemical/nutrientがpost-moveセル参照
13. test shuffleはSimulation.rng非消費
14. V1.4のgolden/CI基準ref更新

V1.4では未利用光と低い光利用率が増える可能性がある。これは意図した挙動であり異常扱いしない。

## V1.4で変更しないもの

- mutation
- reproduction rule
- basic metabolic cost / organ_upkeep
- sensory/movementの基本思想
- V1.3 chemical source/stock/loss
- `chem_uptake=0.5`
- vent数/半径
- 日照時間変動
- 捕食強化
- chemical plume
- 学習/記憶
- 有性生殖

## 直近順序

```text
Exp07実測NOTES main保存 ✅
→ 正本へClaudeレビュー判断反映 ✅
→ v1.3-finalを最新保存点へ更新 ✅
→ V1.4実装 ✅ (evosim/physiology.py / simulation.py / config.py)
→ unit/Energy/Matter/RNG tests ✅ (tests/test_v14_uptake.py)
→ V1.4 golden/CI基準ref更新 ✅
→ Exp08 Phase0 ✅ (tools/bench_v14_uptake.py)
→ Exp08 90 run × 60k
→ default校正
→ 必要ならchem_uptake独立診断
→ 異種刺激比較則
→ 光+chemical同居
```

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
