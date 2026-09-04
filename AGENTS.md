# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/V1.9_現状ステータス.md` — **現在地・権限の正本**
2. `docs/V1.9_物理スケール再校正方針.md` — **CURRENT DESIGN / arbitrary unit再校正の正本**
3. `docs/V1.9_iLUCA再設計仕様.md` — V1.9機構仕様。旧numeric implementation referenceはphysical scaling正本に従い再校正対象
4. PR #67 `docs/V1.9_実装報告.md` — 機構実装checkpoint / Energy収支ギャップ
5. `docs/Exp15_V1.9_実験計画案.md` — physical gate後のformal skeleton / **DO NOT DISPATCH**
6. `docs/次の実験計画.md` — 現在の司令塔
7. `docs/V1.8_総括.md`
8. `docs/環境因子追加・校正方針.md`
9. `docs/バージョニング方針.md`
10. `docs/メインストリーム開発ストーリー.md`
11. `docs/実験結果保存方針.md`
12. `docs/数値再現性・Actions実行環境方針.md`

過去のExp15計画・V1.9旧numeric reference・historical experimentより上記を優先する。

---

# 2. 現在地

```text
V1.8 scientific phase         CLOSED
old V1.8 Exp15                SUPERSEDED / DO NOT DISPATCH
V1.9 mechanism design         CLOSED
V1.9 mechanism implementation PR #67 / checkpoint complete
V1.9 physical scaling         CURRENT REVIEW / DESIGN TASK
Exp15                         SKELETON ONLY / PAUSED
```

PR #67は17 genes / 1-pool Energy / runway homeostasis / H2 explicit / capability gate等を実装し、tests・conservation・determinism・CIまで通っている。

ただし旧arbitrary-unit referenceではfixed iLUCAがresource-rich条件でも恒常Energy赤字となったため、その数値スケールはFINALとしない。

---

# 3. V1.9の目的

V1.9 = **より妥当なchemical-first iLUCA baselineの再構築**。

環境側を生存に合わせて曲げるのではなく、生物自身が自然な環境圧へ生理・進化で応答できる構造を作る。

機構:

```text
INITIAL light_absorption = 0
INITIAL predation_efficiency = 0
Energy = 1-pool
storage_capacity gene + cost
starvation signal = runway / starvation_horizon
reproduction gate = runway >= reproduction_horizon
H2 explicit / CO2 implicit
H2 diffusion halo
uniform random initial spawn
phototrophy = structural innovation gated
predation = V1.9 locked
```

V1.8 day/nightは残す。

---

# 4. physical scaling HARD RULE

今後、旧arbitrary値を「生存するまで調整」しない。

可能な範囲で物理単位・生物学的オーダーから定義する。

確定:

```text
time unit = second [s]
standard dt = 10 s
light cycle = 24 h
reference day/night = 12 h / 12 h
memory_tau reference = 20 s
starvation_horizon initial = 1800 s
reproduction_horizon initial = 3600 s
resource-rich iLUCA doubling-time sanity order = 4–8 h, reference ≈6 h

H2 concentration = mol/m^3
H2 amount        = mol
H2 flux          = mol/s
H2 uptake        = mol/s/organism
vent H2 source-fluid reference ≈10 mM
D_H2 reference ≈5e-9 m^2/s near 25°C
```

旧:

```text
E/tick
substrate/tick
wu
h2_conversion_eff=0.60 as final
h2_uptake_coef=0.5 as final
bmr_core=0.15 E/tick as final
```

をphysical V1.9の最終尺度として使わない。

---

# 5. 現在の未決S1〜S5

Exp15前に人間レビューが必要。

```text
S1 iLUCA reference cell size / dry mass
S2 world/grid cell/effective depth/voxel physical scale
S3 Matter <-> dry biomass scale and growth energetics
S4 movement speed / power physicalization
S5 dt convergence / invariance criteria
```

これらが確定するまでH2 source mol/s・specific uptakeの個体換算・maintenance/growth/movement収支はFINAL化しない。

---

# 6. V1.9 homeostasis HARD RULE

未来情報を使わない。

```text
NG: 日没が近いから活動を止める
NG: 将来のEnergy収益を予測して貯蔵する
OK: 現在Energyと現在full-activity支出からrunwayを計算する
OK: runway不足に応じて現在代謝を調節する
```

- BMR可変部/repairは強く抑制
- H2/light/nutrient uptakeは弱く抑制
- structural/core maintenanceは残す
- movementはV1.9 starvation responseでは直接抑制しない

runway/horizonの正本単位はphysical scaling後 **seconds**。

---

# 7. H2 environment HARD RULE

H2はEnergyそのものではなくsubstrate。

```text
H2 [mol]
 -> uptake [mol/s]
 -> chemical free energy [J/s]
 -> biologically usable power [W]
 -> cellular Energy [J]
```

vent:

- equal source definition
- world edge clippingなし
- source region非重複
- fixed
- V1.9ではvent間の意図的静的flux差なし

H2:

- physical concentration
- diffusion based on D [m^2/s], dt, dx
- explicit consumption
- halo/gradient

baseline initial spawnはworld uniform random。

---

# 8. Structural innovation HARD RULE

continuous mutationと能力起源を分離する。

```text
PHOTOTROPHY: innovation-gated
PREDATION:   V1.9 locked
```

PHOTOTROPHY OFFならLIGHT_ABSは機能上0。
PREDATION OFFならPREDATION geneの通常変異で捕食能力を再出現させない。

---

# 9. 進化可能性とsanityの区別

原則:

```text
fixed ancestor sanity
+
evolution-ON experiment
```

固定祖先が死んでも進化ONで適応可能なら環境FAILとは限らない。

ただし:

> resource-rich単独個体でも、進化可能レバーと無関係に必ずEnergy赤字となる場合は、adaptive pressureではなくscale/model不整合を先に疑う。

---

# 10. 現在AIが行ってよいこと

- PR #67実装レビュー
- physical scaling科学レビュー
- S1〜S5の検討
- scaling仕様/docs更新
- scaling patchの設計
- scaling用unit/conservation/dt tests設計

人間がS1〜S5を確定した後は、その仕様に沿うphysical scaling patch実装へ進んでよい。

---

# 11. 現在AIが勝手に行ってはいけないこと

- Exp15 formal dispatch
- arbitrary parameter sweep
- 生存させるためだけのenvironment/BMR/H2 tuning
- old `tick`値を10秒として機械的換算
- PR #67をphysical scaling未反映のままV1.9 finalとみなす
- phototrophy formal experiment
- V1.8 tuningへ戻る

---

# 12. 絶対設計原則

- 適応度関数を直接置かない
- 特定生態型への固定bonus/penaltyを置かない
- 将来予測を行動へ埋め込まない
- 保存則を破らない
- Recorderをsimulationへフィードバックしない
- same-seed determinismを守る
- 能力起源をcontinuous mutationの裏口で起こさない
- historical experimentを現在仕様へ書き換えない
- 生存するようarbitrary environment parameterを自動校正しない
- **現実スケール化できる量は可能な限りSI/physical unitで意味を定義する**

---

# 13. 次の手順

```text
1. Opus 5 review
2. S1 reference cell size/dry mass
3. S2 world/grid/voxel scale
4. S3 Matter/growth energetics
5. S4 movement power
6. physical scaling patch on PR #67
7. tests / conservation / determinism / dt sanity
8. V1.9 final review / merge
9. Exp15 formalization
```

formal experimentは人間の明示判断なしに開始しない。
