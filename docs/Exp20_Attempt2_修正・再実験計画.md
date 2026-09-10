# Exp20 Attempt 2 — V1.11 Phototrophy 修正・再実験計画

更新: 2026-09-10  
状態: **PREREGISTRATION / 実装修正後に実行**

関連:

- `docs/Exp20_結果考察.md`
- `docs/Exp20_V1.11_PrimitivePhototrophy_SeededInvasion_実験計画.md`
- `docs/V1.11_原始Phototrophy_実装仕様_rev2.md`
- Opus 5 Review Issue #71

---

## 0. Attempt 2を行う理由

Exp20 Attempt 1では、physical phototrophyとは別にlegacy `_absorb_light()` 経路がphysical modeでも動作しており、phototrophへJouleスケールと整合しないEnergyが流入していた。

またprimary endpointを48 hに置いたため、A1でancestor lineageが評価時点までにほぼ全滅し、pseudocountを使ったrelative log-ratioが本来のfitness差ではなくlineage extinctionに支配された。

したがってAttempt 1の生態学的結論は無効とし、コード修正後に同じ問いをAttempt 2として再検証する。

---

# 1. Attempt 2の問い

主質問:

> **正しいphysical phototrophy経路だけを使ったとき、primitive phototrophyはA0_STATICよりA1_TEMPORALでearly relative fitnessを上げるか？**

副質問:

1. A0でAttempt 1の決定論的16倍sweepが消えるか
2. A1でphototroph founderがancestorより長く生存するか
3. phototrophy seeded armがancestor-onlyよりtotal population extinctionを遅らせる／回避するか
4. 1% / 10% / 50% founderで結果が変わるか
5. 観測Energy差がV1.11 physical mechanismの理論上界内に収まるか

---

# 2. 実行前のMUST FIX

## 2.1 physical modeからlegacy light Energy経路を除去

physical modeでは旧 `_absorb_light()` による `world.light -> org.energy` 加算を行わない。

capability OFF時だけ止めるgateでは不十分。physical modeのEnergy pathからlegacy routeそのものを排除する。

確認事項:

```text
physical_mode == True
=> legacy light Energy contribution == 0
```

また `light_max` / `light_uptake_coef` 等のlegacy parameterを変えてもphysical modeのEnergy trajectoryが変化しないことをtestする。

## 2.2 production stepを通すEnergy上界test

`Simulation.step()` を実際に通し、phototrophとancestorのEnergy差がphysical phototrophyで説明可能な上界を超えないことをassertする。

概念式:

```text
DeltaE_photo - DeltaE_ancestor
<= physical_photo_usable_upper_bound
 + |maintenance_difference|
 + tolerance
```

この上界はV1.11の累積counterをそのまま真値として使用せず、photon flux・geometry・absorptance・変換効率・dt等から独立に計算する。

## 2.3 T5 behavioral test

「light alone does not fund sustained net biomass growth」を、関数signatureではなくproduction simulation behaviorで確認する。

## 2.4 dark / OFF regression

最低限:

- physical light OFF
- photon flux = 0
- phototrophy capability OFF

でphoto由来Energyが0になることを実stepで確認する。

---

# 3. Formal conditions

Attempt 1と生物学的条件は変えない。

```text
physical_mode = True
dt_seconds = 10 s
initial_population = 100
Duration = 120 h

Environment:
  A0_STATIC
  A1_TEMPORAL

Initial phototroph frequency:
  0%
  1%
  10%
  50%

Seeds:
  20001
  20002
  20003

physical light:
  light_photon_flux_umol_m2_s = 0.015
  light_effective_wavelength_nm = 800
  light_physical_pattern = uniform
  phototrophy_radiant_to_usable_eff = 0.10
  light_cycle = OFF

phototroph:
  capability = ON
  light_absorption = 0.01 fixed

ancestor:
  capability = OFF
  light_absorption = 0
```

総run数:

```text
2 environments x 4 founder frequencies x 3 seeds = 24 runs
```

Attempt 2内で結果を見てparameterを変更しない。

---

# 4. Preflight gate

formal run前に以下をPASS必須とする。

### G1 — legacy route zero

physical modeでlegacy light Energy contributionが0。

### G2 — Energy upper bound

production `Simulation.step()` を通したphototroph-ancestor Energy差がphysical mechanismの独立上界内。

### G3 — dark behavior

photon flux 0でphoto credit = 0。

### G4 — no-light growth behavior

lightのみでは持続的net biomass growthをfundしない。

### G5 — existing ledgers

```text
C/N/P closure
photo_used <= photo_usable_max <= photo_absorbed <= photo_incident
structural N accounting
H2 ledger
```

### G6 — legacy parameter independence

physical modeでlegacy `light_max` / `light_uptake_coef` を変えても結果へ影響しない。

1項目でもFAILならformal 24 runを開始しない。

---

# 5. Primary endpoint — early relative fitness

48 h単一点は使用しない。

評価時点:

```text
6 h
12 h
18 h
24 h
```

各時点で:

```text
P_t = phototroph lineage population
A_t = ancestor lineage population
```

P_t > 0かつA_t > 0の場合のみ:

```text
L_t = ln(P_t / A_t)
```

を計算する。

各runで `L_t` をtimeに対して一次回帰し、その傾きを:

```text
s_early_per_day
```

として1日あたりへ換算する。

同じseed / founder frequencyで:

```text
Delta_s_early = s_early_A1 - s_early_A0
```

を比較する。

### ルール

- primary endpointにpseudocountを使用しない
- lineage extinction後のlog-ratioを人工的に有限化しない
- 有効な時点が3点未満なら `s_early = NA`
- NA runはmedianへ強制代入せず、lineage extinction結果として別報告
- n=3なのでp値を主判定にしない
- median、seedごとの符号、raw trajectoryをそのまま報告する

---

# 6. Ecological rescue endpoint

relative fitnessとは分離する。

各runで:

```text
phototroph lineage extinction time
ancestor lineage extinction time
total population extinction time
survival at 120 h
population N(t)
population AUC
lineage-specific births
lineage-specific deaths
starvation deaths
```

を保存する。

A1では特に:

```text
0% founder control
vs
1 / 10 / 50% seeded arm
```

でtotal population survivalを比較する。

「ancestorが死んだため比が上がる」と「phototroph自身が増える」を分けて解釈する。

---

# 7. Mechanism diagnostics

最低でも1 physical hour cadenceで:

```text
P_t / A_t
mean matter by lineage
mean stored Energy by lineage
H2 uptake per capita by lineage
maintenance expenditure by lineage
photo maintenance offset
photo_incident_j_cum
photo_absorbed_j_cum
photo_usable_max_j_cum
photo_used_j_cum
photo_unused_j_cum
photo_structural_n_mol
births / deaths by lineage
```

を保存する。

またformal artifactへeffective configとinitial founder/genome情報を残し、再現可能性を確保する。

---

# 8. A0 negative controlの読み方

A0ではAttempt 1のような:

```text
P48 = P0 x 16
3 seeds完全一致
ancestor完全不変
```

という決定論的sweepが消えることを確認する。

ただしA0でphototrophとancestorが完全同一になること自体を固定合否基準にはしない。V1.11 physical phototrophyの小さなmaintenance creditは存在するため、差が出ても理論上説明可能なら許容する。

合否の中心は:

1. legacy Energy = 0
2. Energy差がphysical上界内
3. 観測効果量が機構の理論スケールと整合

である。

---

# 9. Interpretation preregistration

## Pattern A — environment-dependent benefit

```text
A0: s_early ~ 0
A1: s_early > A0
A1 seeded arm: survival延長 / rescue
```

なら、primitive phototrophyがH2 interruption環境で選択価値を持つと判断する。

## Pattern B — physical effect too weak

```text
A0: ~0
A1: ~0
rescueなし
```

なら、現行0.015 umol/m2/sではphototrophy効果が小さすぎる。バグではなく効果量問題として次のphoton flux calibrationへ進む。

## Pattern C — A0でも明確なadvantage

legacy routeが0かつEnergy上界testをPASSした上でA0 advantageが再現するなら、初めてphysical phototrophyのgeneral advantageとして扱う。その場合に限りbenefit / cost balanceを検討する。

## Pattern D — unexplained Energy / synchronized sweep

Energy上界違反、複数seed完全一致、2^n同期増殖等が再発した場合はformal resultを解釈せず、再度mechanism auditへ戻る。

---

# 10. Attempt 2後の方針

Attempt 2でPattern AまたはBが得られた場合、次の候補はphoton flux calibration。

第一候補水準:

```text
0.015
0.05
0.15
0.5
1.5
umol/m2/s
```

原則:

- 最初に環境側parameterであるphoton fluxだけを1軸で振る
- `radiant_to_usable_eff` やstructural N costは同時に動かさない
- 目的は「A1でrescue / selectionが出始める最低光量」を探すこと
- Attempt 2の結果を見てから正式Exp21としてpreregisterする

---

# 11. 異常結果checklist

formal analysis前に必ず確認する。

```text
[ ] seed間分散が不自然に0ではないか
[ ] population増加が2^nの完全整数倍ではないか
[ ] 観測Energy差がphysical mechanismの理論上限内か
[ ] endpointがlineage extinction後のpseudocountに支配されていないか
[ ] relative指標とabsolute population trajectoryの両方を見たか
```

---

# 12. 実行順

```text
1. legacy light route修正
2. production-step regression tests追加
3. preflight G1-G6 PASS
4. Exp20 Attempt 2 formal 24 run
5. aggregate / raw trajectory確認
6. Attempt 2考察
7. 必要ならphoton flux calibrationをExp21としてpreregister
```

**Attempt 2結果を見る前にphototrophy efficiency / N costを弱体化しない。**
