# Exp15 V1.9 実験計画案

更新: 2026-09-04
状態: **DESIGN SKELETON / PHYSICAL SCALING GATE PENDING / DO NOT DISPATCH**

この文書はV1.9後に行う最初の科学検証Exp15の骨格を固定する。
旧 `docs/Exp15_実験計画確定.md` はV1.8時代の計画であり **SUPERSEDED / DO NOT DISPATCH**。

重要:

> PR #67でV1.9の機構実装はできたが、旧arbitrary-unit referenceではfixed iLUCAがresource-rich条件でも恒常的Energy赤字となった。したがってExp15は一旦PAUSEし、`docs/V1.9_物理スケール再校正方針.md` のphysical sanity gate完了後に再開する。

Exp15の科学目的・Phase A/B/C構造は維持する。
run duration、seed数、正式判定基準はphysical scaling後に**秒・時間・世代数**を基準に確定する。

---

# 1. Exp15の位置づけ

Exp15はphototrophy創発実験ではない。

> **物理スケールへ再校正されたV1.9 chemical-first iLUCAが、H2環境で生物として成立し、新設した進化可能な生理レバーが自然な環境圧への適応に使われるかを検証する。**

V1.9ではEnergy、生理、繁殖、H2空間場、mutation/capability構造を大きく変更したため、最初のformal experimentでphototrophy創発まで混ぜない。

phototrophy structural innovationの科学検証はExp15後の **Exp16候補** とする。

---

# 2. Exp15前のPhase 0 — physical sanity gate

Phase 0はformal experimentではなく、V1.9の尺度が科学的に意味を持つための実装・sanity gate。

必須:

```text
[ ] time unit = second
[ ] standard dt = 10 s
[ ] day/night period = 24 h reference
[ ] iLUCA reference cell size/dry mass defined
[ ] world/grid/effective-depth/voxel physical scale defined
[ ] H2 field = concentration/amount in physical units
[ ] vent source definition -> mol/s derivation complete
[ ] H2 diffusion uses physical D [m^2/s]
[ ] H2 uptake uses per-biomass kinetics [mol/(kgDW s)]
[ ] H2 -> usable Energy uses J-based accounting
[ ] Matter / biomass scale and growth energetics defined
[ ] basal maintenance / movement / repair Energy scales redefined physically
[ ] resource-rich single-iLUCA Energy balance has no unavoidable unit-mismatch deficit
[ ] resource-rich generation-time order is plausible (reference 4–8 h, not hard target)
[ ] dt=5/10/20 s numerical sanity completed
[ ] Energy/Matter/H2 conservation PASS
[ ] same-seed determinism PASS
[ ] full tests / CI PASS
```

Phase 0で「6時間で必ず分裂する」ようparameter fittingしてはいけない。
現実オーダーの供給・uptake・maintenance・growth costを置いた結果として、reference doubling-time orderが著しく不自然でないかを見る。

---

# 3. Exp15の主要問い

## Q1. fixed iLUCA baselineはH2世界で妥当に振る舞うか

見るもの:

- H2を主Energy源として世代交代可能か
- uniform random spawnからH2 halo / vent周辺へ空間分布が形成されるか
- temporal chemical sensing / chemotaxisが実際に意味を持つか
- H2 uptake / conversion / expenditure / growth / reproductionが物理台帳上整合するか
- runwayとstarvation responseが設計通り働くか
- 特定の初期配置や環境緩和を与えなくても成立するか

fixed iLUCAが絶滅しても、それだけでenvironment FAILとは判定しない。
ただし**resource-rich単独個体でも全遺伝的レバーに関係なく必ず赤字**なら、adaptive pressureではなくscale/model不整合を先に疑う。

## Q2. evolution ONでadaptive rescue / strategy evolutionが起きるか

V1.9で追加した3形質:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

を進化可能にしたとき、固定祖先より生存・世代交代・長期安定性が改善するかを見る。

```text
fixed ancestor -> collapse / fragile
3-gene evolution ON -> persistence / stabilization
```

となる場合、それは失敗ではなく「環境が適応を要求し、進化が応答した」結果として扱う。

## Q3. 適応にどの形質が寄与したか

必要に応じて3形質を単独解禁し、adaptive rescue / equilibrium shiftへの寄与を切り分ける。

---

# 4. 共通世界

physical scaling完了後のV1.9 baselineを使用する。

```text
chemical-first iLUCA
PHOTOTROPHY = OFF
PREDATION   = OFF
light_absorption = 0
predation_efficiency = 0
H2 explicit / CO2 implicit
multiple equal-source fixed vents
vent overlapなし / edge clippingなし
H2 physical diffusion halo
uniform random initial spawn
V1.8 day/night mechanism保持
physical time unit = seconds
standard dt = 10 s
24 h light cycle reference
```

初期iLUCAはlight routeを持たないため、day/nightは初期baselineの主要Energy圧にならない。

H2 source strength、diffusion、uptake、Energy yield、maintenance等は、**旧arbitrary implementation referenceではなくphysical scaling正本値**を使う。

生存させる目的だけでformal直前にenvironment parameterを調整してはいけない。

---

# 5. Phase A — fixed iLUCA baseline

## 5.1 目的

physical V1.9 iLUCAとH2 spatial ecologyが科学検証へ進める状態か確認する。

## 5.2 evolution

全continuous genes固定。
capability innovationも停止。

```text
storage_capacity      fixed
starvation_horizon    fixed
reproduction_horizon  fixed
その他continuous genes fixed
PHOTOTROPHY innovation OFF
PREDATION locked
```

## 5.3 主要観測

人口・世代:

- population trajectory
- extinction / persistence
- births / deaths / death cause
- max / median generation
- generation到達時間 [h]
- realized doubling/generation intervals [h]

Energy physiology:

- Energy [J]
- power income / expenditure [W]
- E/E_max
- runway [s/min/h]
- starvation state / metabolic_factor / uptake_factor
- full-activity expenditure reference [W]
- realized maintenance / repair / movement power
- reproduction events / post-division Energy

H2 ecology:

- H2 concentration distribution [mol/m^3 or mM]
- total H2 amount [mol]
- vent/source influx [mol/s]
- environmental loss [mol/s]
- biological uptake [mol/s]
- H2-derived usable power [W]
- vent-distance-band population
- vent-distance-band H2 uptake
- temporal sensing dQ_chem / turn response
- high-H2 / low-H2 occupancy

conservation:

- Energy ledger residual [J]
- Matter ledger residual
- H2 mol balance

## 5.4 解釈

Aが安定:
- fixed ancestor baseline成立。
- Phase Bでは3形質にどの選択圧が掛かるかを見る。

Aが脆弱 / 絶滅:
- 即environment tuningしない。
- Phase Bで進化的救済可能か確認する。

Aが進化の時間を与えないほど即時collapse:
- physical scale / initial physiology / world geometry / implementationを再監査。

---

# 6. Phase B — 3-gene evolution ON

## 6.1 目的

V1.9で新設した生理レバーが、固定されたphysical environmentで自然選択へ応答できるか検証する。

## 6.2 解禁する遺伝子

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

この3つだけ進化ON。
その他continuous genes固定。
PHOTOTROPHY innovation OFF。
PREDATION locked。

## 6.3 主要readout

- survival / persistence
- population equilibrium / variability
- generation time [h]
- 3 genesのmean / median / quantile / lineage trajectory
- starvation_horizon / reproduction_horizon はseconds/hoursで表示
- trait covariance
- trait shift relative to initial value
- runway distribution [time]
- starvation response使用率
- Energy / H2 utilization efficiency
- vent-distance distribution
- fixed Phase Aとの差

重要比較:

```text
same physical environment
same seed set
fixed iLUCA vs 3-gene evolution ON
```

---

# 7. Phase C — 寄与切り分け

Phase Bで3形質の進化効果が確認された場合のみ必要に応じて実施。

| Arm | storage_capacity | starvation_horizon | reproduction_horizon |
|---|---|---|---|
| C0 | fixed | fixed | fixed |
| C1 | evolve | fixed | fixed |
| C2 | fixed | evolve | fixed |
| C3 | fixed | fixed | evolve |
| C4 | evolve | evolve | evolve |

目的:

- adaptive rescueにどの軸が必要か
- 単独形質で十分か
- 形質間組み合わせが必要か
- trade-off / covarianceが生じるか

---

# 8. Exp15ではやらないこと

- phototrophy innovationの科学検証
- predation解禁
- temperature / oxygen / pH等の新環境因子追加
- vent fluxの時間変動
- H2 source強度の意図的な静的不均一化
- environment parameter最適値探索
- 生存境界の精密探索
- 旧V1.8 Exp15再実行

---

# 9. Exp16への接続

Exp15でchemical-first baselineと進化可能な生理戦略が成立した後、Exp16候補としてphototrophy originを検証する。

```text
PHOTOTROPHY innovation OFF
vs
PHOTOTROPHY innovation ON
```

Exp16で初めて:

```text
chemical-first ancestor
 -> structural innovation
 -> weak phototrophy
 -> quantitative refinement
 -> light/day-night selection pressure
```

を科学的に評価する。

---

# 10. formal実験として未確定のもの

physical scaling + implementation sanity後に確定:

- run duration [physical hours/days + minimum generations]
- seed数
- preflight要否
- persistence / extinction判定窓
- Phase Bのminimum generations
- Phase C実施条件
- Recorder最終項目
- Actions matrix / artifact構成

旧versionの `10k tick / 50k tick` を機械的に流用しない。

---

# 11. dispatch gate

```text
V1.9 mechanism implementation complete
physical scaling decisions S1-S5 complete
physical scaling patch complete
full tests / CI PASS
Energy/Matter/H2 conservation PASS
same-seed determinism PASS
dt numerical sanity PASS
physical mechanical sanity complete
implementation review complete
Exp15 duration / seed / formal判定基準を人間承認
```

それまでは **DO NOT DISPATCH**。
