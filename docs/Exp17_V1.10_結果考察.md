# Exp17 V1.10 結果・考察

更新: 2026-09-08  
状態: **CLOSED / PHASE A PASS / PHASE B INVALID AS IDENTITY GATE / PHASE C1 COMPLETE**

Exp17はV1.10でgeneric environmental MatterをDIC / fixed N / phosphateへ分解し、C/N/P収支・growth limitation・fixed iLUCA成立性を確認する実験である。

---

# 1. Phase 0 — mechanical validation

C/N/Pについてclosed ledger、growth assimilation、recycling、および各元素を極端に不足させるlimiter sentinelを確認した。

結果:

- C/N/P ledgerは数値誤差範囲でclosure
- carbon / nitrogen / phosphorusをそれぞれ独立にgrowth limiterとして発動可能
- generic environmental Matterを使わずC/N/Pからbiomassを構成可能

したがって、C/N/P mechanismそのものは成立している。

---

# 2. Phase A — reference open environment

条件:

```text
5 seeds x 10 physical days
fixed iLUCA
V1.9 H2 baseline維持
V1.10 initial reference C/N/P + background exchange
```

結果:

```text
5/5 survived 10 days
5/5 reached max_generation = 5
final population = 2945–3004
mean final population = 2978.8
C/N/P ledger residual = おおむね1e-15 order
```

累積growth limiterは概ね:

```text
Energy  ≈ 99.81%
Room    ≈ 0.153%
Kinetic ≈ 0.041%
C       = 0%
N       = 0%
P       = 0%
```

解釈:

- C/N/P明示化によってiLUCAの生存・成長・世代交代は壊れなかった。
- 元素台帳も十分な精度で閉じた。
- 一方、reference C/N/P量は現在の100個体・20 mm worldの生物需要に対して非常に大きく、10日間ではC/N/P制約は発生しなかった。

**Phase Aはscientific PASS。**

---

# 3. Phase B — low C / N / P identity test

条件:

```text
B0 reference
B1 DIC x0.01
B2 fixed N x0.01
B3 phosphate x0.01
各3 seeds x 3 days
```

結果:

- 同一seedではB0/B1/B2/B3のpopulation / generation / limiter挙動が実質同一
- C/N/P limiterはいずれも0%
- Energy limiterが約99.75%を占めた

したがって、1/100へ減らしてもC/N/Pは依然として十分多く、Phase Bは意図したidentity stress領域へ到達しなかった。

これはC/N/P mechanism failureではない。Phase 0では各元素を独立limiterとして作動させられているため、主因は**環境stockのスケールが生物需要に対して過大だったこと**である。

## 3.1 自動gateの不具合

Phase B aggregateは当初PASSを返したが、この判定は無効である。

旧実装ではtarget C/N/P limiterを、他のC/N/P limiterだけと比較していた。そのため:

```text
C = 0
N = 0
P = 0
```

でも `0 >= 0` によりtargetが最大と誤判定された。実際の最大limiterはEnergyだった。

従って記録は:

> **Phase B = scientific identity gate NOT DEMONSTRATED / original auto-PASS invalid**

とする。

V1.10 close可否はPhase 0のmechanical identity validationと、後続Phase C1の有限resource実証を含めて判断する。

---

# 4. Phase C1 — C/N/P初期配置量校正

Phase B後の診断として、C/N/P background exchangeをOFFにし、初期100個体と同じbiomassを新たに作る元素量を1 biomass-equivalentとして有限stockを配置した。

条件:

```text
C10   = 10 equivalents
C30   = 30 equivalents
C50   = 50 equivalents
C100  = 100 equivalents
3 seeds each / 10 days
12/12 runs complete
```

GitHub Actions run: `34111388635`

配置濃度:

| condition | DIC | fixed N | phosphate |
|---|---:|---:|---:|
| 10x | 0.0273916 uM | 0.00549725 uM | 0.000451992 uM |
| 30x | 0.0821747 uM | 0.0164918 uM | 0.00135598 uM |
| 50x | 0.136958 uM | 0.0274863 uM | 0.00225996 uM |
| 100x | 0.273916 uM | 0.0549725 uM | 0.00451992 uM |

主要結果:

| placement | C/N/P制約 | 初回CNP limiter | final population | final stock |
|---|---|---|---:|---|
| 10x | 明確に発生 | 約6.1 day | 約800 | ほぼ枯渇 |
| 30x | 発生 | 約8.8 day | 約2190 | ほぼ枯渇 |
| 50x | 10日では無し | none | 約2980 | 約15%残存 |
| 100x | 無し | none | 約2980 | 約58%残存 |

50xと100xでpopulation trajectoryはほぼ同等であり、30x以下では有限C/N/P stockが明確にgrowthを制約した。

したがって10日スケールのtransitionは概ね:

```text
30–50 biomass-equivalents
```

に存在する。

---

# 5. 人間判断 — V1.10 working baseline

35x / 40x / 45xの追加探索は行わない。

理由:

- 目的は最適値探索ではなく、C/N/Pが有限資源として機能することの確認
- 50xで10日間の通常成長を妨げず、30x以下では不足が実際に進化圧になり得る
- 将来不都合が出た場合に再校正すればよく、現段階で境界を細かく決める価値は低い

人間判断により、今後のworking baselineは:

> **initial C/N/P stock = initial 100-cell biomass requirementの50 equivalents**

を暫定採用する。

この50xはearly Earth海洋の真の濃度を主張する値ではなく、現在のworld volume / agent scaleと生物需要を整合させるsimulation working referenceである。

また50xを有限資源として意味あるものにするため、**C/N/P background exchangeは当面OFFをworking baselineとする。** 将来、advection / environmental cycling / external nutrient supplyを導入する際に別world-ruleとして再検討する。

---

# 6. Exp17結論

Exp17から確認できたこと:

1. C/N/P elemental bookkeepingは成立する。
2. C/N/Pはそれぞれ独立growth limiterとして機能する。
3. fixed iLUCAはC/N/P明示化後も生存・成長・世代交代できる。
4. 当初reference濃度は現在のsimulation生物量に対して過大だった。
5. 有限50x stockをworking referenceにすると、通常10日runを妨げず、より低いstockでは栄養不足という進化圧を作れる。
6. Phase B旧auto-PASSはgate実装bugであり科学的PASSとして扱わない。

以上より、**V1.10の目的は達成したと判断する。**
