# Exp15 V1.9 実験計画案

更新: 2026-09-04
状態: **DESIGN SKELETON / V1.9実装後に最終化 / DO NOT DISPATCH YET**

この文書は、V1.9実装後に行う最初の科学検証 Exp15 の骨格を固定する。
旧 `docs/Exp15_実験計画確定.md` はV1.8時代の計画であり **SUPERSEDED / DO NOT DISPATCH**。

V1.9実装・test・保存則・決定性・mechanical sanity・人間レビューが完了するまでは、本計画をformal dispatchしてはいけない。

tick数、seed数、formal合否閾値はV1.9実装後のmechanical sanityを見て確定する。

---

# 1. Exp15の位置づけ

Exp15はphototrophy創発実験ではない。

> **V1.9で再設計したchemical-first iLUCAが、H2環境で生物として成立し、追加した進化可能な生理レバーが自然な環境圧への適応に実際に使われるかを検証する。**

V1.9ではEnergy、生理、繁殖、H2空間場、mutation/capability構造を同時に大きく変更するため、最初のformal experimentでphototrophy創発まで混ぜない。

phototrophy structural innovationの科学検証は、Exp15でchemical-first baselineを確認した後の **Exp16候補** とする。

---

# 2. Exp15の主要問い

Exp15で答える問いは3つ。

## Q1. fixed iLUCA baselineはH2世界で妥当に振る舞うか

見るもの:

- H2を主Energy源として世代交代可能か
- random spawnからH2 halo / vent周辺へ空間分布が形成されるか
- temporal chemical sensing / chemotaxisが実際に意味を持つか
- H2 uptake / conversion / expenditure / reproductionが台帳上整合するか
- runwayとstarvation responseが設計通り働くか
- 特定の初期配置や環境緩和を与えなくても成立するか

fixed iLUCAが絶滅しても、それだけでenvironment FAILとは判定しない。

## Q2. evolution ONでadaptive rescue / strategy evolutionが起きるか

V1.9で追加した3形質:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

を進化可能にしたとき、固定祖先より生存・世代交代・長期安定性が改善するかを見る。

特に:

```text
fixed ancestor -> collapse / fragile
3-gene evolution ON -> persistence / stabilization
```

となる場合、それは失敗ではなく「環境が適応を要求し、進化が応答した」結果として扱う。

## Q3. 適応にどの形質が寄与したか

必要に応じて3形質を単独で解禁し、adaptive rescue / equilibrium shiftへの寄与を切り分ける。

---

# 3. 共通世界

V1.9 FINAL baselineを変更せず使用する。

```text
chemical-first iLUCA
PHOTOTROPHY = OFF
PREDATION   = OFF
light_absorption = 0
predation_efficiency = 0
H2 explicit / CO2 implicit
4 vent
全vent同一総flux
固定位置
非重複
edge clippingなし
H2 diffusion haloあり
uniform random initial spawn
V1.8 day/night mechanismは保持
```

初期iLUCAはlight routeを持たないため、day/nightは初期baselineの主要Energy圧にはならない。

H2 source flux、diffusion、loss、uptake、conversion、Energy physiologyなどはV1.9実装referenceをまず用いる。
生存させる目的だけでformal直前にenvironment parameterを調整してはいけない。

---

# 4. Phase A — fixed iLUCA baseline

## 4.1 目的

新しいV1.9 iLUCAそのものと、H2 spatial ecologyが科学検証へ進める最低限の状態か確認する。

## 4.2 evolution

原則として全continuous genes固定。
capability innovationも停止。

```text
storage_capacity      fixed
starvation_horizon    fixed
reproduction_horizon  fixed
その他continuous genes fixed
PHOTOTROPHY innovation OFF
PREDATION locked
```

## 4.3 主要観測

人口・世代:

- population trajectory
- extinction / persistence
- births / deaths / death cause
- max / median generation
- generation到達tick

Energy physiology:

- mean / quantile Energy
- E/E_max
- runway distribution
- starvation state / metabolic_factor / uptake_factor
- full-activity expenditure reference
- realized maintenance / repair / movement expenditure
- reproduction events / post-division Energy

H2 ecology:

- total H2 stock
- source influx
- environmental loss
- biological uptake
- conversion loss
- H2 concentration distribution
- vent-distance-band population
- vent-distance-band H2 uptake
- temporal sensing dQ_chem / turn response
- high-H2 / low-H2 occupancy

conservation:

- Energy ledger residual
- Matter ledger residual
- H2 mass / energy-equivalent accounting

## 4.4 解釈

Aが安定:
- V1.9 fixed ancestor baselineは成立。
- Phase Bでは「救済」ではなく、3形質にどの選択圧が掛かるかを見る。

Aが脆弱 / 絶滅:
- 即environment tuningしない。
- Phase B evolution ONで救済されるか確認する。

Aが初期数十tickで全seed即死など、進化が働く世代時間すら与えない:
- mechanism / initial physiology / implementation referenceの再監査対象。
- 生存のための盲目的parameter sweepには進まない。

---

# 5. Phase B — 3-gene evolution ON

## 5.1 目的

V1.9で新設した生理レバーが、固定環境下で自然選択へ実際に応答できるか検証する。

## 5.2 解禁する遺伝子

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

この3つだけを進化ON。
その他のcontinuous genesは固定する。

PHOTOTROPHY innovationはOFF。
PREDATIONはlocked。

これにより、結果をV1.9で新設した生理戦略へ帰属しやすくする。

## 5.3 主要readout

- survival / persistence
- population equilibrium / variability
- generation rate
- 3 genesのmean / median / quantile / lineage trajectory
- trait covariance
- trait shift relative to initial value
- runway distribution
- starvation response使用率
- Energy / H2 utilization efficiency
- vent-distance distribution
- fixed Phase Aとの差

重要な比較:

```text
same environment
same seed set
fixed iLUCA vs 3-gene evolution ON
```

## 5.4 成功の意味

Exp15の成功は「必ず人口が増える」ことではない。

以下のいずれかが得られれば科学的に有益:

- fixedよりevolution ONが明確に長く持続 / 安定
- 3形質が再現性のある方向へ変化
- H2空間利用やrunway分布が変化
- 生存率は同じでも繁殖・貯蔵・飢餓応答戦略が分化

逆に3形質が全く動かない場合は、選択圧不足・mutation scale・形質がfitnessへ接続されていない可能性を疑う。

---

# 6. Phase C — 寄与切り分け

Phase Bで3形質の進化効果が確認された場合、必要に応じて実施する。

候補arm:

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
- 形質間の組み合わせが必要か
- trade-off / covarianceが生じるか

Phase Cは自動的に必須としない。
Phase A/Bの結果で情報価値がある場合のみformal化する。

---

# 7. Exp15ではやらないこと

- phototrophy innovationの科学検証
- predation解禁
- temperature / oxygen / pH等の新環境因子追加
- vent fluxの時間変動
- H2 source強度の不均一化
- environment parameter最適値探索
- 生存境界の精密探索
- V1.8の旧Exp15再実行

原則:

> Exp15はV1.9 chemical-first baselineとadaptive physiologyを検証する。
> 新しい大きな進化innovationは混ぜない。

---

# 8. Exp16への接続

Exp15でchemical-first baselineと進化可能な生理戦略が成立した後、Exp16候補としてphototrophy originを検証する。

基本比較候補:

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

Exp15とExp16を分離することで、iLUCA生理の成立と新能力創発を混同しない。

---

# 9. 未確定事項

V1.9実装後のmechanical sanity / 人間レビュー後に確定する。

- formal tick数
- seed数
- preflight要否
- persistence / extinctionの正式判定窓
- Phase Bで必要な最小世代数
- Phase Cを実施する条件
- recorderの最終項目
- Actions matrix / artifact構成

これらをV1.9実装前に固定しない理由:

> V1.9でEnergy時間スケール・H2空間場・繁殖時間スケールが変わるため、旧versionの10k/50k tick等を機械的に流用すると実験時間窓の意味が変わる。

---

# 10. dispatch gate

Exp15 formal dispatch前に必須:

```text
V1.9 implementation complete
full tests PASS
Energy/Matter/H2 conservation PASS
same-seed determinism PASS
mechanical sanity complete
implementation review complete
Exp15 tick/seed/判定基準を人間承認
```

それまでは **DO NOT DISPATCH**。
