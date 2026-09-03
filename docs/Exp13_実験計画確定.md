# Exp13 実験計画確定 — V1.8 一次Energy生態非対称

更新: 2026-09-03
状態: **人間方針確定 / Sonnet 5実装・実行可能**

目的:

> V1.8で導入する一次Energy物理が、
> **light = broad / renewable / day-night / low-average**
> **chemical = localized / stock / depletable / competitive / high-local-return potential**
> という異なる生活条件を作れているか確認する。
>
> 一点を決め打ちせず、光量とchemical uptake特性を広く地図化し、現在の世界で使うworking referenceを選ぶ。

最優先正本:
1. `docs/V1.8_Exp13_レビュー判断.md`
2. `docs/V1.8_一次Energy生態非対称仕様.md`
3. 本書
4. `docs/V1.8_実装チェックリスト.md`
5. `docs/数値再現性・Actions実行環境方針.md`

旧Exp13案・Opusレビュー原文より上記を優先する。

---

# 1. Exp13で決めること / 決めないこと

## 決める

1. day/night + density-dependent uptake実装が物理・台帳上正しいか
2. light-only世界の「絶滅域 → 境界域 → 頑健成立域 → 豊富域」の地図
3. 現世界におけるworking `light_max`
4. chemicalの`chemical_uptake_half × chem_uptake`生態地図
5. 現世界におけるworking `chemical_uptake_half / chem_uptake`
6. chemical stock depletion / recovery / density competitionが成立するか
7. light-only / chemical-only双方が長期成立できるか
8. mixed worldで両Energy routeに実利用価値が残るかを探索
9. day/nightがbody_sizeへ新しい選択圧を作るか診断

## 決めない

- 自然界の普遍的な絶対光量
- phototrophyの進化起源
- INITIAL_GENOME.light_absorption=0化
- cyanobacteria / chloroplast / plastid
- vent source有限寿命
- 季節
- 温度
- bmr_core再選定
- 「lightとchemicalのどちらが優れているか」という単一順位

selected値は将来environment physics追加時に再校正可能な**working reference**。

---

# 2. 共通条件

V1.7 close後の値:

```text
bmr_core = 0.15
memory_tau = 10
response_gain = 64
light_cycle_period_ticks = 200
light_day_fraction = 0.5
light_uptake_half = 0.6
```

Exp13の一次Energy条件は原則:

```text
primary_energy_density_response = True
light_cycle_enabled = True  # lightがある条件
```

知覚responseは変更しない:

```text
light_stimulus_half = 1.2
chemical_stimulus_half = 12.3
```

nutrient / reproduction / movement / damage / vent source/loss等はV1.7-finalを維持。

`max_population_halt=10000`は計算安全装置であり、生態制御ではない。

---

# 3. Phase 0 — 実装・再現性・runtime HARD GATE

Exp12の10k×2のような重いpreflightは行わない。

必須:

```text
P0-1 Config schema / JSON round-trip / manifest checker
P0-2 V1.8 unit tests
P0-3 Energy/Matter conservation / ledger
P0-4 feature flags 2×2短時間E2E
P0-5 current-run determinism 2,000 tick ×2
P0-6 workflow/collector E2E smoke
P0-7 runtime preflight
P0-8 full pytest / CI Green
```

### P0-4 feature flags

同一代表light-only条件で短時間:

```text
density OFF / cycle OFF
density ON  / cycle OFF
density OFF / cycle ON
density ON  / cycle ON
```

を各1本以上。

OFF/OFFはV1.7回帰。

### P0-5 determinism

```text
mixed environment
seed=1
primary_energy_density_response=True
light_cycle_enabled=True
light_max=2.1
chemical_uptake_half=1.5
chem_uptake=2.0
2,000 tick ×2
```

同一current runner内bit完全一致。

過去Hosted Runner artifactとのbit完全一致はHARD GATEにしない。

---

# 4. 実行前runtime予測 — Sonnet 5必須報告

**Phase A正式matrixをdispatchする前に、Exp13全体が終了するwall-clock概算をユーザーへ報告する。**

新規計測instrumentationは追加しない。短い代表run、既存`performance.csv`、Actions timestamps/logsを使う。

報告必須:
- formal simulation総run数（予定143 run）
- phase別run数・tick数
- max-parallel
- 代表short-run実測
- single-run最大時間概算
- phaseごとのwave数を考慮したmatrix wall-clock
- Phase 0 / selection / collectを含む**Exp13全体合計wall-clock概算**
- 安全率・不確実性

`single-run timeout`と`experiment total wall-clock`を混同しない。

Phase Aでselected値が確定した後、Phase B開始前に予測を更新してよいが、**最初の合計予測を省略しない。**

---

# 5. Phase A1 — light量を広く地図化

Phase A1は進化OFF。初期個体を各光量へ合わせて人為的に救済しない。

phenotype:

```text
light_absorption = 2.0
chemical_absorption = 0.3
その他 = INITIAL_GENOME
全14遺伝子固定
```

environment:

```text
light-only
light_pattern=vertical
chem_vent_flux=0
placement=random
cycle ON
density response ON
```

候補:

```text
light_max = 0.8, 1.2, 1.5, 1.8, 2.1, 2.4, 3.0, 4.0
```

各:

```text
seed=1..5
ticks=10,000
```

総run:

```text
8 × 5 = 40 run
```

### 5.1 必須観測

各水準で:
- COMPLETE / EXTINCT / POP_HALT
- population trajectory / late median
- births / deaths / starvation
- births in final 2,000 tick
- generation
- flow_light / org-tick
- daytime Energy gain
- night Energy decline / survival
- light utilization fraction
- mean_move_per_org_tick
- body energy distribution
- cycle phase別population/Energy

### 5.2 robust viability

1つのlight水準を`ROBUST_LIGHT_VIABLE`とする条件:

```text
A. COMPLETE >= 4/5
B. EXTINCT <= 1/5
C. POP_HALT = 0/5
D. final 2,000 tick内にbirth > 0 のseed >= 4/5
E. late population median >= 25 (= initial_populationの25%) のseed >= 4/5
F. night light gain = exactly 0
G. conservation/integrity OK
```

25は「1〜数個体が残っただけ」を頑健成立と誤認しないための事前 operational floor。自然界の適正個体数を意味しない。

### 5.3 selected light

全8水準を必ず最後まで地図化する。途中PASSで上位水準を省略しない。

`selected_light_max`は:

> **ROBUST_LIGHT_VIABLEを満たす最小水準**

とする。

理由:
- light-onlyが成立する
- その中で過度に豊富なlightを避け、chemical nicheの価値を残しやすい
- 絶対値を「正解」とは主張しない

候補なし:

```text
LIGHT_CALIBRATION_FAIL / REVIEW
```

Phase Bへ進まない。

---

# 6. Phase A2 — chemical uptake 2次元地図

Phase A2も進化OFF。

phenotype:

```text
light_absorption = 0.3
chemical_absorption = 2.0
その他 = INITIAL_GENOME
全14遺伝子固定
```

environment:

```text
chemical-only
light_max=0
chem_vent_flux=16
placement=vent
```

候補格子:

```text
chemical_uptake_half = 0.5, 1.5, 3.0, 6.15
chem_uptake          = 0.5, 1.0, 2.0, 4.0
```

全組合せ:

```text
4 × 4 = 16 combinations
seed=1..3
ticks=5,000
48 run
```

### 6.1 必須観測

- COMPLETE / EXTINCT / POP_HALT
- population / births / starvation
- chemical gain / org-tick
- vent stock distribution
- vent occupancy
- `H(C,K)` realized distribution on occupied vent cells
- depletion depth
- recovery after local use falls
- source / loss / uptake ledger
- Energy capacity clipping fraction

### 6.2 grid admissibility

combinationを`CHEM_GRID_ADMISSIBLE`とする条件:

```text
A. COMPLETE >= 2/3
B. final 1,000 tick内にbirth > 0 のseed >= 2/3
C. POP_HALT = 0/3
D. occupied-vent organism-timeでのgroup median H(C,K) が 0.10〜0.90
E. min median vent stock <= 0.7 * biological-free C_eq をseed >=2/3で満たす
F. conservation/integrity OK
```

Dはhalf-saturation responseが実運転点から完全に外れていないことを見る。

### 6.3 selected chemical pair

admissible combinationの中から:

1. **最小`chem_uptake`**を優先
2. 同じ`chem_uptake`内では、occupied ventのgroup median `H(C,K)`が0.5に最も近い`chemical_uptake_half`
3. tieは小さい`chemical_uptake_half`

を選ぶ。

これは「chemicalを最大強化する」のではなく、**成立する最小処理能力と、実濃度帯に合うhalf-saturation**を選ぶ規則。

候補なし:

```text
CHEMICAL_CALIBRATION_FAIL / REVIEW
```

---

# 7. Phase A2b — selected chemical pairの長期/探索検証

A2で選ばれたpairを固定し:

### vent placement

```text
seed=1..5
ticks=10,000
```

### random placement

```text
seed=1..5
ticks=10,000
```

総run:

```text
10 run
```

vent側HARD:

```text
COMPLETE >=4/5
birth in final 2k >=4/5
clear depletion >=4/5
integrity OK
```

random placementはHARD gateにしない。探索コスト診断:
- time_to_first_birth
- starvation deaths
- movement
- vent_cell_frac
- chemical gain/org-tick

を記録する。

### BURST_RATIOについて

`chemical / light = X倍`というratioを選定HARD GATEにしない。

同じ最初1,000 tick窓でのper-org gainや、単独個体理論最大取得速度を**診断値**として出してよいが、selected pairは生態成立・depletion・実運転点から決める。

---

# 8. Phase A3 — chemical密度競争mechanism check

selected chemical pairを使用。

```text
initial_population = 1, 10, 50
placement=vent
seed=1..3
ticks=2,000
```

9 run。

PASS方向:
- 密度増加でper-capita chemical gainが低下
- 総gainはstock/source制約を超えない
- 高密度ほどvent stockが低下
- conservation OK

方向が逆なら`INTEGRITY_OR_MECHANISM_REVIEW`としてPhase Bへ進まない。

---

# 9. Phase A run数

正式simulation:

```text
A1 light map               40
A2 chemical grid           48
A2b selected validation    10
A3 density                  9
--------------------------------
Phase A total             107 run
```

Phase 0の短時間testは別。

A1/A2はそれぞれmatrix並列化可能だが、selected値依存のA2b/A3はA2終了後に実行する。

---

# 10. Phase A verdict

```text
A_PASS
LIGHT_CALIBRATION_FAIL / REVIEW
CHEMICAL_CALIBRATION_FAIL / REVIEW
INTEGRITY_OR_MECHANISM_REVIEW
```

`A_PASS`のときのみ:

```text
selected_light_max
selected_chemical_uptake_half
selected_chem_uptake
```

を機械可読artifactへ固定しPhase Bへ渡す。

Phase B開始後に候補値・選定規則を変更しない。

---

# 11. Phase B1 — light-only長期成立

```text
light-only
selected_light_max
light specialist
全14遺伝子固定
random placement
seed=1..8
ticks=20,000
```

8 run。

見るもの:
- COMPLETE
- ongoing birth
- population
- starvation
- night survival
- flow/light utilization
- movement

---

# 12. Phase B2 — chemical-only長期成立

```text
chemical-only
selected chemical pair
chemical specialist
全14遺伝子固定
random placement
seed=1..8
ticks=20,000
```

8 run。

見るもの:
- COMPLETE
- ongoing birth
- vent discovery/occupancy
- stock depletion/recovery
- population
- chemical flow
- starvation/movement

B1/B2のpopulation絶対値を「どちらが優秀か」の順位には使わない。

---

# 13. Phase B3 — mixed-world exploratory evolution

```text
light + chemical ON
selected parameters
initial genome = current generalist (light=0.3 / chemical=0.3)
進化ON = light_absorption, chemical_absorption の2遺伝子のみ
その他12遺伝子固定
bmr_core=0.15
seed=1..12
ticks=30,000
```

12 run。

目的:
- 両routeに実利用価値が残るか
- 片方へ完全に一方向化するか
- 資源利用戦略の分化兆候

観測:
- light/chemical absorption mean/variance
- lineage別Energy flow
- late primary-Energy source share
- vent占有
- daylight/night activity
- lineage share
- 2遺伝子scatter / clustering（診断のみ）

二峰性や共存をV1.8 ACCEPTの必須条件にはしない。ただし、片routeが実質利用されない場合は`SOURCE_BALANCE_REVIEW`として次チャットで人間判断する。

---

# 14. Phase B4 — day/nightによるbody_size圧の診断

V1.8 ACCEPTのHARD GATEではないが必須診断。

## B4a Exp12平衡付近の固定小型個体

```text
light-only
selected_light_max
light specialist
body_size = 0.246 fixed
全遺伝子固定
initial_matter = 0.8 * 0.246 = 0.1968
initial_energy = 標準初期状態と同じEnergy-capacity fractionになる値
seed=1..3
ticks=5,000
```

3 run。

目的:
- Exp12で成立した小型側が100 tick night下で生存可能か直接確認

## B4b body_size-only evolution

```text
light-only
selected_light_max
light specialist
initial body_size=1.0
進化ON=body_sizeのみ
他13遺伝子固定
seed=1..5
ticks=20,000
```

5 run。

目的:
- day/night導入でbody_sizeがどの方向へ動くか
- Exp12の0.2459平衡がV1.8でも維持されるか

---

# 15. Phase B run数 / Exp13総run数

```text
B1 light-only       8
B2 chemical-only    8
B3 mixed           12
B4a small fixed     3
B4b body evolution  5
----------------------
Phase B total       36

Phase A            107
Phase B             36
----------------------
Formal simulation  143 run
```

Phase 0短時間E2Eはこの143に含めない。

---

# 16. Exp13判定

## `V1_8_ACCEPT_CANDIDATE`

少なくとも:

```text
1. Phase 0全Green
2. Phase A = A_PASS
3. A3 competition direction PASS
4. B1 COMPLETE >= 6/8
5. B1 final 4kでbirthあり >= 6/8
6. B2 COMPLETE >= 6/8
7. B2 final 4kでbirthあり >= 6/8
8. conservation / Config / SHA / numeric environment / artifact integrity violation 0
```

を満たす。

## `V1_8_RECALIBRATE / REVIEW`

- B1/B2どちらかが5/8以下
- selected pairが長期で成立しない
- density competitionが想定方向に出ない
- mixed worldで片routeが実質無意味になる

場合。

## `INTEGRITY_FAIL`

- expected run欠落/重複
- Config不整合
- SHA/numeric environment混在
- ledger/conservation violation
- aggregation failure

技術的不完了と科学的REVIEWを混同しない。

B3/B4の詳細解釈とV1.8恒久採用の人間判断は、Exp13完了後の**V1.8チャット**で行う。

---

# 17. workflow設計

推奨依存:

```text
phase0
  -> A1_light_map
  -> A2_chemical_grid
  -> select_A
  -> A2b_selected_validation + A3_density
  -> phaseA_collect
  -> phaseB (B1/B2/B3/B4)
  -> final_collect
```

A1とA2はPhase 0後に並列開始してよい。

requirements:
- generated manifest
- human-handwritten Config複製禁止
- selected parameter artifactをBへ渡す
- selected artifact空ならfail-fast
- many-artifact取得は完全性を保証する方法（`gh run download`等）
- expected key完全一致
- timeout / max-parallelはruntime preflight後に設定
- Drive転送はcollect成功後

---

# 18. 実装・集計で必ず残す値

Phase A/B共通:
- run status
- Config hash
- git SHA
- numeric environment key
- wall time / existing performance data
- population / births / deaths / generation
- Energy/Matter ledger
- flow_light / flow_chemical
- light_supply actual integral
- vent stock / occupancy
- realized H values

Exp13結果では:
- 全light sweep表
- chemical 2D grid表/heatmap
- selected valuesと選定根拠
- B1/B2 long-term
- B3 exploratory
- B4 body_size diagnostic
- runtime prediction vs actual

をGitHubへ保存する。
