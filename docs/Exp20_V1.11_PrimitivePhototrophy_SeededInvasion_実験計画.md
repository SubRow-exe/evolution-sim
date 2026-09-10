# Exp20 — V1.11 Primitive Phototrophy Seeded Invasion 実験計画

更新: 2026-09-10  
状態: **PREREGISTRATION / Claude実装・実行用正本**

> V1.11実装は `docs/V1.11_原始Phototrophy_実装仕様_rev2.md` を唯一の正本とする。旧rev1の数値・H2 yield bonus方式は使用しない。

---

# 0. 背景

V1.11では、H2依存iLUCAから最初期のanoxygenic phototrophyを獲得可能にする。

V1.11 rev2での意味は:

```text
light -> cyclic photophosphorylation -> ATP/PMF -> maintenance/activity補助
H2    -> reducing power + chemical Energy
CO2 + N + P + reducing power -> biomass
```

したがってphototrophyは、H2が一時的に不足・停止したときにstored Energy消費を抑え、生存時間を伸ばす可能性がある。一方、lightだけで持続的なnet biomass growthはできない。

Exp18ではH2総供給量を揃えたまま時間構造だけを変えると:

- A0 STATIC: 安定生存
- A1 TEMPORAL: 6 hごとのvent ON/OFF切替で祖先が全滅

となった。

A1は「H2の総量不足」ではなく、**局所H2 source interruptionへの耐久不足**を強く表す環境である。V1.11 phototrophyのmaintenance creditがまさにこの欠点を補えるかを検証する。

また、自然innovation確率 `1e-4 / birth` では現在の5–10世代程度の短期runで出現・定着まで観察できる保証がない。そのためExp20は自然発生を待たず、t=0でprimitive phototrophを既知頻度で混ぜる **seeded invasion experiment** とする。

---

# 1. Exp20の問い

主質問:

> **primitive phototrophyは、H2が安定したA0よりも、H2 sourceが時間的に途切れるA1で相対fitnessを上げるか？**

副質問:

1. 少数（1%）からphototrophが増加できるか
2. phototrophがA1で祖先集団の絶滅を遅らせる／回避するか
3. 初期頻度1% / 10% / 50%で相対fitnessが変わるか（frequency dependence）
4. phototrophyのN構造コストがあるため、A0では無条件のsweepにならず、環境依存のtrade-offが現れるか
5. 光Energy ledger / N ledger / H2 ledgerが物理・保存則上成立するか

Exp20では `light_absorption` の長期continuous evolutionは評価しない。

---

# 2. Scope / version

Exp20は **V1.11の最初のformal ecological validation**。

新しい機能はV1.11 rev2のみ:

```text
physical photon flux
phototrophy capability
light_absorption -> absorptance
photo maintenance credit
explicit phototrophy structural N pool
```

以下はV1.10.1 baselineを維持:

```text
H2 physical uptake kinetics
H2 finite-flux vent
C/N/P 50 biomass-equivalents
C/N/P background exchange OFF
iLUCA basal physiology
predation OFF
```

---

# 3. Formal baseline

## 3.1 common physical baseline

Exp19 / LUCA proxy / V1.10.1 formal値を継承する。

```text
physical_mode = True
dt_seconds = 10 s
world = 20 mm x 20 mm
grid = 40 x 40
cell_size = 0.5 mm
initial_population = 100
vent_count = 4
H2 source mode = finite flux
F0 = 4.890000722073717e-11 mol/s/vent
H2 diffusion = 5e-9 m2/s
H2 loss/exchange tau = 900 s
C/N/P = 50 biomass-equivalents
C/N/P background exchange = OFF
predation = OFF
```

H2 usable Energy formal baselineはConfig class defaultではなくLUCA proxy実値:

```text
h2_usable_energy_j_per_mol = 2407.5 J/mol H2
```

## 3.2 physical light

formal armでは全て:

```text
physical_light_enabled = True
light_photon_flux_umol_m2_s = 0.015
light_effective_wavelength_nm = 800
light_physical_pattern = uniform
phototrophy_radiant_to_usable_eff = 0.10
light_cycle = OFF
```

lightは全worldで同じ。Exp20では空間light nicheを検証しない。

## 3.3 primitive phototroph phenotype

```text
phototrophy capability = ON
light_absorption = 0.01 fixed
absorptance = 1-exp(-0.01) ~= 0.995%
```

ancestor:

```text
phototrophy capability = OFF
light_absorption = 0
```

---

# 4. Geneticsを固定する

Exp20はinnovation/optimization実験ではなくinvasion fitness実験。

全formal armで:

```text
phototrophy_innovation_prob = 0
phototrophy_loss_prob = 0
continuous genes = fixed
initial_jitter_sigma = 0
```

つまり親と子は原則clonalで、比較差は:

```text
phototrophy capability + light_absorption + その構造N cost
```

だけ。

`mutation_rate` を含むその他geneを結果に応じて変えない。

---

# 5. t=0 phototroph seeding

初期100個体中のphototroph-capable founder数を:

```text
0%  -> 0
1%  -> 1
10% -> 10
50% -> 50
```

とする。

## 5.1 founder選択

arm間でRNG系列を変えないこと。

phototroph founder選択のためにsimulation RNGを追加消費してはいけない。

推奨:

```text
(seed, organism_id, "exp20-photo-founder")
```

を `hashlib.blake2b` 等のstable hashでrankingし、上位N個体をphototroph化する。

Python built-in `hash()` はprocessごとに変動し得るため禁止。

1% founder集合は10%のsubset、10%は50%のsubsetになるよう同一rankingを使う。

これにより同seed内では位置・個体初期状態を最大限対応させたまま初期頻度だけ変更できる。

## 5.2 t=0でfunctional apparatusを持たせる

Exp20の問いは「機能的primitive phototrophが侵入できるか」なので、seeded founderを装置未完成状態から始めない。

各seeded founderについてrev2式から:

```text
photo_n_target_mol
```

を計算し:

```text
photo_structural_n_mol = photo_n_target_mol
assembly_fraction = 1
```

で開始する。

ただしNを無から生成してはいけない。

founderが存在するlocal voxelの `fixed_nitrogen` fieldから同量をt=0で厳密に減らす。

```text
world fixed N -> organism photo_structural_n
```

という内部移転として扱う。

local voxelに必要Nが不足している場合、他cellからsilentに借りてはいけない。preflight/formal runをfailさせる。

初期system nitrogenはこの移転前後でmachine precision範囲内に保存されること。

---

# 6. Environment arms

## A0 STATIC

Exp18 A0を再利用。

```text
4 vents
位置固定
全vent常時ON
各vent flux = F0
world total H2 source = 4F0
```

## A1 TEMPORAL

Exp18 A1をそのまま再利用。

```text
vent位置 = 固定
4 ventsを2組に分ける
6 hごとにactive pairを交代
active vent = 2F0
inactive vent = 0
常に2 vents active
```

したがって各時点で:

```text
2 * 2F0 = 4F0
```

となり、A0とworld全体の瞬間総H2 source rateも積算供給量も一致する。

A1で変わるのは **H2供給の局所時間構造** のみ。

A1のvent grouping / phase / turnover実装を結果を見て変更しない。

---

# 7. Formal design

```text
Environment: A0_STATIC / A1_TEMPORAL
Initial photo frequency: 0 / 0.01 / 0.10 / 0.50
Seeds: 20001 / 20002 / 20003
Duration: 5 physical days
```

総run数:

```text
2 x 4 x 3 = 24 runs
```

同じseed・frequencyをA0/A1でpaired comparisonする。

### 5日にする理由

- Exp18 A1 ancestor-onlyでは約3日付近で絶滅が起きた。
- 最初の48 hで複数回の6 h source switchingを経験できる。
- 48 h時点でselectionを測り、その後120 hまでecological rescueを見る。
- 現在のGitHub-hosted runnerで6 h/jobを超えるリスクを抑える。

各matrix jobは1 runのみ。複数runを1 jobへ直列に詰めない。

---

# 8. Primary endpoint — 48 h invasion fitness

A1ではancestor-onlyが後半に全滅し得るため、5日最終値だけでrelative fitnessを評価しない。

**主評価時点は48 h** とする。

phototroph founderありarm（1/10/50%）について:

```text
P_t = phototroph-capable population at time t
A_t = ancestor(non-phototroph) population at time t
```

relative log-ratio change:

```text
R48 = ln((P_48 + 0.5)/(A_48 + 0.5))
    - ln((P_0  + 0.5)/(A_0  + 0.5))
```

0.5はlineage extinction時のlog(0)回避用に事前固定するpseudocount。

1日あたり:

```text
s48_per_day = R48 / 2
```

各seed/frequencyについて:

```text
Delta_s48 = s48_A1 - s48_A0
```

を主estimandとする。

解釈:

```text
Delta_s48 > 0
=> phototrophyの相対fitnessはSTATICよりTEMPORAL H2環境で高い
```

n=3なのでp値による有意差判定を主目的にしない。

各initial frequencyのmedian Delta_s48、3 seedの符号、全9 paired comparisonsの方向をそのまま報告する。

結果を見て任意の% thresholdを追加しない。

---

# 9. Secondary endpoints

## 9.1 ecological rescue

各runで:

```text
survival at 120 h
extinction time
population N(t)
population AUC
births / deaths
starvation deaths
max generation
```

特にA1で:

```text
0% photo control
vs
1 / 10 / 50% seeded photo
```

を比較する。

phototrophが「選択される」ことと「集団全体を救済する」ことは別結果として扱う。

## 9.2 frequency trajectory

最低でも:

```text
0 h
6 h
12 h
24 h
48 h
72 h
120 h
```

のphototroph fractionを保存する。

可能ならstatsを1 physical hour cadenceで記録する。

## 9.3 frequency dependence

1% / 10% / 50%で `s48_per_day` を比較する。

高頻度ほどadvantageが低下する場合:

- N構造cost
- local competition
- resource depletion

等によるnegative frequency dependenceの候補となる。

ただしExp20だけで機序を断定しない。

## 9.4 phototrophy mechanism diagnostics

最低限:

```text
photo_incident_j_cum
photo_absorbed_j_cum
photo_usable_max_j_cum
photo_used_j_cum
photo_unused_j_cum
photo_conversion_loss_j_cum
mean photo_credit use per phototroph
mean assembly_fraction
photo_structural_n_mol total
```

必須不等式:

```text
photo_used_j <= photo_usable_max_j <= photo_absorbed_j <= photo_incident_j
```

## 9.5 lineage-specific physiology

photo / ancestor別に可能な範囲で:

```text
population
births
deaths / starvation deaths
mean stored Energy
mean runway
mean matter
mean local H2
H2 biological uptake per capita
maintenance expenditure
photo maintenance offset
```

を集計する。

## 9.6 element / H2 ledger

```text
C/N/P inventory residual
photo structural-N inventory
H2 source / environmental loss / biological uptake
system Energy residual
```

を保存。

structural Nをsystem nitrogenへ必ず含める。

---

# 10. Interpretation preregistration

## Pattern 1 — desired environment-dependent advantage

```text
A0: s48 ~= 0 or negative
A1: s48 positive
Delta_s48 > 0 consistently
```

なら:

> primitive phototrophyは無条件に強い能力ではなく、H2 interruption環境で選択価値が高まる

と解釈できる。

## Pattern 2 — A0でも強いsweep

```text
A0 / A1ともstrong positive s48
```

なら:

> current photon flux / photo efficiency / structural costの組合せではphototrophyがgeneral advantageになっている

と記録する。

結果を見て同じExp20内で数値を弱めない。必要ならExp20.1 sensitivityとして別実験。

## Pattern 3 — A1でもadvantageなし

```text
Delta_s48 <= 0
```

なら:

> current physically grounded low-light priorではprimitive phototrophyがA1 interruptionを補うほど強くない

と記録する。

結果を見てphoton fluxを上げない。必要なら独立sensitivityで事前登録する。

## Pattern 4 — relative fitnessは上がるが集団は絶滅

これは有効な結果。

```text
phototroph fraction rises
but total population eventually extinct
```

なら:

> phototrophyはA1で相対的には有利だが、0.015 umol photons/m2/s・1% absorptanceではecological rescueに不足

と区別する。

## Pattern 5 — low frequencyのみ侵入

1%でpositive、50%で弱い/negativeならfrequency dependenceの可能性。

これは将来の共存・resource feedback実験候補とする。

---

# 11. Phase 0 / preflight — formal前のmechanical validation

formal 24 run開始前に短いmechanical testsを必須とする。

最低限:

### T20-1 OFF regression

```text
phototrophy OFF
```

でV1.10.1 physical physiologyへ回帰。

### T20-2 Dark

```text
phototrophy ON + light=0
=> photo_used = 0
```

### T20-3 H2 absent / light present

phototrophはphoto creditでmaintenanceを肩代わりできるが:

```text
no persistent Energy storage charging from light alone
no sustained net biomass growth from light alone
```

### T20-4 No carry

unused photo creditはtick endで消滅し、次tickへcarryしない。

### T20-5 absorptance

`1-exp(-a)` が0<=absorptance<1、単調増加。

### T20-6 photo Energy ledger

```text
used <= usable_max <= absorbed <= incident
```

### T20-7 structural N conservation

assembly / t=0 seeding / inheritanceを含めN inventoryが保存。

### T20-8 seeded founder exactness

0/1/10/50 founderが指定通りで、same seedのnested founder setsが成立。

### T20-9 RNG isolation

founder assignmentがsimulation RNGを追加消費せず、phototrophy以外のpaired initial stateを変えない。

### T20-10 A0/A1 H2 source equality

同durationで:

```text
cumulative H2 external source A0 == A1
```

をmachine precision/既存numerical tolerance内で確認。

### T20-11 LUCA baseline

formal configで:

```text
h2_usable_energy_j_per_mol == 2407.5
```

をassert。3750へsilent fallbackしない。

preflight failure時はformalを開始しない。

---

# 12. Output / aggregate

推奨directory:

```text
experiments/exp20_v111_phototrophy_invasion/
```

最低限:

```text
run_exp20.py
aggregate_exp20.py
README.md or config manifest
```

formal output per run:

```text
config.json
summary.json
stats.csv (1 h cadence推奨)
lineage_summary.csv or equivalent
```

aggregate:

```text
exp20_aggregate.csv
exp20_primary_estimand.csv
exp20_summary.md/json
```

aggregateはartifact不足・incomplete runをsilent skipしてはいけない。

24 runのexpected manifestを持ち、欠損があればaggregate jobをfailさせる。

---

# 13. GitHub Actions

Exp20専用workflowを作る。

推奨:

```text
.github/workflows/exp20-v111-phototrophy.yml
```

構造:

```text
preflight
  -> formal matrix 24 jobs
  -> aggregate
```

matrix軸:

```text
environment = [A0_STATIC, A1_TEMPORAL]
photo_fraction = [0, 0.01, 0.10, 0.50]
seed = [20001, 20002, 20003]
```

各job = 1 run = 5 days。

GitHub-hosted runnerの制限を考慮し、複数runを1 jobへ直列化しない。

snapshotは必要最小限。individual-level巨大dumpを高頻度で保存しない。

workflow timeoutを6 h超へ設定することで制限を回避しようとしてはいけない。

---

# 14. 変更禁止 / integrity

formal開始後、結果を見て以下を変更しない:

```text
photon flux = 0.015 umol/m2/s
wavelength = 800 nm
radiant_to_usable_eff = 0.10
light_absorption = 0.01
photo N multiplier = rev2 value
A0/A1 H2 definitions
F0
6 h switching interval
C/N/P = 50 equivalents
C/N/P exchange OFF
initial photo fractions
seeds 20001-20003
duration 5 days
primary endpoint = 48 h
```

実装バグ以外の理由で変更が必要なら、Exp20 Attempt 1を保存してExp20.1またはAttempt 2として新たに事前登録する。

---

# 15. Exp20で主張してよいこと / まだ主張しないこと

Exp20で評価可能:

- primitive phototrophy capabilityの短期invasion fitness
- H2 temporal interruptionによるselection differential
- short-term ecological rescue
- initial-frequency dependenceの兆候
- photo Energy / N costのmechanical trade-off

まだ評価しない:

- phototrophyが自然innovationから何世代で出現するか
- `light_absorption` が長期的にどこまで進化するか
- spatial light niche / depth adaptation
- H2から完全独立したphotoautotrophy
- H2S / Fe2+利用
- oxygenic photosynthesis / O2 production
- 長期共存・speciation

長期計算環境構築後にnatural innovation + continuous evolutionを別experimentで行う。

---

# 16. Claude向け実装順序

1. `V1.11_原始Phototrophy_実装仕様_rev2.md` を実装
2. V1.10.1 regression testを通す
3. Exp20 T20-1〜T20-11を実装して全PASS
4. Exp20 harness / 24-arm manifestを作成
5. formal開始前にeffective configをartifactへ保存
6. 24 runを実行
7. aggregateでexpected manifest completenessを検証
8. primary `Delta_s48` とsecondary ecological endpointsを機械集計
9. raw artifactを残し、結果を見てformal parameterを変更しない

Claudeは旧rev1のH2 yield bonus式を再導入しないこと。
