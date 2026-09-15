# Exp23 実験計画 — primitive phototrophy 直接競争実験

更新: 2026-09-15  
対象version: **V1.11**  
状態: **PREREGISTERED / READY FOR IMPLEMENTATION**

関連:

- `docs/Exp21_実験計画.md`
- `docs/Exp21_結果考察.md`
- `docs/Exp22_実験計画.md`
- `docs/Exp22_結果考察.md`
- `docs/Exp22_Opus5レビュー.md`
- Issue #75

---

# 1. 背景

Exp21では、physical modeにおいて同一集団内で既存形質差に自然選択が働き、lineage frequencyが変化することを確認した。

Exp22ではprimitive phototrophyのphoton fluxを校正し、A2_DYNAMIC_VENTで以下を確認した。

- low flux (`0.015`, `0.05`) は生態効果が弱い
- `0.15` はborderline
- `0.5 µmol photons m^-2 s^-1` は中程度の正効果
- `1.5 µmol photons m^-2 s^-1` は強いpositive effect
- zero-lightではphototrophy apparatus由来のコストが存在し、A0では約1%程度の不利が観測される
- stored Energy (`R_E`) はfitness primaryとして不適切で、population / deaths / total living matter / lineage frequencyを主要指標とすべき

Opus5レビューでは、Exp23のprimary fluxとして `0.5`、positive controlとして `1.5`、seed数として **8 seeds** が推奨された。

Exp23では、phototrophy OFF/ONを同一世界へ50:50で投入し、photon fluxに応じてphototrophy ON lineageが実際に増減するかを直接検証する。

---

# 2. 目的

**phototrophy capabilityが持つ維持コストと光由来benefitのバランスが、同一集団内の自然選択としてlineage frequencyへ反映されるか確認する。**

主たる問い:

1. photon flux = 0ではphototrophy ON lineageは増えない、または減少するか。
2. photon flux = 0.5ではphototrophy ON lineageが増加するか。
3. photon flux = 1.5ではphototrophy ON lineageが明確に増加するか。
4. flux増加に応じてphototrophy ONへの選択が強くなるか。

Exp23はspontaneous evolution実験ではなく、**既知のOFF/ON phenotypeを直接競争させるselection assay**である。

---

# 3. 実験環境

## A2_DYNAMIC_VENTのみ

Exp23のformal competitionは **A2_DYNAMIC_VENTのみ**で行う。

理由:

- Exp21でA2がlineage frequency変化を検出可能な環境であることを確認済み
- Exp22でphototrophyのbenefitがA2で明瞭に現れた
- A0はExp22ですでにapparatus cost / growth effectの情報を取得済み
- Exp23では「動的環境下でphototrophyが選択されるか」に実験目的を限定する

A2環境条件はExp21 / Exp22と同一とし、結果を見てH2 fluxやvent turnover強度を変更しない。

- vent relocation: 48 physical hごと
- 120 h run中に48 h / 96 hの2回を経験

---

# 4. 競争させる2 lineage

## OFF lineage

- `phototrophy_on = False`
- phototrophy innovation/loss OFF
- reference phenotypeのその他geneはON lineageと同一

## ON lineage

- `phototrophy_on = True`
- `light_absorption = 0.01`
- phototrophy innovation/loss OFF

## 共通条件

- `physical_mode = True`
- `physical_light_enabled = True`
- `light_cycle_enabled = False`
- light pattern = uniform constant
- continuous mutation OFF
- structural innovation OFF
- predation OFF
- initial jitter OFF
- OFF/ON以外のgene / matter / Energy / damage / position分布は同一母集団由来

子孫は親lineageのphototrophy capabilityを正しく継承すること。

---

# 5. 初期集団

- total population: **100**
- OFF lineage: **50**
- ON lineage: **50**

初期100個体を共通条件で生成した後、専用lineage-assignment RNGで50:50へ割り当てる。

### 割当条件

- organism/environment RNGから独立した専用RNGを使用
- 同seedで再現可能
- 50:50を厳密保証
- 位置・matter・Energy・damage等による系統偏りを生じさせない

可能なら、lineage labelを入れ替えたmirror assignmentのdiagnosticもpreflightで実施し、初期割当そのものによるfitness biasが無いことを確認する。

---

# 6. photon flux条件

formal conditionは3水準。

| condition | photon flux [µmol photons m^-2 s^-1] | 役割 |
|---|---:|---|
| F0 | **0.0** | negative control / apparatus cost only |
| F05 | **0.5** | primary working flux |
| F15 | **1.5** | positive control |

`flux=0` は正式に許容する。

- `physical_light_enabled=True`
- `light_photon_flux_umol_m2_s=0.0`
- photo incident / absorbed / usable / used energyは厳密に0であること
- structural apparatus / upkeep costは残る

負のfluxはvalidationで拒否する。

---

# 7. 実行時間

**120 physical hours**

主要時点:

- 0 h
- 12 h
- 24 h
- 48 h
- 72 h
- 96 h
- 120 h

必要なら内部samplingはより高頻度でよいが、少なくとも上記時点は必ずartifactへ残す。

---

# 8. seed

**8 seeds固定**

```text
23001
23002
23003
23004
23005
23006
23007
23008
```

結果を見てseedを追加・差し替えしない。

3 flux × 8 seeds = **24 formal runs**。

8 seedの根拠:

- Exp21のlineage-frequency noise floor
- Exp22 flux=0.5の72 h total-living-matter effect
- Opus5レビューのpower estimate

flux=0.5では120 h時点で約4.9–7.0 percentage pointのfrequency shiftが期待され、8 seedで検出可能な見込み。

---

# 9. Primary endpoint

## phototrophy ON lineage frequency

```text
f_photo = N_ON / (N_ON + N_OFF)
```

初期値 = 0.5。

primary comparisonは120 h時点の `f_photo`。

### 主要仮説

```text
F0   : f_photo <= 0.5 または少なくとも増加しない
F05  : f_photo > 0.5
F15  : f_photo >> 0.5
```

さらにflux-responseとして

```text
selection toward ON: F0 < F05 < F15
```

の順序性を重視する。

---

# 10. Secondary endpoints

lineageごとに以下を記録する。

- population
- births cumulative
- deaths cumulative
- starvation deaths cumulative
- total living matter
- mean matter
- mean stored Energy
- mean starvation state
- photo incident / absorbed / usable / used Energy cumulative
- photo structural N
- lineage extinction time
- fixation time

`mean stored Energy` / `R_E` はfitness primaryには使用しない。

fitness関連の解釈優先順位:

1. lineage frequency
2. population / survival / deaths
3. total living matter
4. births
5. mechanistic diagnostics (Energy / N / starvation state)

---

# 11. Selection coefficient

両lineageが存在する区間では、lineage比率のlogit変化から補助的にselection coefficientを算出する。

例:

```text
s = [logit(f_t2) - logit(f_t1)] / Δt
```

ただし片lineageが0になった場合はpseudocountで無理に連続値化しない。

- extinction
- fixation

をそのままイベントとして記録する。

---

# 12. Preflight / Gate

formal run前に以下をすべてPASSさせる。

## G0 — legacy light contamination = 0

Exp22と同じlegacy-light regressionを維持する。

## G1 — physical photon Energy upper-bound

常に:

```text
photo_used <= photo_usable_max <= photo_absorbed <= photo_incident
```

## G2 — effective config一致

A2 / flux / mutation OFF / light cycle OFF / uniform light等が本計画とfield単位で一致すること。

## G3 — initial population / lineage ratio

- total = 100
- OFF = 50
- ON = 50

## G4 — initial-state fairness

lineage assignment前のposition / matter / Energy / damage / genomeが共通母集団由来であること。

ON/OFFで意図的に異なるのは:

- phototrophy capability
- `LIGHT_ABS=0.01`
- capabilityに伴って正式モデル上発生するapparatus assembly / upkeep

のみ。

## G5 — lineage inheritance

OFF親の子はOFF、ON親の子はONを維持する。

mutation / innovation / lossにより実験途中でlineage stateが反転しないこと。

## G6 — zero-flux identity

F0では:

```text
photo_incident = 0
photo_absorbed = 0
photo_usable_max = 0
photo_used = 0
```

を厳密に満たす。

## G7 — OFF run flux independence

OFF-only diagnosticにおいて、同一(environment, seed)ならflux 0 / 0.5 / 1.5でtrajectoryが完全一致すること。

これが崩れた場合、fluxがOFF経路へ漏れているためformal competitionを開始しない。

## G8 — ledger closure

Energy / C / N / P ledgerが既存gateをPASSする。

## G9 — lineage assignment bias diagnostic

少なくとも短時間diagnosticで、lineage label swapにより結果が一方向へ固定されないことを確認する。

## G10 — seed preregistration

formal seedは23001–23008に固定し、結果後の追加をしない。

---

# 13. Formal outputs

各runで最低限以下を保存する。

## time series CSV

少なくとも:

- time_h
- N_OFF
- N_ON
- f_photo
- OFF_births_cum
- ON_births_cum
- OFF_deaths_cum
- ON_deaths_cum
- OFF_starvation_deaths_cum
- ON_starvation_deaths_cum
- OFF_total_living_matter
- ON_total_living_matter
- OFF_mean_matter
- ON_mean_matter
- OFF_mean_stored_energy_j
- ON_mean_stored_energy_j
- photo energy ledger fields

## per-run summary

- final f_photo
- Δf_photo from 0.5
- fixation/extinction if any
- lineage-specific births/deaths
- lineage-specific total living matter
- selection coefficient where valid

## aggregate

fluxごとに:

- n complete seeds
- final f_photo median / mean / min / max
- number of seeds with f_photo > 0.5
- median Δf_photo
- lineage death/birth differences
- median selection coefficient
- fixation/extinction count

artifact欠損が1件でもあればaggregateはfail loudlyする。

---

# 14. 成功判定

## Primary condition: F05 = 0.5

**Strong support**:

- 120 hでON lineageが **8 seed中7 seed以上**で `f_photo > 0.5`
- final `f_photo` median >= **0.53**
- median selection coefficient > 0
- population/deaths/total living matterの少なくとも一部がON優位の機構と整合

この場合:

> `0.5 µmol photons m^-2 s^-1` ではprimitive phototrophyの光利益がapparatus costを上回り、A2_DYNAMIC_VENTにおいて自然選択でphototrophy ON lineageが増加する

と判断する。

## Positive control: F15 = 1.5

期待:

- ON lineageが8 seedの大半で明確に増加
- F05より大きいfrequency shift

F05がnullでもF15が明確にpositiveなら、assay failureではなく「0.5のselection effectが弱い」と解釈する。

## Negative control: F0 = 0

期待:

- ON lineageは増加しない
- apparatus costにより減少しても自然

F0でONが一貫して強く増加した場合は、phototrophy以外の差・bugを疑い、F05/F15の生物学的解釈を保留する。

---

# 15. Flux-responseの最終判定

最も重要なのは3条件の順序性。

理想:

```text
median f_photo(F0) < median f_photo(F05) < median f_photo(F15)
```

このパターンが得られれば、単に「ONが増えた」だけでなく、

> **phototrophyには維持コストがあり、利用可能な光Energyが増えるにつれてnet fitnessが負から正へ転じる**

というtrade-offを直接示せる。

---

# 16. Exp23でやらないこと

- spontaneous phototrophy innovation
- phototrophy loss evolution
- `light_absorption` geneの進化
- day/night cycle
- N-limited structural-cost trade-off
- fluxを結果後に追加・調整
- seed追加によるoptional stopping
- A0 competitionの追加

Exp23は **A2におけるphototrophy OFF/ON direct competition**だけに限定する。

---

# 17. Exp23後の分岐

## Exp23成功

V1.11で以下が成立したことになる。

1. physical phototrophy経路が動作
2. flux-responseが存在
3. apparatus costが存在
4. 十分な光でnet benefitが正になる
5. 同一集団内でphototrophy ON lineageが自然選択により増加

次はspontaneous innovationを導入し、phototrophyが**発生してから選択される**長期進化実験へ進む。

## Exp23不成立

F15 positive controlの結果で分岐する。

- F15 positive / F05 null: 0.5のeffectが弱い。mechanismは成立。
- F15もnull: competition harness / inheritance / ecology couplingを診断。
- F0でONが強く増える: apparatus/capability実装またはlineage setupを診断。

結果を見て即座にseedやdurationを増やさず、原因診断を先に行う。

---

# 18. Claude実装・実行指示

Claude Codeは本書をExp23の正本として使用する。

実装時:

1. Exp21 competition harnessを可能な限り再利用する。
2. Exp22 phototrophy setup / physical-light gatesを再利用する。
3. 新しい独自ロジックを最小化する。
4. preflight G0–G10を実装し、全PASS後のみformal runを開始する。
5. 24 formal runs (`3 flux × 8 seed`) をGitHub Actionsで実行する。
6. 全run完了後aggregateを生成する。
7. completeness gateで24/24を必須とする。
8. formal結果を見てseed / flux / durationを変更しない。
9. 実装上、本計画から変更が必要な場合は、勝手に変更して実行せず、差分と理由をIssue #75へ報告する。

---

# 19. 一文要約

**Exp23は、A2_DYNAMIC_VENTでphototrophy OFF/ONを50:50で直接競争させ、flux 0 / 0.5 / 1.5、120 h、各8 seedsの条件で、光利用能力の維持コストとbenefitが自然選択によるlineage frequency変化として現れるかを検証するV1.11の本命competition assayである。**
