# Exp13 結果考察（Phase A中断時点）

更新: 2026-09-03
状態: **Phase Aで科学的STOP。Phase B未実施。Exp14へ原因切り分けを移行。**

実行:
- workflow: `Exp13`
- run id: `33722634280`
- formal SHA: `a8f33648c0287b5eb47304f0c079b90715a19130`
- Phase 0: PASS
- Phase A1/A2: 実行済み
- select_A: `LIGHT_CALIBRATION_FAIL / REVIEW`
- A2b/A3/Phase B: 未実施

> GitHub Actions上の最終conclusionは `failure` だが、今回の主要因は計算クラッシュではなく、事前規則どおり **light候補が1つもROBUST_LIGHT_VIABLEにならなかったための科学的STOP** である。

---

# 1. Exp13で起こったこと

## 1.1 Phase A1 — light sweep

事前候補:

```text
light_max = 0.8, 1.2, 1.5, 1.8, 2.1, 2.4, 3.0, 4.0
5 seed × 10,000 tick
```

集計結果:

| light_max | COMPLETE | EXTINCT | late birth OK | robust viable |
|---:|---:|---:|---:|---|
| 0.8 | 0/5 | 5/5 | 0/5 | False |
| 1.2 | 0/5 | 5/5 | 0/5 | False |
| 1.5 | 0/5 | 5/5 | 0/5 | False |
| 1.8 | 0/5 | 5/5 | 4/5 | False |
| 2.1 | 0/5 | 5/5 | 5/5 | False |
| 2.4 | 0/5 | 5/5 | 5/5 | False |
| 3.0 | 0/5 | 5/5 | 5/5 | False |
| 4.0 | 0/5 | 5/5 | 5/5 | False |

したがって事前規則どおり:

```text
selected_light_max = NONE
LIGHT_CALIBRATION_FAIL / REVIEW
```

となり、Phase Bへは進まなかった。

## 1.2 light_max=4.0 の詳細

最大光量でも5/5 seedが餓死絶滅した。

| seed | 昼の最大population | 最大時tick | extinction tick | 最終births_cum | starvation deaths |
|---:|---:|---:|---:|---:|---:|
| 1 | 503 | 100 | 404 | 515 | 515 |
| 2 | 453 | 100 | 377 | 466 | 466 |
| 3 | 494 | 100 | 397 | 506 | 506 |
| 4 | 440 | 100 | 382 | 457 | 457 |
| 5 | 492 | 100 | 580 | 508 | 508 |

共通パターン:

```text
initial population = 100
↓
開始直後に約200へ増殖
↓
最初の昼の終わり（tick 100）に約440〜503まで増殖
↓
100 tickの夜（light=0）
↓
tick 200で約8〜16個体まで急減
↓
次の昼に少数が再繁殖
↓
次の夜で再び崩壊
↓
最終的に全seed starvation extinction
```

例: seed1

```text
tick  20: pop 200
40:       234
60:       332
80:       462
100:      503  ← 日没
120:      500
140:      393
160:      191
180:       71
200:       14  ← 夜明け
```

死亡原因は事実上 starvation に集中している。

## 1.3 「単純に光量が少ない」だけでは説明しにくい

seed1の例では:

```text
light=2.4 -> max pop 246 / extinction tick 373
light=3.0 -> max pop 321 / extinction tick 562
light=4.0 -> max pop 503 / extinction tick 404
```

光を増やすほど昼のpopulationは増えたが、`4.0`が`3.0`より長く生きるとは限らなかった。

したがって現時点では:

> 光量を上げれば単調に安定性が改善する

とは判断できない。

---

# 2. 原因について現在もっとも有力な解釈

## 2.1 長い連続無供給時間

現V1.8:

```text
light_cycle_period_ticks = 200
light_day_fraction = 0.5
```

なので:

```text
100 tick daylight
100 tick complete darkness
```

になる。

tickは現実の時間単位ではなく、現在の代謝・Energy capacity・繁殖時間スケールに対して **100 tick連続無供給が長すぎる可能性** がある。

## 2.2 昼間のboomが夜越しreserveを壊している可能性

A1標準個体の初期条件:

```text
initial_energy = 50
initial_matter = 0.8
energy_capacity = 100 × body_size
body_size = 1.0
repro_energy_frac = 0.6
```

初期Energyは繁殖閾値近傍/以上にあり、開始直後からpopulationが100→約200へ増える。

さらに昼間にEnergyを得ると大量繁殖し、親が蓄えたEnergy/Matterの一部が子へ分配される。

結果として:

```text
昼: abundant light -> rapid reproduction / population boom
夜: light=0 -> reserve不足 + 大population維持費
   -> starvation crash
```

というboom-bustが繰り返されている可能性が高い。

これは「初回の初期条件事故」だけではない。最初の夜を生き残った少数個体も次の昼に再繁殖し、その後の夜で再び崩壊する。

## 2.3 総光量不足も否定しない

`light_max=4.0`でも全滅しているため、平均Energy供給が不足している可能性も残る。

ただし上記boom-bustのため、**光量不足と夜長・繁殖圧を混ぜたまま単純にlight_maxだけ拡張しても原因を切り分けられない。**

---

# 3. Chemical側で分かったこと

Phase A2 chemical gridは正常に情報を得られた。

事前admissibilityを満たした組合せ:

```text
K=1.5, chem_uptake=0.5  group median H≈0.565
K=3.0, chem_uptake=0.5  group median H≈0.599
K=6.15, chem_uptake=1.0 group median H≈0.181
```

事前選定規則:
1. admissible中の最小 `chem_uptake`
2. 同じuptakeでmedian Hが0.5に最も近いK

をそのまま適用すると、暫定第一候補は:

```text
chemical_uptake_half = 1.5
chem_uptake = 0.5
```

である。

ただしExp13はlight calibrationでSTOPしたため、A2bの10k長期/探索確認とA3密度競争は未実施。**working chemical値として正式確定はしない。**

Exp14ではchemical gridを再計算せず、この結果を保存してlight原因切り分けを優先する。

---

# 4. Collector / workflow上の補足

## 4.1 `late_pop_ok` 表示

A1集計では全seed絶滅している低光量条件でも `late_pop_ok` がTrueになる例がある。

これは科学結論を変えないが、late windowへ到達していない/絶滅runの扱いが紛らわしい。

Exp14前に:
- early extinctionをlate-pop PASSとして数えない
- `False`または`N/A`を明確化

する。

## 4.2 GitHub Actionsの赤FAIL表示

科学的calibration failureをnon-zero exitで表現したためActions上は技術failureに見える。

今後は:

```text
SCIENTIFIC_STOP / REVIEW
```

と

```text
TECHNICAL_FAIL / INTEGRITY_FAIL
```

をUI/summary上でも区別する。

科学STOP時もartifact/reportを保存してworkflowを意図的終了したことが分かるようにする。

---

# 5. Exp13の科学的結論

Exp13は「無駄な失敗」ではない。

Phase Aによって:

1. V1.8のday/night + density response環境で、事前light範囲0.8〜4.0では頑健light生態系が成立しないことを検出した
2. 最大光量4.0でも、昼の急増→夜のstarvation crashという明瞭なboom-bustを発見した
3. 単純なlight_max不足だけでなく、day/night時間スケールと繁殖/貯蔵Energyの相互作用を切り分ける必要があると判明した
4. chemical側は候補領域を狭めることができた

したがってExp13 Phase Bをそのまま再開せず、次はExp14でlight extinction mechanismを診断する。

---

# 6. 次

正本:

`docs/Exp14_実験計画確定.md`

Exp14で原因を切り分けた後に、必要なら次実験でlight量/周期を広く再地図化する。
