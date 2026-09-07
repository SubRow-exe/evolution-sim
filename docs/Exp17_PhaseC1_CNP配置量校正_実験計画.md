# Exp17 Phase C1 — C/N/P初期配置量校正診断

更新: 2026-09-07  
状態: **POST-EXP17 DIAGNOSTIC AMENDMENT / HUMAN APPROVED BEFORE EXECUTION**

## 0. 位置づけ

これはExp17 Phase A/Bの結果を保存した後に追加する**条件付きPhase C診断**である。
Phase A/Bの事前登録条件・結果を後から書き換えない。

Exp17 Phase BではDIC / fixed N / phosphateを各1/100へ下げても、対応するC/N/P limiterが実質的に発動しなかった。
Phase A seed 17001では10日間のbiological uptakeが、初期100個体が持つ元素量に対して約42.44倍分だった。一方、reference worldの初期環境stockは初期生物量に対して概算でC約8.0e5倍、N約1.8e4倍、P約2.2e4倍あり、さらに900 s時定数のbackground exchangeがある。

したがってPhase C1では、**外部補充を切り離し、初期生物量に対して何倍分のC/N/Pを有限配置すると資源制約が現れるか**を測る。

これはreference濃度を生存側へ自動調整する実験ではない。結果からV1.10 defaultを自動採用しない。

---

## 1. 目的

1. C/N/Pの「初期配置量」と生物需要のスケール関係を数値で確認する。
2. background exchangeの効果を混ぜず、有限reservoirだけの影響を分離する。
3. 10日スケールでC/N/P制約が現れる境界を、おおまかにbracketする。
4. 今後background exchangeを再導入するときの供給量校正に使える基準を得る。

---

## 2. 配置量の定義

初期個体群は100個体、各個体 `matter=0.50`、`matter_unit_to_kgdw=2.8e-16` なので、初期総dry biomassは:

```text
B0 = 100 * 0.50 * 2.8e-16
   = 1.4e-14 kgDW
```

V1.10固定biomass組成:

```text
C = 0.47 kg/kgDW
N = 0.11 kg/kgDW
P = 0.02 kg/kgDW
```

world volume:

```text
40 * 40 * (5e-4 m)^2 * (5e-4 m)
= 2.0e-7 m3
```

「1 biomass-equivalent」は、現在の初期100個体と同じdry biomassを新しく作るのに必要なC/N/P mol量と定義する。

```text
1 eq C = 5.47831155e-13 mol
1 eq N = 1.09945027e-13 mol
1 eq P = 9.03983987e-15 mol
```

---

## 3. 条件

共通:

- V1.10 / Exp17と同じfixed iLUCA
- H2 baselineはV1.9確定値のまま
- continuous genes固定
- structural innovation OFF
- initial population = 100
- 10 physical days
- seeds = `17201, 17202, 17203`
- C/N/P diffusionはV1.10値のまま
- **`cnp_background_exchange_enabled=False`**
- generic `nutrient`は不使用

C/N/Pは常にbiomass stoichiometryと同じ比で一緒に増減させる。
したがって本実験は「C/N/Pのどれが律速か」を識別する実験ではなく、**材料総量がいつ成長制約になるか**を見る。

### C10 — 10 biomass-equivalents

```text
DIC       = 2.73915577e-05 mol/m3 = 0.0273916 uM
fixed N   = 5.49725137e-06 mol/m3 = 0.00549725 uM
phosphate = 4.51991993e-07 mol/m3 = 0.000451992 uM
```

### C30 — 30 biomass-equivalents

```text
DIC       = 8.21746732e-05 mol/m3 = 0.0821747 uM
fixed N   = 1.64917541e-05 mol/m3 = 0.0164918 uM
phosphate = 1.35597598e-06 mol/m3 = 0.00135598 uM
```

### C50 — 50 biomass-equivalents

```text
DIC       = 1.36957789e-04 mol/m3 = 0.136958 uM
fixed N   = 2.74862569e-05 mol/m3 = 0.0274863 uM
phosphate = 2.25995997e-06 mol/m3 = 0.00225996 uM
```

### C100 — 100 biomass-equivalents

```text
DIC       = 2.73915577e-04 mol/m3 = 0.273916 uM
fixed N   = 5.49725137e-05 mol/m3 = 0.0549725 uM
phosphate = 4.51991993e-06 mol/m3 = 0.00451992 uM
```

値はrunner内でもConfigとstoichiometryから再計算し、`effective_config.json`へ実値を保存する。

---

## 4. 事前予測

Phase A seed 17001の10日間C uptakeは `2.32494633e-11 mol` で、初期community C量の約`42.44 eq`に相当した。固定stoichiometryなのでN/Pも同じbiomass-equivalentで増える。

したがって、referenceと同じ成長軌跡を仮定した単純予測は:

```text
C10  : 明確に材料制約が出る
C30  : 材料制約が出る
C50  : 境界付近
C100 : 10日では材料総量に余裕がある
```

ただし、資源が減ると成長自体が遅くなるため、42.44 eqを厳密な閾値とは扱わない。

---

## 5. readout

各runで最低限:

- final / max population
- max generation
- total biomass time series
- C/N/P field stock time series
- C/N/P biological uptake
- C/N/P ledger residual
- external C/N/P in/out（exchange OFFなので0であること）
- growth limiter counts / fractions
- **late 24 h limiter fraction**
- C/N/P limiterが初めて観測された時刻
- final environmental C/N/P remaining fraction

C/N/Pは同じstoichiometric比で配置するため、個別C/N/P limiter名のtie/orderよりも、

```text
combined CNP limiter fraction
```

を主診断とする。

---

## 6. integrity gate

科学結果をPASS/FAILで選別しない。ただし以下は実験成立条件として必須:

```text
3 seeds x 4 conditions = 12 runsが全て存在
C/N/P ledger relative residual <= 1e-6
C/N/P external in/out == 0 within numerical tolerance
conditionの実効Configが指定equivalent量と一致
```

不足artifactやledger破綻はscientific resultではなくintegrity failureとする。

---

## 7. 解釈規則

結果からreference/defaultを自動変更しない。

主に次の形で境界を報告する:

```text
10x: CNP制約あり/なし
30x: CNP制約あり/なし
50x: CNP制約あり/なし
100x: CNP制約あり/なし
```

例:
- 30xで強いCNP制約、50xで弱い/無し → transitionは30–50 eq付近
- 50xでも強い、100xで無し → 50–100 eq付近
- 100xでも強い → 上限不足。値を外挿採用せず追加診断を検討
- 10xでも全くCNP制約が出ない → stoichiometric uptake / limiter / inventory実装を再監査

Phase C1後に必要なら、別Phase C2としてbackground exchange supply rateを校正する。
