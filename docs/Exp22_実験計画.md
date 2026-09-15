# Exp22 実験計画 — V1.11 primitive phototrophy photon-flux calibration

更新: 2026-09-15  
状態: **DRAFT FOR REVIEW / 実行前にClaudeレビューを行う**  
対象version: **V1.11**

関連:

- `docs/V1.11_原始Phototrophy_実装仕様_rev2.md`
- `docs/V1.11_選択圧直接測定_実験ロードマップ.md`
- `docs/Exp20_結果考察.md`
- `docs/Exp20_Attempt2_Opus5レビュー.md`
- `docs/Exp21_実験計画.md`

---

# 0. Exp22の位置付け

V1.11はまだ継続する。

Exp20 Attempt 2で既存生理形質のfitness effectを直接測定し、Exp21では `starvation_horizon=1800 s` と `2700 s` の2系統を同一世界で競争させた結果、A2 dynamic ventで2700 s系統の頻度上昇を確認した。

したがって、

> **physical modeでも、環境変化 → 形質依存fitness差 → 系統頻度変化という自然選択が成立する**

ことは確認できた。

ここからV1.11本題のprimitive phototrophyへ戻る。

ただしExp20 Attempt 1はlegacy light経路の混入により無効であり、当時の `0.015 umol m^-2 s^-1` をそのまま正式値として採用してはいけない。

Exp22はphototrophyの競争・進化実験ではなく、

> **どのphoton fluxなら、V1.11 rev2の正しいphysical phototrophy経路で、次段のcompetition assayに使える大きさのfitness-related effectが生じるかを校正するStage-1 paired fitness-effect assay**

とする。

---

# 1. 主質問

Exp22で答えるのは次の3点。

## Q1 — physical phototrophy経路は正しく作動しているか

photon fluxを増やしたとき、

```text
incident light
-> absorbed light
-> usable photo credit
-> actually used maintenance credit
```

が物理上界とledger identityを守りながら増加するか。

## Q2 — どの光量から生理的に意味のある効果が出るか

phototrophy OFFとONを同一seed・同一初期状態で比較し、

```text
stored Energy保護
starvation exposure低下
total living matter / population維持
starvation death低下
```

がどのfluxから観測可能になるか。

## Q3 — 次のcompetition assayへ進める光量域はどこか

弱すぎて検出不能でも、強すぎて一般的な必勝能力になる条件でもなく、

> **現実的なseed数・run時間でcompetitionとして検出可能な中程度の効果量**

を持つflux域を特定する。

Exp22単体では「phototrophyが進化する」とは結論しない。

---

# 2. 仮説

## H1 — mechanistic monotonicity

photon flux増加に伴い、phototrophy ON群の

```text
photo_incident_j_cum
photo_absorbed_j_cum
photo_usable_max_j_cum
photo_used_j_cum
```

は原則として単調非減少する。

## H2 — Energy protection

phototrophy ONではOFFよりstored Energyが保護される。

効果は低fluxでは微小、高fluxほど大きくなる。

## H3 — dynamic-environment rescue

A2_DYNAMIC_VENTでは48 hのvent turnover後にH2供給条件が変わるため、phototrophyによるmaintenance補助が

```text
starvation exposure
starvation death
population / total living matter
```

へ現れやすい。

A0_STATICでは主としてEnergy温存効果として現れ、A2より生存上の差は小さいことを期待する。

## H4 — zero-light cost control

flux=0でphototrophy ONに利益はない。

一方、phototrophy apparatusのstructural N costが実際に効けば、ON群はOFF群と同等またはわずかに不利になり得る。

これは正常なtrade-offとして扱う。

---

# 3. Exp22開始前のMUST-FIX / preflight gate

以下はformal runより先に通す。1つでも失敗した場合、Exp22本計算を開始しない。

## G0 — legacy `_absorb_light()` Energy経路をphysical modeから排除

Exp20 Attempt 1を無効化した旧light Energy流入をphysical modeで完全に止める。

formal physical runでは:

```text
legacy light flow = 0
```

を必須とする。

旧arbitrary modeの後方互換性は維持する。

## G1 — production `Simulation.step()` test

実際の `Simulation.step()` を通してphototrophy ON/OFFを比較する。

独立計算したphysical上界に対して:

```text
0 <= photo_used
photo_used <= photo_usable_max
photo_usable_max <= photo_absorbed
photo_absorbed <= photo_incident
```

を全tick/累積で満たすこと。

旧light経路由来Energyが混入していないことも同時にassertする。

## G2 — effective config一致

実際にrunへ渡された `effective_config.json` と本書の条件表をfield単位で比較する。

特に:

```text
physical_mode = True
physical_light_enabled = True
light_cycle_enabled = False
light_physical_pattern = uniform
phototrophy innovation/loss = 0
continuous mutation = OFF
```

を必ず確認する。

## G3 — light-only growth禁止

H2=0、light>0の短いmechanical controlで、phototrophyがmaintenanceを補助しても、light単独で持続的なnet biomass growth / reproductionを作らないことを確認する。

これはV1.11 rev2 HARD RULE P3の回帰テストとする。

## G4 — structural N ledger

phototrophy apparatus assembly/releaseを含めてもN ledgerが既存許容誤差内で閉じること。

## G5 — t=0 paired-state一致

同一environment / seed / fluxのOFF・ON pairについて、開始時点で以下を一致させる。

```text
organism position / orientation
matter
absolute stored Energy
damage
H2 field
DIC / fixed N / phosphate fields
RNG state
対象外genes
```

許容する差は:

```text
phototrophy capability
light_absorption (OFF=0 / ON=0.01)
```

のみ。

`photo_structural_n_mol` は両者とも0から開始し、ON群だけがrun開始後に環境fixed-Nからassemblyする。

---

# 4. light cycleの扱い

Exp22はfluxそのものの1軸校正が目的なので:

```text
light_cycle_enabled = False
```

とし、24 h常時一定のuniform photon fluxを与える。

これにより既知のdaylight coupling問題をExp22のflux calibrationから切り離す。

**これは「V1.11では夜間も光合成する」という仕様決定ではない。**

昼夜cycleを使うformal ecological experimentへ進む前に、physical phototrophy経路へ `daylight_factor` を接続するかを別途明示的に決定する。

---

# 5. phototrophy phenotype

V1.11 rev2のprimitive phenotypeを固定する。

```text
phototrophy capability OFF:
    light_absorption = 0

phototrophy capability ON:
    light_absorption = 0.01
    phototrophy_seed_absorption = 0.01
```

mapping:

```text
absorptance = 1 - exp(-0.01) ~= 0.995%
```

その他のphototrophy parameterはrev2正本を固定使用する。

```text
light_effective_wavelength_nm = 800
phototrophy_radiant_to_usable_eff = 0.10
photo_apparatus_n_multiplier = 10
bchl_extinction_mM_cm = 213
```

Exp22中に結果を見てこれらを調整しない。

---

# 6. photon flux水準

事前固定:

```text
0
0.015
0.05
0.15
0.5
1.5
umol photons m^-2 s^-1
```

意味:

- `0`: negative control + structural costのみを見る
- `0.015`: rev2 original working reference
- `0.05 / 0.15`: low-to-moderate calibration
- `0.5 / 1.5`: positive-control寄りの高flux

結果を見て途中で水準を追加・削除しない。

この範囲にcompetitionへ進める条件が存在しない場合、Exp22は「working flux未決定」として終了し、次の別preregistered sensitivityで範囲を拡張する。

---

# 7. 環境

Exp20/21で使用した既存環境をそのまま利用し、環境側を再調整しない。

## A0_STATIC

```text
H2 vent static
vent turnover OFF
```

phototrophyの平常時Energy温存効果を見る基準環境。

## A2_DYNAMIC_VENT

```text
H2 vent turnover ON
turnover interval = 48 h
```

Exp21で実際に形質依存の自然選択を発生させた環境。

72 h runとすることで:

```text
0-48 h  : turnover前
48-72 h : 最初のvent移動後
```

を同一runで観測する。

H2 source calibration、C/N/P条件、world geometry等はExp21/Exp18由来のformal値を再利用し、Exp22結果に合わせてretuneしない。

---

# 8. paired run設計

各 `environment × seed × photon flux` について、必ず同じfluxで2 runを作る。

```text
Run OFF: phototrophy capability OFF
Run ON : phototrophy capability ON, light_absorption=0.01
```

**OFF runにも同じphysical photon fluxを設定する。**

「OFFなら光を利用できないから同じはず」と仮定してbaselineを別fluxから使い回さない。

これにより各pairの外部環境差をphototrophy capabilityだけに限定する。

common-random-number paired runとして同一seed・同一初期配置を使うが、run分岐後までRNG差が0とは仮定しない。

---

# 9. seed / run数 / duration

seedはExp22専用番号帯として事前固定する。

```text
22001
22002
22003
```

Stage-1 calibrationであり、連続量のpaired effectとflux-responseを測ることが目的なので3 seedとする。

formal run総数:

```text
2 environments
x 6 flux levels
x 3 seeds
x 2 capability states (OFF / ON)
= 72 runs
```

run条件:

```text
duration = 72 physical h
dt = 10 s
sample cadence = 600 s
initial population = 100
continuous mutation = OFF
phototrophy innovation = 0
phototrophy loss = 0
predation innovation = OFF
```

GitHub Actionsでは `environment × seed` を1 jobとし、各job内で6 flux × OFF/ONを順に実行する構成を推奨する。

6 jobsを並列化できる。

---

# 10. 保存するreadout

各runについて最低限:

```text
time
population
total living matter
mean matter
mean stored Energy
mean starvation state
starvation-exposed fraction
births cumulative
deaths cumulative
starvation deaths cumulative
H2 biological uptake cumulative
C/N/P uptake / ledger closure
vent turnover count
```

phototrophy diagnostics:

```text
photo_incident_j_cum
photo_absorbed_j_cum
photo_usable_max_j_cum
photo_used_j_cum
photo_unused_j_cum
photo_conversion_loss_j_cum
photo_structural_n_mol (population total / mean)
photo_n_assembly_cum
photo_n_released_cum
legacy light flow
```

---

# 11. paired effect指標

平均matter単独はsurvivor biasを持つためprimaryにはしない。

## 11.1 Primary continuous readout — stored Energy protection

各pairで:

```text
R_E(window)
= integral(E_ON - E_OFF) dt / integral(E_OFF) dt
```

を計算する。

window:

```text
0-48 h
48-72 h
0-72 h
```

特にA2の `48-72 h` をvent turnover後の主要calibration windowとして扱う。

## 11.2 Primary stress readout — starvation exposure

```text
Delta starvation_exposure_AUC
= integral(frac_ON - frac_OFF) dt
```

負値ほどphototrophyが飢餓状態を減らしたことを示す。

A2では48-72 hを重点評価する。

## 11.3 Ecological secondary readout

```text
relative delta final total living matter
Delta population
Delta births
Delta deaths
Delta starvation deaths
first-birth timing
```

population差や死亡差が0でも、continuous primary readoutでflux-responseを評価できるようにする。

## 11.4 Mechanistic readout

各fluxで:

```text
photo_used_j_cum
photo_used / photo_usable_max
structural N investment
H2 uptake difference
```

を確認し、「何が効いて差が出たか」を説明可能にする。

---

# 12. flux-responseの事前評価ルール

Exp22はbiologyのPASS/FAIL実験ではなくcalibrationなので、結果を一つのp値で合否判定しない。

ただし後から都合のよいfluxを選ぶことを避けるため、competition候補の抽出ルールを先に固定する。

## 12.1 preferred working-flux candidate

非zero fluxのうち、低い方から見て最初に以下を全て満たすfluxを **preferred candidate** とする。

1. 全ledger / G0-G5 gate PASS
2. A2の `R_E(48-72h)` が3/3 seedで正
3. A2の `median R_E(48-72h) >= +1%`
4. A2で `Delta starvation_exposure_AUC(48-72h) <= 0` が3/3 seed
5. A0 / A2ともmax population halt等の人工停止条件へ到達しない

`+1%` は「competitionへ進める前に最低限ほしいcontinuous effect」のworking thresholdであり、生物学的普遍値ではない。Claudeレビューでこの閾値の妥当性を重点確認する。

## 12.2 general-advantage flag

preferred candidateについて、A0でも72 h時点で

```text
median relative delta total living matter >= +10%
```

なら `GENERAL_ADVANTAGE_FLAG` を付ける。

これは即失格ではないが、「dynamic環境特有の適応」ではなく常時強い能力である可能性を次段competition設計で明示する。

## 12.3 candidateなしの場合

6水準のどれも12.1を満たさない場合:

```text
NO_WORKING_FLUX_IN_RANGE
```

として終了する。

結果を見た後に同じExp22内でfluxを追加しない。

---

# 13. aggregate出力

aggregate artifactには最低限以下を含める。

```text
exp22_pair_results.csv
exp22_flux_response.csv
exp22_seed_summary.csv
exp22_gate_summary.json
exp22_working_flux_recommendation.json
```

`exp22_flux_response.csv` は各environment × fluxについて:

```text
median / min / max R_E
median / min / max starvation-exposure effect
final total-living-matter effect
population/birth/death effect
photo_used_j
photo utilization fraction
structural N investment
```

を3 seedでまとめる。

formal completeness gateとして72/72 runが揃わない場合はaggregate成功扱いにしない。

---

# 14. Exp22で主張してよいこと / いけないこと

## 主張してよい

```text
- physical phototrophy経路がledger上正しく動作した
- photon fluxに対するmechanistic/fitness-related effect curve
- どのflux域が次のcompetition検証に適するか
- A0とA2で効果の現れ方がどの程度違うか
```

## まだ主張しない

```text
- phototrophyが自然選択で増える
- phototrophyが進化的に固定する
- primitive Earthで実際にこのfluxだった
- spatial phototrophic nicheが成立した
- day/night cycle下での適応性
```

これらは後段実験の問いとする。

---

# 15. Exp22後の分岐

## working fluxが得られた場合

次段（仮Exp23）:

> **phototrophy OFF vs ONの同一世界competition / rescue assay**

候補設計:

```text
A0_STATIC vs A2_DYNAMIC_VENT
50:50 initial lineage ratio
selected photon flux
120 h
multiple seeds
mutation / innovation / loss OFF
```

Exp21と同じStage-2 competition方式で、実際のlineage frequency変化を測る。

## working fluxが得られない場合

competitionへ進まず、Exp22結果に基づき別番号のflux-range sensitivityを事前登録する。

---

# 16. Claudeレビューで重点的に確認してほしい点

1. **G0 legacy `_absorb_light()` 排除方法が十分か**
2. production-step physical upper-bound testに抜けがないか
3. OFF/ON pairをfluxごとに別runする設計が妥当か
4. flux水準 `0 / 0.015 / 0.05 / 0.15 / 0.5 / 1.5` の範囲が適切か
5. Stage-1 calibrationとして3 seed / 72 hが十分か
6. primaryを `R_E(48-72h)` とstarvation exposure AUCにすることが妥当か
7. preferred candidateの `median R_E >= +1%` 閾値が妥当か
8. structural N costを含んだON/OFF比較で初期条件の公平性が保たれているか
9. `light_cycle_enabled=False` としてdaylight couplingを後段へ分離する判断が妥当か
10. Exp23 competitionへ進む前に追加すべきmechanical gateがないか

---

# 17. 実行順

```text
1. Claudeレビュー
2. レビュー指摘を計画へ反映
3. G0-G5に必要なproduction code / tests修正
4. Exp22 harness + workflow実装
5. preflightのみ実行
6. preflight全PASSを確認
7. 72 formal runs実行
8. aggregate
9. flux-response考察
10. working fluxが得られた場合のみphototrophy competitionへ進む
```
