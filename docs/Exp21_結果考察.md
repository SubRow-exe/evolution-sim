# Exp21 結果考察

更新: 2026-09-15  
状態: **FINAL / Opus 5 review反映済み**

関連:

- `docs/Exp21_実験計画.md`
- `docs/Exp21_Exp22_Opus5レビュー.md`
- Issue #75

---

## 1. 目的

Exp20 Attempt 2では、A2（動的噴出口環境）において `starvation_horizon` が長い個体ほど生存面で有利になることが確認された。

Exp21の目的は、その性能差が単独runの差ではなく、**同一集団内での系統頻度変化＝自然選択として実際に現れるか**を直接確認することである。

比較した2系統:

- baseline: `starvation_horizon = 1800 s`
- long-horizon: `starvation_horizon = 2700 s`（baseline ×1.5）

初期比率は50:50、突然変異はOFFとした。

---

## 2. 実験条件

- A0_STATIC: 噴出口移動なし
- A2_DYNAMIC_VENT: 48 hごとに噴出口移動
- duration: 120 h
- seed: 各環境8 seed
- 合計16 run
- initial ratio: baseline 50% / long-horizon 50%
- mutation: OFF
- phototrophy: OFF

A2では48 hと96 hの2回の噴出口移動を経験する。

---

## 3. 主結果

### 3.1 A2_DYNAMIC_VENT

120 h後のlong-horizon系統割合:

- 中央値: **56.3%**
- 8 seed中 **7 seedで50%超**
- 範囲: **45.6–63.3%**
- 固定・完全絶滅: なし

片側符号検定:

```text
P(X >= 7 | n=8, p=0.5) = 9/256 = 0.035
```

中央値からの選択係数換算:

```text
s = ln((0.563/0.437)/(0.50/0.50)) / 5 day
  ~= 0.051 /day
```

したがって、A2ではlong-horizon系統が増える方向の選択が確認された。

### 3.2 A0_STATIC — 「差がない対照」ではなく検出力の低い対照

120 h後のlong-horizon割合は中央値50.0%だった。

ただしartifactを全8 seed確認すると、**A0では両系統とも全seedで死亡0**だった。

出生数もほぼ同一で、120 h時点では:

- 6/8 seed: baseline 150 / long 150
- 2/8 seed: baseline 149 / long 150

であった。

したがってA0の50:50維持は、

> `starvation_horizon` に効果が無かった証拠

ではない。

**死亡による淘汰が起こらず、出生数もほぼ同一だったため、系統頻度が動く機会そのものが非常に乏しかった。**

よってA0は「効果なし」を示すnegative controlとして強く解釈しない。

---

## 4. 時系列と機構

A2では0–48 hまでは概ね50:50で、最初の噴出口移動後から系統差が現れ始めた。

観測は次の機構と整合する。

```text
vent turnover
-> H2供給の局所条件変化
-> Energy余裕の低下
-> long-horizon系統がより早く省エネ側へ移行
-> starvation deathを抑える
-> 生存個体が多く残る
-> その後の繁殖機会も増える
-> lineage frequencyが上昇
```

実測例（seed 21001 / A2）:

```text
死亡: long 61 / baseline 69  -> longが8個体ぶん有利
出生: long 138 / baseline 130 -> longが8個体ぶん多い
最終: long 127 / baseline 111
```

出生差は、long系統の生存個体が多く残ったため繁殖機会が増えた下流効果と読むのが自然である。

---

## 5. `starvation_horizon` は「長いほど常に有利」ではない

long-horizonには利点だけでなくコスト側もある。

`starvation_horizon` が長いと早く省エネ状態へ移る一方で:

- `metabolic_factor` が低下する
- `uptake_factor` も低下し、H2取り込みを早く絞る
- 保護reserve `P_full × starvation_horizon` が増え、成長へ回せるEnergyが減る

したがって、今回2700 sがA2で1800 sより有利だったことから、さらに長くすれば単調に有利とは言えない。

**中間に適応度最大値が存在する可能性を残す。**

---

## 6. Exp21の最終判断

**Exp21は成功と判定する。**

Exp20 Attempt 2で確認した「形質値によるfitness-related performance差」が、Exp21では同一集団内のlineage frequency変化として実際に現れた。

A2では:

1. 環境変化が起きる
2. 形質依存の生存差が生じる
3. 有利な系統が集団内で増える

という自然選択の流れを直接確認した。

ただし主張範囲は次の通りとする。

```text
確認した:
  設計者が初期集団へ置いたstanding variation（2 lineage）に対して
  physical modeで選択が働き、頻度が変化すること

未確認:
  突然変異によって新たに生じた変異が、限られたrun長の中で
  機能水準まで到達し、その後に選択されること
```

Exp21はmutation OFFであるため、後者は未解決である。

---

## 7. v1.11における位置づけ

V1.9以降持ち越されていた課題のうち、

> **physical modeでstanding variationに対して自然選択が成立するか**

については一区切りついた。

一方、短い計算予算の中で突然変異から形質を進化させる問題は残る。

そのため今後も、まず直接fitness効果とcompetitionを測り、その後に必要な世代数・seed数を逆算して進化実験を設計する方針を維持する。

---

## 8. 次の方針

v1.11を継続し、本題のprimitive phototrophyへ戻る。

Exp22ではいきなりphototrophyの進化を待たず、**physical phototrophy経路の動作確認とphoton flux calibration**をpaired runで行う。

その結果から、次段competition assayに現実的なseed数で使えるfluxが存在するかを判定する。