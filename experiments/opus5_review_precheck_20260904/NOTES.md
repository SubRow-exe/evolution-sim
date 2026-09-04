# Opus 5 レビュー時 事前実走チェック — 実測NOTES

更新: 2026-09-04

> **これは正式実験ではない。** `docs/実験結果保存方針.md` の対象となる formal experiment ではなく、
> `docs/Exp15_実験計画確定.md` の条件を formal dispatch 前にローカルで走らせ、
> **判定が両側へ振れうるか**を確認した feasibility 検証である。
> Exp番号を持たず、恒久parameter選定の根拠にも使わない。

考察の正本: `docs/Exp14結果_Exp15計画_Opus5レビュー.md`

---

## 1. 実行条件

```text
コード       : main SHA e19988f (V1.8実装済み。evosim には一切変更を加えていない)
実行経路     : ローカル (GitHub Actions ではない)
ticks        : 1,500
seed         : Phase A / energy等価arm = 1..3、Phase B / remedy = 1..2
run数        : 合計 41
表現型       : light specialist (light_absorption=2.0 / chemical_absorption=0.3)
               全14遺伝子固定 (進化OFF)
共通条件     : docs/Exp15_実験計画確定.md §3 をそのまま使用
```

`docs/Exp15_実験計画確定.md` §4 の表現型 HARD GATE を再現するため、
各runで `Simulation(cfg, seed)` 初期化後に初期100個体すべての
`light_absorption == 2.0` を assert している。

再現:

```bash
uv run python experiments/opus5_review_precheck_20260904/run_precheck.py 1500
```

raw出力: `raw_output.txt`

---

## 2. 結果

### 2.1 Exp15 Phase A 2×2 (`light_max=1.2`)

| arm | cycle | density | 周期平均供給 | 結果 | final pop | max_gen |
|---|---|---|---:|---|---|---|
| A0 | OFF | OFF | 0.780 | REACHED | 807 / 831 / 829 | 8 / 6 / 6 |
| A1 | OFF | ON | 0.780 | REACHED | 807 / 830 / 820 | 8 / 7 / 7 |
| A2 | ON | OFF | 0.248 | EXTINCT 165 / 171 / 171 | 0 | − |
| A3 | ON | ON | 0.248 | EXTINCT 165 / 171 / 171 | 0 | − |

**A1 は A0 と、A3 は A2 と、seed1 で数値まで一致した**（pop 807 / 絶滅tick 165）。

`light_max=1.2` では

```text
demand = light_uptake_coef(2.0) × light_absorption(2.0) × A_eff × H(I,0.6)
supply = I
demand ≥ supply ⟺ I ≤ 2.0×2.0×A_eff − 0.6 = 3.4  (M=1)
```

で世界中どこでも供給律速となり、同一cell内の全個体に同じ `H` が掛かるため
需要比例配分 `gain_i = supply × raw_i / Σraw_i` で `H` が約分されて消える。
**この光スケールでは density response は定義上不活性である。**

### 2.2 energy等価な昼夜arm（Exp15 には無い。レビューで追加）

`light_max = 1.2 / 0.31831 = 3.7699` とすると、周期平均供給が A0 と厳密に一致する。

| arm | cycle | density | `light_max` | 周期平均供給 | 結果 |
|---|---|---|---:|---:|---|
| A0 | OFF | OFF | 1.2 | 0.780 | REACHED pop 830 / gen 8 |
| **A2′** | **ON** | OFF | **3.7699** | **0.780** | **EXTINCT 380 / 381 / 399** |
| A3′ | ON | ON | 3.7699 | 0.780 | EXTINCT 571 / 560 / 362 |

**時間平均の光取得が厳密に同一でも、昼夜があるだけで絶滅する。**

### 2.3 Exp15 Phase B の `light_max` 掃引（cycle + density ON）

| `light_max` | 結果 |
|---:|---|
| 2.4 | EXTINCT 373 / 379 |
| 4.0 | EXTINCT 404 / 377 |
| 8.0 | EXTINCT 392 / 389 |
| 12.0 | EXTINCT 376 / 377 |

**光量5倍で絶滅tickが 373 → 377。掃引軸として完全にフラットである。**

絶滅tickは夜の整数倍に量子化している。

```text
夜1 = tick 100–200  ->  light_max=1.2      絶滅 165–171
夜2 = tick 300–400  ->  light_max 2.4以上  絶滅 373–404
```

### 2.4 remedy候補（`light_max=4.0` / combined 固定、1軸ずつ）

| remedy | 変更 | 周期平均light | 結果 | final pop | max_gen |
|---|---|---|---|---:|---:|
| R0 | baseline | ×1.00 | EXTINCT 404 / 377 | 0 | − |
| R1 | `repro_energy_frac` .6→.80 | ×1.00 | REACHED | 34 / 18 | 6 |
| R2 | `energy_capacity` 100→300 | ×1.00 | REACHED | 648 / 657 | 4 |
| **R3** | **`period` 200→80（夜100→40）** | **×1.00** | **REACHED** | **958 / 981** | **9 / 8** |
| R4 | `day_fraction` .5→.8（夜100→40） | ×1.60 | REACHED | 2764 / 2790 | 9 |
| R5 | R1 + R2 | ×1.00 | REACHED | 442 / 419 | 4 |

**`light_max` 以外の4軸はいずれも単独で救済した。**

とくに R3 は周期平均光量が R0 と完全に同一で、夜の長さだけを 100→40 に変えている。
それで絶滅（tick 390）から pop 970 / 世代9 へ反転する。

---

## 3. この検証から言えること / 言えないこと

### 言える

1. `light_max=1.2` では density response が不活性なので、Exp15 Phase A の A1 / A3 は情報を持たない
2. 昼夜の害は「平均光量の減少」ではなく「時間構造そのもの」である（A0 vs A2′）
3. 致命的な変数は夜の長さである（R0 vs R3。平均光量を固定して夜長だけ変えると反転する）
4. Exp15 Phase B の `light_max` 掃引には成立域が存在しない見込みが高い
5. `period` / `energy_capacity` / `repro_energy_frac` はいずれも救済軸になりうる

### 言えない

1. **1,500 tick は Exp15 の target（Phase A 5,000 / Phase B 10,000）より短い。**
   「REACHED」は短期の非崩壊であって長期成立ではない
2. seed 2〜3本なので、seed間ばらつきの評価には足りない
3. GitHub Actions ではなくローカル実行なので、数値実行環境が formal と一致しない
   （`docs/数値再現性・Actions実行環境方針.md` の formal 基準を満たさない）
4. remedy の値（`period=80` 等）は working reference の候補ではない。
   救済**方向**を示しただけで、選定は事前登録した正式実験で行うべきである
5. 進化OFF・固定表現型の結果なので、進化を許した場合の挙動は含まない

**したがってこの結果で恒久parameterを決めてはいけない。**
Exp15 の設計を dispatch 前に見直すための材料としてのみ使う。

---

## 4. 出力物

```text
run_precheck.py   再現スクリプト (evosim には変更なし)
raw_output.txt    41 run の raw 出力
NOTES.md          本書
```

集計プロットは作成していない。表が小さく、`raw_output.txt` から直接読めるためである
（`docs/実験結果保存方針.md` §4 の「可視化不要な場合は理由を明記」に該当）。
