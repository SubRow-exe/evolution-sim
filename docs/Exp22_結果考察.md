# Exp22 結果考察 — V1.11 primitive phototrophy photon-flux calibration

更新: 2026-09-15  
状態: **RESULT REVIEW / Exp23前に再レビュー要**  
対象version: **V1.11**

関連:

- `docs/Exp22_実験計画.md`
- `docs/Exp21_Exp22_Opus5レビュー.md`
- Issue #75
- GitHub Actions run: `34919570508`

---

# 1. Exp22の目的

Exp22は、primitive phototrophyについて「進化するか」を直接見る実験ではなく、

> **どのphoton fluxなら次段のcompetition assay（Exp23）で検出可能なfitness-related effectを出せるか**

を校正するStage-1実験である。

A0_STATIC / A2_DYNAMIC_VENT、3 seed、6 flux、OFF/ON paired run、72 hで実施した。

formal runは **72/72 run完了**、preflight / aggregateとも成功した。

---

# 2. 主結果

A2_DYNAMIC_VENTにおける72 h時点の `relative delta final total living matter`（ON vs OFF）の中央値:

| photon flux [µmol m^-2 s^-1] | median Δ total living matter | 解釈 |
|---:|---:|---|
| 0 | -4.56% | zero-lightでもseed分岐/ON化に伴う差が出る |
| 0.015 | -7.42% | 効果は検出できない |
| 0.05 | -5.65% | 効果は検出できない |
| 0.15 | +2.22% | 境界域。seed間符号不一致が大きい |
| 0.5 | **+12.40%** | 中程度の正の生態効果 |
| 1.5 | **+55.35%** | 強すぎる正の効果 |

A2のpopulation差（ON-OFF）中央値:

```text
flux 0      : -4
flux 0.015  : -7
flux 0.05   : -5
flux 0.15   : +4
flux 0.5    : +11
flux 1.5    : +46
```

A2のstarvation death差（ON-OFF）中央値:

```text
flux 0      : +1
flux 0.015  : +11
flux 0.05   : +3
flux 0.15   : -4
flux 0.5    : -6
flux 1.5    : -32
```

したがって、高fluxではphototrophyが単なるEnergy ledger上の差ではなく、**生存・個体数・総living matterへ明確に翻訳されている**。

---

# 3. flux-responseの解釈

Exp22の結果は大きく4領域に分けられる。

```text
0.015 / 0.05 : 弱すぎる。zero-light controlのばらつきと同程度以下
0.15         : transition / borderline領域
0.5          : 明確だが圧倒的ではない中程度の効果
1.5          : 強いpositive control。competitionでは必勝能力化する懸念
```

特に `0.5` は3 seed中2 seedで明確に正、1 seedではほぼ中立であり、medianでは総living matter +12.4%、population +11、starvation death -6となった。

同じseedのzero-light controlとの差を見ると、`0.5` の総living matter効果は3 seedすべてでzero-lightより正方向へ改善しており、その差の中央値は約 **+18.3 percentage points** である。

一方 `1.5` は全seedで非常に強い正効果を示し、Exp23の主条件としては強すぎる可能性が高い。

---

# 4. `NO_WORKING_FLUX_IN_RANGE` の読み方

aggregateは `NO_WORKING_FLUX_IN_RANGE` を返したが、これは

> 「phototrophyに有効なfluxが存在しなかった」

という意味ではない。

candidate判定はA2 48–72 hの `R_E`（stored Energy protection）を主要条件としており、

```text
R_E > 0 in 3/3 seed
median R_E >= +1%
```

を要求していた。

しかし高fluxでは、追加Energyはstored Energyとして残るよりも、**成長・繁殖・生存維持へ使われる**。実際、`0.5` と `1.5` では総living matterとpopulationが大きく増える一方、48–72 hのstored Energy差は負方向になる。

したがって、Exp22で判明したのは

> **stored Energyをcompetition候補選定のprimaryにしたこと自体が不適切だった**

という点である。

Exp23のflux選定では、stored Energyはmechanistic diagnosticに降格し、

```text
population
starvation deaths
total living matter
lineage frequency
```

をfitness側の主要指標とするべきである。

---

# 5. zero-light controlの注意点

A2ではflux=0でもON/OFF間に

```text
median Δ total living matter = -4.56%
median Δ population = -4
```

が生じた。

structural N costはIssue #75で確認された通り非常に小さいため、この差を単純にphototrophy apparatus costと解釈するのは不適切である。

phototrophy ON化に伴う初期の微小差や、その後の死亡・出生イベントによるRNG trajectory divergenceがA2で増幅された可能性が高い。

したがって低fluxの `0.015 / 0.05 / 0.15` は、このnoise floorを明確に超えたとは言いにくい。

一方 `0.5` と `1.5` はzero-light controlから十分に離れており、phototrophy由来の正効果とみなす根拠が強い。

---

# 6. Exp23候補flux

## 第一候補: `0.5 µmol photons m^-2 s^-1`

理由:

1. A2でmedian total living matter **+12.4%**
2. median population **+11**
3. median starvation deaths **-6**
4. zero-light controlとの差が明確
5. `1.5`ほど支配的ではなく、competitionで選択係数を測る余地が残る

したがって、現時点では

> **Exp23 primary working flux = 0.5 µmol photons m^-2 s^-1**

を第一候補とする。

`1.5` は必要ならpositive controlとして使用可能だが、主条件にはしない。

`0.15` はborderline conditionとして補助的価値はあるが、Exp23 primaryには採用しない。

---

# 7. 実装・事前登録との差分

今回のClaude実装には、Issue #75反映後の最終計画との差分がある。

## D1 — zero fluxの扱い

最終計画では `0 -> 1e-6` への置換を事前登録していたが、実装では `Config` validationを変更して **flux=0を許容**し、そのままformal runを行った。

物理的にはzero-light controlとして意味のある変更だが、**事前登録からの変更**なので、Exp23へ進む前に妥当性をレビューで明示確認する。

## D2 — Exp23必要seed数の見積もり未実装

Issue #75で追加した

> Exp22の人口統計効果からExp23必要seed数を逆算し、recommendation artifactへ残す

という要件がaggregateへ実装されていない。

Exp23計画を確定する前に、Exp21のlineage-frequency noise floorと今回の `0.5` 効果を使って、必要seed数を改めて決める必要がある。

## D3 — candidateロジックが旧R_E中心のまま

Issue #75反映後は人口統計効果も候補選択へ含める方針だったが、実装された `aggregate_exp22.py` は旧来のR_E条件中心である。

このため `NO_WORKING_FLUX_IN_RANGE` は正式な生物学的結論として採用しない。

---

# 8. Exp22最終判断

**Exp22はcalibration experimentとして成功と判定する。**

確認できたこと:

- physical phototrophy経路はformal runで動作した
- photon flux増加に伴い、生態的効果が弱い領域から強い領域へ移ることを確認した
- `0.5` 付近にcompetition assayへ使いやすい中程度の効果域が存在する
- `1.5` は強いpositive controlとして機能する
- stored Energy単独ではfitness候補選定に不適切であることが判明した

まだ確認していないこと:

- phototrophy ON lineageが同一集団内で実際に増えるか
- `0.5`でのlineage selection coefficient
- structural N costがN律速環境でtrade-offとして働くか
- mutationからphototrophyが生成・選択されるか
- day/night cycle下での適応性

---

# 9. 次の方針

Exp23を正式化する前に、本結果をClaude / Opusへ再レビューさせる。

重点レビュー項目:

1. `0.5 µmol m^-2 s^-1` をExp23 primary fluxとする判断は妥当か
2. `1.5`をpositive controlとして併用すべきか
3. zero-light A2差（median -4.56%）の原因解釈に問題がないか
4. R_Eをcandidate判定から外し、population / deaths / total living matterを重視する修正が妥当か
5. Exp23で必要なseed数を何seedにするべきか
6. flux=0をConfig変更で許容した今回の実装変更を正式採用してよいか
7. Exp23前に追加のmechanical / statistical gateが必要か

レビュー後にExp23をpreregisterし、実装・実行へ進む。
