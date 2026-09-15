# Exp22 実験計画 — V1.11 primitive phototrophy photon-flux calibration

更新: 2026-09-15  
状態: **REVIEWED / READY FOR IMPLEMENTATION**  
対象version: **V1.11**

関連:

- `docs/V1.11_原始Phototrophy_実装仕様_rev2.md`
- `docs/V1.11_選択圧直接測定_実験ロードマップ.md`
- `docs/Exp20_結果考察.md`
- `docs/Exp20_Attempt2_Opus5レビュー.md`
- `docs/Exp21_実験計画.md`
- `docs/Exp21_結果考察.md`
- `docs/Exp21_Exp22_Opus5レビュー.md`
- Issue #75

---

# 0. Exp22の位置付け

V1.11を継続する。

Exp20 Attempt 2で既存生理形質のfitness-related effectを直接測定し、Exp21ではstanding variationとして置いた2 lineageを同一世界で競争させ、A2 dynamic ventでlineage frequency変化を確認した。

したがって、

> **physical modeでstanding variationに対して自然選択が働くこと**

は確認できた。

一方、突然変異から機能形質が生成され、短いrun内で選択されることは未確認である。

ここからV1.11本題のprimitive phototrophyへ戻る。

Exp20 Attempt 1はlegacy light経路混入により無効であり、当時の `0.015 umol photons m^-2 s^-1` を正式値として採用しない。

Exp22は競争・進化実験ではなく、

> **正しいphysical phototrophy経路について、photon fluxとmechanistic / fitness-related effectの関係を校正し、次段competition assayを現実的なseed数で設計できるfluxを選ぶStage-1 assay**

とする。

---

# 1. 主質問

## Q1 — physical phototrophy経路は正しく作動しているか

```text
incident light
-> absorbed light
-> usable photo credit
-> actually used maintenance credit
```

が独立した物理上界とledger identityを守りながらfluxに応じて増えるか。

## Q2 — 光Energyが生態的効果へどう変換されるか

phototrophy OFF / ONを同一seed・同一初期状態でpaired比較し、

```text
A2: stored Energy保護 / starvation exposure / death / population
A0: growth / total living matter
```

へどの程度翻訳されるかを見る。

## Q3 — 次のcompetition assayを現実的な検出力で実行できるか

R_Eだけで候補を選ばず、人口統計効果から**Exp23に必要なseed数を事前推定**する。

Exp22単体では「phototrophyが自然選択で増える」とは結論しない。

---

# 2. 仮説と主張範囲

## H1 — mechanistic monotonicity

photon flux増加に伴いON群の

```text
photo_incident_j_cum
photo_absorbed_j_cum
photo_usable_max_j_cum
photo_used_j_cum
```

は原則として単調非減少する。

## H2 — A2 Energy protection

A2ではphototrophy ONにより、vent turnover後のstored Energy低下・starvation exposureが緩和される。

## H3 — demographic rescue

十分なfluxではA2で

```text
starvation death低下
population維持
total living matter維持
```

へ効果が波及する。

## H4 — near-zero-light control

`1e-6 umol photons m^-2 s^-1` では、理論上phototrophy benefitは実質0であり、ON/OFFの光Energy効果は検出不能水準になる。

### structural N costについて

Issue #75の検算では、現行50x CNP stockに対してphototrophy apparatusのstructural N要求は小さすぎる。

```text
apparatus structural N / organism biomass N ~= 0.565%
初期100個体のapparatus N / environmental fixed N ~= 0.0113%
```

したがって**Exp22は実質的にbenefit側の校正であり、N costとのtrade-off検証ではない。**

Exp22で得るworking fluxは、N costが非律速な条件での値であり、trade-off検証は将来のN-limited条件（例: Exp17由来10x/30x stock）を用いた別実験へ分離する。

---

# 3. Exp22開始前のMUST-FIX / preflight gate

1つでも失敗した場合、formal runを開始しない。

## G0 — legacy `_absorb_light()` Energy経路をphysical modeから排除

physical modeではlegacy light Energy流入を完全に0とする。

旧arbitrary modeの後方互換性は維持する。

## G1 — production `Simulation.step()` physical upper-bound test

実際の `Simulation.step()` を通して:

```text
0 <= photo_used
photo_used <= photo_usable_max
photo_usable_max <= photo_absorbed
photo_absorbed <= photo_incident
```

を全tick / 累積で満たす。

さらに、V1.11内部counter同士の比較だけでは第2のEnergy入口を検出できないため、**機構非依存の上界**を追加する。

ON/OFFの短いpaired testについて、configとgeometryから独立計算した上界を使い:

```text
DeltaE_ON - DeltaE_OFF
<= independent_physical_usable_light_upper_bound
 + abs(maintenance_difference)
 + tolerance
```

をassertする。

独立上界のabsorptanceはN制限後の値ではなく:

```text
1 - exp(-light_absorption)
```

を使用する。

## G2 — effective config一致

`effective_config.json` と本書をfield単位で照合する。

必須:

```text
physical_mode = True
physical_light_enabled = True
light_cycle_enabled = False
light_physical_pattern = uniform
phototrophy innovation = 0
phototrophy loss = 0
continuous mutation = OFF
```

flux値も各runについて事前登録値と完全一致させる。

## G3 — light-only growth禁止

H2=0 / light>0の短いcontrolで、光がmaintenanceを補助してもlight単独で持続的net biomass growth / reproductionを作らないことを確認する。

## G4 — structural N ledger

apparatus assembly / releaseを含めてN ledgerが既存許容誤差内で閉じること。

## G5 — t=0 paired-state一致

同一environment / seed / fluxのOFF・ON pairで、開始時点の外生条件を一致させる。

一致対象:

```text
position / orientation
matter
absolute stored Energy
damage
H2 field
DIC / fixed N / phosphate fields
RNG state
対象外genes
```

許容差:

```text
phototrophy capability
light_absorption (OFF=0 / ON=0.01)
```

`photo_structural_n_mol` は両群0から開始し、ONだけrun開始後にenvironment fixed-Nからassemblyする。

## G6 — legacy parameter independence property test

physical modeでlegacy parameter

```text
light_max
light_uptake_coef
```

を大きく変更しても、physical phototrophyのEnergy trajectory / resultが変化しないことをproperty testで確認する。

## G7 — competition power handoff

formal aggregate時に、各fluxの人口統計効果から**Exp23必要seed数の見積もり**を必ず生成する。

G7はpreflightではなくExp22完了条件である。

---

# 4. light cycleの扱い

Exp22では:

```text
light_cycle_enabled = False
```

とし、24 h一定のuniform photon fluxを与える。

重要な実装事実として、**現状のphysical phototrophy経路 `physical_light_incident_power_w()` は `daylight_factor` を参照していない。**

したがって現時点では `light_cycle_enabled` の値にかかわらずV1.11 physical光路は昼夜cycleの影響を受けない。

Exp22でFalseとするのは、この状態をconfig上も明示して1軸flux calibrationに限定するためである。

昼夜cycleを使うformal ecological experimentへ進む前に、この未接続問題を別途解決する。

---

# 5. phototrophy phenotype

ON phenotypeを固定する。

```text
OFF:
  light_absorption = 0

ON:
  light_absorption = 0.01
  phototrophy_seed_absorption = 0.01
```

mapping:

```text
absorptance = 1 - exp(-0.01) ~= 0.995%
```

固定parameter:

```text
light_effective_wavelength_nm = 800
phototrophy_radiant_to_usable_eff = 0.10
photo_apparatus_n_multiplier = 10
bchl_extinction_mM_cm = 213
```

Exp22中に結果を見て変更しない。

---

# 6. photon flux水準

事前固定:

```text
0.000001
0.015
0.05
0.15
0.5
1.5
umol photons m^-2 s^-1
```

`0` はConfig validationを通らないため使用しない。`1e-6` を**実質zero-light control**とする。

意味:

- `1e-6`: near-zero benefit control
- `0.015`: rev2 original reference
- `0.05 / 0.15`: low-to-moderate calibration
- `0.5 / 1.5`: positive-control寄り高flux

結果を見て同じExp22内で水準を追加・削除しない。

---

# 7. 理論効果量の事前予測

ON phenotype `light_absorption=0.01`、absorptance約0.995%、maintenance `P_full ~= 0.4327 fW` に対し、理論上のusable light / maintenance比は概ね以下。

| photon flux (umol m^-2 s^-1) | expected usable / maintenance | 事前解釈 |
|---:|---:|---|
| 0.000001 | ~0.000026% | 実質0 |
| 0.015 | ~0.39% | +1%閾値未満予測 |
| 0.05 | ~1.31% | mechanistic候補の最有力 |
| 0.15 | ~3.93% | 0.05が実測閾値を外した場合の次候補 |
| 0.5 | ~13.09% | 強いpositive control |
| 1.5 | ~39.28% | 支配的効果寄り |

この表は**実測結果に合わせて変更しない事前予測**である。

実測mechanistic countersが大きく逸脱した場合、biologyではなくimplementation / ledger問題を優先して疑う。

また、0.05が +1% criterionを満たさなくてもcriterionを下げない。事前ルール通り次の0.15を評価する。

---

# 8. 環境

## A0_STATIC

```text
H2 vent static
vent turnover OFF
```

A0では個体がprotective reserve付近へ張り付くため、phototrophy効果はstored Energyより**growth / total living matter**に出る可能性が高い。

## A2_DYNAMIC_VENT

```text
H2 vent turnover ON
turnover interval = 48 h
```

72 h run:

```text
0-48 h  : turnover前
48-72 h : 最初のvent移動後
```

A2ではEnergy protection / starvation rescueを主に見る。

H2 source、C/N/P stock、world geometry等は既存formal値を再利用し、結果に合わせてretuneしない。

---

# 9. paired run設計

各 `environment × seed × photon flux` について:

```text
Run OFF: phototrophy capability OFF
Run ON : phototrophy capability ON, light_absorption=0.01
```

**OFF runにもONと同じphysical photon fluxを設定する。**

同一seed・同一初期配置で開始するが、死亡等でrunが分岐した後までRNG系列が一致するとは仮定しない。

---

# 10. seed / run数 / duration

seed:

```text
22001
22002
22003
```

Stage-1 calibrationとして3 seedを維持する。

A2ではrun分岐後にCRN advantageが弱まるため、3/3符号一致は強い統計証拠ではない。**偶然でも3/3一致する確率は12.5%**であることを結果考察へ明記する。

formal run数:

```text
2 environments
x 6 flux levels
x 3 seeds
x 2 capability states
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

GitHub Actionsでは `environment × seed` を1 jobとし、6 jobs並列を基本とする。

---

# 11. 保存するreadout

各run:

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
photo_structural_n_mol
photo_n_assembly_cum
photo_n_released_cum
legacy light flow
```

---

# 12. paired effect指標

平均matter単独はsurvivor biasがあるため単独primaryにしない。

## 12.1 A2 primary — stored Energy protection

```text
R_E(window)
= integral(E_ON - E_OFF) dt / integral(E_OFF) dt
```

window:

```text
0-48 h
48-72 h
0-72 h
```

A2では `48-72 h` を主要calibration windowとする。

## 12.2 A2 stress readout

```text
Delta starvation_exposure_AUC
= integral(frac_ON - frac_OFF) dt
```

負値ほどphototrophyがstarvation exposureを減らす。

加えて:

```text
Delta starvation deaths
Delta deaths
Delta population
```

を必ず保存する。

## 12.3 A0 primary — growth / living matter

A0ではstored Energyへ効果が残らずgrowthへ流れる可能性が高いため:

```text
relative delta total living matter
relative delta mean matter
birth timing / births
```

をprimary ecological readoutとする。

A0のR_Eはmechanistic参考値として扱う。

## 12.4 Mechanistic readout

```text
photo_used_j_cum
photo_used / photo_usable_max
structural N investment
H2 uptake difference
```

を確認する。

---

# 13. Exp23 competition検出力への変換

Exp22のseparate paired runsから、competitionで期待されるlineage差の**粗い人口統計proxy**を作る。

同一seed・同一fluxの72 h final populationを使い:

```text
W_ON  = N_ON_final / N_initial
W_OFF = N_OFF_final / N_initial

f_proxy = W_ON / (W_ON + W_OFF)
Delta_proxy_pt = 100 * (f_proxy - 0.5)
```

これは実際の同一世界competition結果ではなく、**別runの人口増減から作る事前検出力proxy**であることを明記する。

Exp21の実測seedばらつきから competition frequency のSDを約6.2 percentage pointsと置き、2σ相当の目安として:

```text
n_required_est
= ceil((2 * 6.2 / abs(median Delta_proxy_pt))^2)
```

を計算する。

`Delta_proxy_pt ~= 0` の場合は `n_required_est = INF / not estimable` とする。

参考:

```text
Delta = 6.3 pt -> n ~= 4
Delta = 3.0 pt -> n ~= 17
Delta = 2.0 pt -> n ~= 38
Delta = 1.0 pt -> n ~= 154
```

この推定はExp23のpreregistration用であり、Exp22でcompetition効果を証明したことにはしない。

---

# 14. flux-responseの事前評価ルール

## 14.1 mechanistic working flux

非near-zero fluxを低い方から見て、最初に以下を全て満たすfluxを `MECHANISTIC_WORKING_FLUX` とする。

1. G0-G6およびledger gate PASS
2. A2 `R_E(48-72h) > 0` が3/3 seed
3. A2 `median R_E(48-72h) >= +1%`
4. A2 `Delta starvation_exposure_AUC(48-72h) <= 0` が3/3 seed
5. A0 / A2とも人工的max-population halt等へ到達しない

`+1%` はworking thresholdであり、結果を見て変更しない。

## 14.2 competition-ready preferred candidate

`MECHANISTIC_WORKING_FLUX` のうち低い方から見て、さらに以下を満たす最初のfluxを `PREFERRED_COMPETITION_FLUX` とする。

6. A2で人口統計効果がphototrophy有利方向に整合すること
   - starvation deathsが増えない
   - final populationが悪化しない
   - 3 seedの多数（>=2/3）が同方向
7. `median Delta_proxy_pt >= +3.0 percentage points`
8. `n_required_est <= 20`

`+3 pt` はExp21の実測雑音床から、次段を概ね20 seed以内で設計するための実務的下限である。

mechanistic working fluxは得られたが7–8を満たさない場合:

```text
MECHANISTIC_WORKING_BUT_COMPETITION_UNDERPOWERED
```

として、Exp23へ自動的には進まない。

## 14.3 GENERAL_ADVANTAGE_FLAG

preferred candidateでA0 72 h時点の

```text
median relative delta total living matter >= +10%
```

なら `GENERAL_ADVANTAGE_FLAG` を付ける。

これは失格ではないが、dynamic環境特異的rescueではなく常時強いbenefitである可能性を明示する。

## 14.4 candidateなし

どのfluxもmechanistic criterionを満たさない場合:

```text
NO_WORKING_FLUX_IN_RANGE
```

同じExp22内でfluxを追加しない。

---

# 15. aggregate出力

最低限:

```text
exp22_pair_results.csv
exp22_flux_response.csv
exp22_seed_summary.csv
exp22_gate_summary.json
exp22_working_flux_recommendation.json
```

`exp22_flux_response.csv`:

```text
median / min / max R_E
starvation-exposure effect
final population effect
total-living-matter effect
birth/death/starvation-death effect
photo_used_j
photo utilization fraction
structural N investment
Delta_proxy_pt
```

`exp22_working_flux_recommendation.json` は最低限:

```text
mechanistic_working_flux
preferred_competition_flux
status
median_R_E_post_turnover
median_Delta_proxy_pt
n_required_est
recommended_exp23_seed_count
GENERAL_ADVANTAGE_FLAG
notes
```

`recommended_exp23_seed_count` はpreferred candidateがある場合:

```text
max(8, n_required_est)
```

とし、candidate条件により最大20を想定する。

formal completeness gateとして72/72 runが揃わない場合、aggregate成功扱いにしない。

---

# 16. Exp22で主張してよいこと / いけないこと

## 主張してよい

```text
- physical phototrophy経路が独立物理上界とledgerを守って動作したか
- photon fluxに対するmechanistic effect curve
- A2でEnergy benefitがstarvation / populationへどう翻訳されたか
- A0でgrowthへどう翻訳されたか
- 次のcompetitionに必要なseed数の事前見積もり
- N非律速50x条件でのworking flux
```

## まだ主張しない

```text
- phototrophyが自然選択で増える
- phototrophyが進化的に固定する
- structural N costとのtrade-offが成立する
- primitive Earthで実際にこのfluxだった
- day/night cycle下での適応性
- spatial phototrophic nicheが成立した
```

---

# 17. Exp22後の分岐

## PREFERRED_COMPETITION_FLUXあり

次段（仮Exp23）を事前登録する。

```text
phototrophy OFF vs ON single-world competition
A0_STATIC / A2_DYNAMIC_VENT
50:50 initial lineage ratio
selected flux
120 h以上
mutation / innovation / loss OFF
seed数 = max(8, n_required_est)
```

Exp21と同じlineage-frequency方式でphototrophy能力そのものが選択されるかを測る。

## mechanisticのみ / competition underpowered

Exp23へ進まず、run duration・環境ストレス・flux rangeのどれを変えるかを別番号で事前登録する。

## N cost trade-off

Exp22とは分離し、N-limited stockを用いる別実験として設計する。

---

# 18. Claude実装時の必須確認事項

Claudeは実装前に本計画とIssue #75を読み、少なくとも以下を満たすこと。

1. legacy `_absorb_light()` をphysical Energy経路から除去
2. mechanism-independent Energy upper-bound testを追加
3. legacy parameter independence property testを追加
4. `flux=0` を使わず `1e-6` を使用
5. effective configをformal条件と照合
6. A0とA2でprimary readoutを分ける
7. aggregateで `Delta_proxy_pt` と `n_required_est` を算出
8. 72/72 run completeness gateを維持
9. 結果を見てthreshold / flux gridを変更しない
10. structural N costをExp22の成功条件にしない

---

# 19. 実行順

```text
1. G0-G6に必要なproduction code / tests修正
2. Exp22 harness + aggregate + workflow実装
3. preflightのみ実行
4. preflight全PASSを確認
5. 72 formal runs実行
6. aggregate completeness確認
7. flux-response / demographic translation考察
8. G7: Exp23必要seed数を算出
9. PREFERRED_COMPETITION_FLUXがある場合のみExp23を事前登録
10. structural N cost検証は別実験へ分離
```
