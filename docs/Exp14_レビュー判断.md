# Exp14 Opus 5レビュー判断

更新: 2026-09-03
状態: **人間判断確定 / Exp14正本へ反映対象**

レビュー原文:
- branch: `claude/review-v1-7-exp11-kflr82`
- commit: `2383ee5afee50ac5493d3a5332eb7d2433ae0c0e`
- file: `docs/Exp14_Opus5レビュー.md`

本書はレビュー提案の採否を確定する正本である。レビュー原文より本書を優先する。

---

# 1. Exp13 light絶滅の原因について

Opus 5の中心診断を採用する。

Exp13の絶滅は単純なlight総量不足では説明しにくく、主要因は:

```text
夜の長さ
vs
日没前に個体が保持できるEnergy reserveと夜間消費
```

の時間スケール不整合である。

特に現行条件では繁殖がEnergy reserveを親子へ分配するため、昼にlightを増やしても余剰Energyがそのまま夜越し用貯蔵へ積み上がらず、昼のpopulation boom -> 夜のstarvation collapseが起きる。

ただしレビュー原文の「0.6*Emaxより上へ絶対に貯められない」は一般則としては強すぎる。繁殖にはmatter条件も必要である。Exp13の固定表現型・資源条件では実質的に繁殖がreserveの圧力弁として働いた、と限定して解釈する。

---

# 2. R指標 — 採用

主要診断量として次を事前登録する。

```text
R_ref = night_length_ticks / night_survival_ticks(reference reserve)
```

reference reserveは、そのarmの固定表現型について現行実装の維持費・移動・repairをそのまま使って決定論計算する。

Exp14の目的は `R<1なら必ず成立` のような普遍閾値を決めることではない。

目的は:

> arm間の崩壊/存続が、R_refの変化で一貫して説明できるか

を検証すること。

A1/A2/A4等が複数改善しても、同じRを別方向から下げているだけなら「複数原因のinteraction」とは結論しない。

A3（light量だけ増加）はR_refをほぼ変えないため、R仮説の反証armとして残す。

---

# 3. MUST FIX採否

## M1: Rを主要読み出しへ — 採用

- 各armのrun前予測R_refをmanifest/reportへ保存
- 実測の `night_min / preceding_day_peak`、日没/夜明けEnergy fractionと照合
- A3が明確に改善した場合はR単独仮説を反証し、light総量等を再検討する

## M2: 「改善」の定義を事前登録 — 採用

Phase Aの二値分類:

```text
SURVIVES_SHORT:
  3/3 seedが2,000 tick到達、final population > 0

MARGINAL:
  2/3 seedが2,000 tick到達

COLLAPSE:
  0-1/3 seedが2,000 tick到達
```

ただしExp14は短期diagnosticなので、`SURVIVES_SHORT`は長期平衡を意味しない。

連続量として必ず:
- extinction tick
- survived nights
- daytime peak population
- night minimum population
- night_min / preceding_day_peak
- sunset/dawn Energy/capacity distribution
を併記する。

## M3: A4の初期条件交絡 — 採用

A5を追加:

```text
A5 initial-condition control
baselineと同じ
initial_energy = 40
repro_energy_frac = 0.6
```

これでtick1一斉繁殖だけを抑え、A4の定常reserve効果と分離する。

---

# 4. SHOULD FIX採否

## S1: energy_capacity arm — 採用、ただし条件を修正

A6を追加する。

```text
energy_capacity = 200
initial_energy = 100
その他baseline
```

レビュー原案の `energy_capacity=200` だけでは、初期 `E/Emax` が半減して初期条件が変わる。

そこで:

```text
baseline: cap=100, initial_energy=50
A6:       cap=200, initial_energy=100
```

として初期Energy充填率を揃える。tick1繁殖可能/不可能という初期状態もbaselineと同型に保ち、主に貯蔵容量スケールの効果を見る。

A6は恒久default変更を意味しない。diagnostic interventionである。

## S2: 進化OFFの結論範囲 — 採用

Phase A/B固定表現型の結論は:

> INITIAL_GENOME近傍の固定表現型についての因果/境界診断

に限定する。

V1.8の昼夜世界そのものが原理的に成立不能とは結論しない。

既存の進化機構で自然適応できるかをExp14後半で直接確認する。

## S3: A3事前予測 — 採用

```text
A3 light_max=8.0
事前予測: R_refはほぼ不変なので、夜collapseは根本改善しない
```

A3がSURVIVES_SHORTへ明確に転じる場合、R仮説を反証する重要結果とする。

## S4: A1の供給と実効吸収は完全一致しない — 採用

A1の条件自体は変更しない。

reportへ:
- supply time-averageは揃えている
- density response H(I,K)が非線形なので1個体あたり実効吸収は完全一致しない
- realized H / per-organism light uptakeを併記

と明記する。

## S5: 夜間休止機構が無い — 記録のみ採用

Exp14では新しい休止ルールを実装しない。

ただし現状:
- 夜もwanderする
- `idle_prob`は現行行動則で実質利用されていない
- 夜間低活動は将来の全個体対称rule候補

として記録する。

---

# 5. Exp14を10時間枠で拡張する方針

ユーザーから今回のformal phaseには約10時間のwall-clock余裕がある。

短い原因診断だけで終了せず、**結果を後付けして条件追加しない範囲で、事前登録した3段階を用意する。**

```text
Phase A: mechanism diagnostic
Phase B: period x energy_capacity boundary map
Phase C: evolutionary rescue probe
```

Phase B/CはExp14実行前に条件・分岐・runtime profileを固定する。

結果後の思いつきで同一Exp14へarmを追加しない。

---

# 6. runtime budgetの扱い

formal前にrepresentative benchmarkを取り、Exp14全体wall-clockを予測する。

科学結果ではなく**runtime予測だけ**で、事前登録済みの2 profileから選ぶ。

```text
FULL profile:
  Phase A 2k
  Phase B 5k
  Phase C 20k

COMPACT profile:
  Phase A 2k
  Phase B 3k
  Phase C 10k
```

選択規則:

```text
FULLの安全率込み予測 <= 9時間:
    FULL
else:
    COMPACT
```

COMPACTでも安全率込み予測が10時間を超える場合、formal開始前に人間へ報告し、自動で条件削減しない。

これにより10時間枠を有効活用しつつ、Actions時間超過を避ける。

---

# 7. 結論

Opus 5レビューは主要部分を採用する。

特に:
- R_refによる単一機構検証
- 改善定義の事前登録
- A5で初期一斉繁殖を分離
- A6でEnergy貯蔵容量を診断

をExp14前に正本へ反映する。

加えて10時間枠を使い、固定表現型の境界地図と、既存遺伝子だけで自然適応が可能かまで同じExp14で調べる。
