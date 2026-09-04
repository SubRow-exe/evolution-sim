# Exp14結果 / Exp15計画 — Opus 5レビュー（実走検証つき）

更新: 2026-09-04

レビュー対象（main SHA `e19988f` 時点）:
- `docs/V1.8_現状総括_Exp14結果.md`（commit `87241a7`）
- `docs/Exp14_表現型プロベナンス訂正.md`（commit `366fba5`）
- `docs/環境因子追加・校正方針.md`（commit `c57594f`）
- `docs/Exp15_実験計画確定.md`（commit `cd446de`）
- `docs/Exp15_実装チェックリスト.md`（commit `64bae4e`）

**本書は他のレビューと1点だけ性格が違う。**
`docs/Exp15_実験計画確定.md` の Phase A / Phase B を、**現行コードでそのままローカル実走して先に答えを出している。**
以下の実測は文書の引用ではなく、本レビュー時に `evosim` を回して得た結果である。再現スクリプトは §7 付録にある。

仕様・条件・閾値は一切変更していない。すべて変更提案として整理した。採否は人間判断。

---

# 0. 結論

**Exp15 Phase A は走らせる前に答えが出た。Phase B は走らせても答えが出ないことも分かった。**

現行コード・正しい light specialist（`light_absorption=2.0`）・Exp15 §3 の条件そのままで実走した結果:

| arm | cycle | density | `light_max` | 周期平均供給 | 実測結果（1,500 tick / 3 seed） |
|---|---|---|---:|---:|---|
| **A0** | OFF | OFF | 1.2 | 0.780 | **REACHED** pop 807 / 831 / 829、gen 8 / 6 / 6 |
| **A1** | OFF | **ON** | 1.2 | 0.780 | **REACHED** pop 807 / 830 / 820、gen 8 / 7 / 7 |
| **A2** | **ON** | OFF | 1.2 | 0.248 | **EXTINCT** 165 / 171 / 171 |
| **A3** | **ON** | **ON** | 1.2 | 0.248 | **EXTINCT** 165 / 171 / 171 |
| **A2′** | **ON** | OFF | **3.770** | **0.780（A0と同一）** | **EXTINCT** 380 / 381 / 399 |
| A3′ | ON | ON | 3.770 | 0.780 | EXTINCT 571 / 560 / 362 |

（A2′ / A3′ は Exp15 には無い、本レビューが追加した **energy等価**の昼夜arm。
`light_max = 1.2 / 0.31831 = 3.770` で周期平均供給を A0 と厳密に一致させてある。）

ここから3つの事実が出る。

> **① 密度応答（density response）は `light_max=1.2` では完全に不活性である。**
> A1 は A0 と、A3 は A2 と、seed1 で**数値まで同一**（pop 807 / 絶滅tick 165）。
> Phase A の科学arm 4本のうち **2本（A1・A3）は情報を持たない。**
>
> **② 昼夜は「平均光量の減少」ではなく「時間構造そのもの」で殺している。**
> A0 と A2′ は**時間平均の光取得が厳密に同一**なのに、A0 は pop 830 で世代8まで回り、
> A2′ は 3 seed とも約390 tickで絶滅する。
>
> **③ Phase B の `light_max` 掃引は飽和しており、成立域は存在しない。**

Phase B（cycle+density ON、Exp15 §9 と同じ条件）を先に走らせた結果:

| `light_max` | 実測（1,500 tick / 2 seed） |
|---:|---|
| 2.4 | EXTINCT 373 / 379 |
| 4.0 | EXTINCT 404 / 377 |
| 8.0 | EXTINCT 392 / 389 |
| 12.0 | EXTINCT 376 / 377 |

**光量を5倍（2.4 → 12.0）にしても絶滅tickは 373 → 377 でほぼ動かない。**
したがって Exp15 Phase B（6水準 × 3 seed = 18 run）は、
事前登録された選定規則に照らして **`NO_ROBUST_LIGHT_REFERENCE` を返すことがほぼ確実**である。

さらに絶滅tickは**夜の整数倍に量子化している**。

```text
夜1 = tick 100–200   -> A2 (light_max=1.2)      絶滅 165–171
夜2 = tick 300–400   -> light_max 2.4 以上すべて 絶滅 373–404
```

**光を増やすと「もう一晩だけ」買える。それ以上は何も買えない。**
これは前回レビュー（`docs/Exp14_Opus5レビュー.md`）で示した
「夜の生存は貯蔵容量 `0.6 × E_max` で頭打ちで、`light_max` は式に入らない」
という診断の直接的な実証である。

> **④ `light_max` 以外の軸なら救済できる（§3-2 で実走確認）。**
> `light_max=4.0` を固定したまま、`period` を 200→80（夜100→40、**周期平均光量は不変**）に
> するだけで、絶滅（tick 390）から pop 970 / 世代9 の成立へ反転する。
> `energy_capacity` 100→300、`repro_energy_frac` .6→.80 でも同様に救済される。

以上を1行でまとめると:

> **V1.8 light世界を殺しているのは「光の量」ではなく「夜の長さ」である。
> そして Exp15 は、唯一効かない軸（`light_max`）だけを掃引しようとしている。**

---

# 1. Exp14 の読み方 — 表現型訂正が最重要

## 1-1. `docs/Exp14_表現型プロベナンス訂正.md` は正しい。そして影響は文書が書くより大きい

`tools/make_exp14_configs.py` には `diagnostic_gene_overrides` が**1箇所も無い**
（`tools/make_exp13_configs.py` には `LIGHT_SPECIALIST` として存在する）。
コードで確認した。したがって Exp14 formal 116 run は
`light_absorption = 0.3`（`INITIAL_GENOME`）で走っている。

これは「6.7倍弱い」だけの話ではなく、**律速が入れ替わる**。

```text
demand = light_uptake_coef(2.0) × light_absorption × A_eff × H(I,K)
supply = I

light_absorption = 2.0 -> demand = 4.0·H  ;  demand ≥ supply ⟺ I ≤ 3.4
light_absorption = 0.3 -> demand = 0.6·H  ;  demand ≥ supply ⟺ I ≤ -0.24 → 常に demand律速
```

つまり:

- **意図した light specialist（2.0）: 供給律速。`H` は取得量を一切減らさない**
- **実際に走った表現型（0.3）: 需要律速。`H` が取得量を直接減らす**

`light_absorption=0.3`、`M=1`、A1 の平均cell（`I=0.827`）で:

```text
income  = 0.6 × H(0.827,0.6) = 0.6 × 0.579 = 0.347
支出    = 維持費(organ_sum=1.35) 約0.436 + repair 約0.045 = 約0.48
-> 恒常的に赤字 (−0.13 E/tick)
```

**だから Exp14 は夜を消した A1 でも死に、Generation 2 が一度も成立しなかった。**
Exp14 の絶滅は Exp13 の絶滅と**機構が違う**。

> Exp13 = 供給律速で収支は黒字だが、**夜の貯蔵が足りない**（前回レビューの診断）
> Exp14 = 需要律速で**そもそも昼でも赤字**（表現型バグ由来）

## 1-2. `docs/V1.8_現状総括_Exp14結果.md` §9 の修正が必要

§9 は

> 「V1.8のdensity responseをONにした低強度continuous-light条件では、夜がなくても成立しなかった」

と結論している。方向としては訂正済みだが、**まだ強すぎる**。

本レビューの実走では、**正しい light specialist なら A1（cycle OFF / density ON / `light_max=1.2`）は
1,500 tick を pop 820〜830、世代7〜8 で完走する。** つまり:

```text
誤: density response ON の continuous light では成立しない
正: light_absorption=0.3 という需要律速の表現型では成立しなかった。
    light_absorption=2.0 では density response ON でも問題なく成立する。
```

§9 は「A1はV1.7回帰ではない」という指摘までは正しいが、
**その先の「density responseが効いた可能性」は、light specialist では成立しない。**

→ §9 に本レビューの A0/A1 実測を追記し、
「density response の寄与は表現型依存であり、light specialist では `I ≤ 3.4` の全域で不活性」
と明記することを提案する。

## 1-3. 維持できる Exp14 の知見／撤回すべき知見

訂正文書 §3・§4 の切り分けは適切である。1点だけ補強する。

Exp14 で観測された

```text
- cycle を消すと寿命が延びた
- storage capacity 増加で一晩越しが改善した
- tick1繁殖抑制が延命方向だった
```

の3点は、**本レビューの light specialist 実走でも同じ向きが再現した**（§0 の表、および §3 の remedy）。
表現型が違っても方向は保存されているので、**定性的には維持してよい**。
ただし訂正文書が言うとおり定量値は使えない。

---

# 2. Exp15 Phase A のレビュー

## 2-1. 支持する点

- **2×2 の機構切り分けは正しい設計**である（前回 V1.8 レビュー S-2 で提案した内容と一致）
- **表現型 HARD GATE（§4）が非常に良い。** `Simulation(cfg, seed)` を実際に初期化して
  初期100個体すべての `light_absorption == 2.0` を assert する、というのは
  Exp14 の再発を機械的に止める正しい設計である。本レビューの実走スクリプトにも同じ assert を入れた
- **A4 duplicate sentinel** は Exp14 を踏まえた良い追加
- Phase A → Phase B の自動遷移禁止（§9・§15）
- `docs/環境因子追加・校正方針.md` の「唯一の最適値を探さない / working reference で先へ進む」は
  Exp11・Exp12 で繰り返した過剰精密化への正しい是正である。**プロジェクト全体方針として支持する**

## 2-2. MUST FIX ①: A1 / A3 は情報を持たない（実測で確認）

§0 のとおり、`light_max=1.2` では A1 ≡ A0、A3 ≡ A2 になる。理由は解析的にも明快である。

```text
demand ≥ supply ⟺ light_uptake_coef × light_absorption × A_eff ≥ I + light_uptake_half
              ⟺ I ≤ 2.0 × 2.0 × A_eff − 0.6
M=1 (A_eff=1) なら I ≤ 3.4
```

`light_max=1.2` では cell の光は最大でも 1.2 なので、**世界中どこでも供給律速**。
供給律速のとき、同一cell内の全個体に同じ `H(I,K)` が掛かるため、
需要比例配分 `gain_i = supply × raw_i / Σraw_i` で **`H` は約分されて完全に消える。**

したがって Phase A は、設計上は 2×2 だが**実質 1×2（cycle の ON/OFF）にしかならない**。

### 変更提案（MUST FIX）

density 軸を、`H` が実際に効く光スケールでも測る。

```text
Phase A へ2 arm追加（+10 run）
  A1b: cycle OFF / density ON  / light_max = 4.0   (I > 3.4 の領域を含む)
  A0b: cycle OFF / density OFF / light_max = 4.0   (A1b の対照)

  -> A0b vs A1b の差が density response の真の寄与
```

あるいは Phase A 全体を `light_max=1.2` と `4.0` の2スケールで回す。

**「`light_max=1.2` は V1.7 の historical scale だから」という §5 の理由は、
density 軸に関しては逆効果である。** そのスケールでは density 機構が定義上眠っている。

## 2-3. MUST FIX ②: energy等価な昼夜arm が無い（最も情報量が高い1本）

Exp15 の A2 / A3 は `light_max=1.2` のまま cycle を ON にするので、
**周期平均供給が 0.780 → 0.248 へ 3.14分の1 になる。**
維持費（light specialist、M=1）は約 0.569 なので、**平均収支が最初から赤字**である。

したがって A2 / A3 の崩壊は「昼夜という時間構造」ではなく
「平均光量が維持費を下回った」ことで説明が付いてしまい、**2要因が交絡する。**

本レビューが追加した **A2′（cycle ON / density OFF / `light_max=3.770`）** はこれを分離する。

```text
A0  : static, 周期平均供給 0.780  -> REACHED  pop 830 / gen 8
A2′ : cycle , 周期平均供給 0.780  -> EXTINCT  380 / 381 / 399
```

**時間平均の光取得は厳密に同一。** それでも一方は世代8まで回り、一方は約390 tickで全滅する。

> **昼夜は平均エネルギーを削るから危険なのではない。時間的に偏らせるから危険なのである。**

これは V1.8 の設計思想（`docs/V1.8_一次Energy生態非対称仕様.md` §11「sourceの物理的性質だけで
異なる生活史trade-offが生まれるか」）にとって**むしろ良い結果**である。
昼夜は確かに質的に異なる圧を作っている。強すぎるだけである。

### 変更提案（MUST FIX）

```text
Phase A へ A2′ を追加する（+5 run、seed 1..5）
  cycle ON / density OFF / light_max = 1.2 / mean_daylight_factor = 3.770

判定への使い方（事前登録）:
  A2′ が A0 と同程度に成立 -> 昼夜の害は「平均光量の減少」が主因
                             -> Phase B の light_max 掃引に意味がある
  A2′ が崩壊              -> 昼夜の害は「時間構造」が主因
                             -> light_max 掃引では解決しない。Phase B の軸を変える
```

**この1 arm が Phase B を走らせる価値があるかどうかを決める。**
そして本レビューの実測では、**後者（崩壊）である。**

## 2-4. SHOULD FIX: Phase A の HARD GATE は通る（先に確認済み）

§6 の科学 HARD GATE は「A0 が `ROBUST_SHORT` か `OVERDRIVEN` でなければ `BASELINE_NOT_VIABLE` で停止」である。

実走では A0 は 3/3 seed が 1,500 tick 完走、pop 807〜831、`max_generation` 6〜8 だった。
Exp15 の target は 5,000 tick なので断定はできないが、
**個体数も世代交代も健全に回っており、`BASELINE_NOT_VIABLE` になる兆候は無い。**

なお A0 は 1,500 tick 時点でまだ増加傾向にあるが、`OVERDRIVEN` にはならない見込みである。

```text
世界の総light供給   = 1.2 × (0.3+1.0)/2 × 1600 cell = 1,248 E/tick
1個体の維持費(M=1) ≈ 0.569 E/tick
-> 光律速の収容力  ≈ 1,248 / 0.569 ≈ 2,200 個体
```

`max_population_halt = 10000` には届かないので、5,000 tick でも `REACHED_TARGET` になるはずである。
ただし収容力付近では個体あたり取得が維持費へ張り付くので、
**A0 の「成立」は余裕のある成立ではなく収容力上限での成立**である点は、
A1〜A3 と比較する際に意識したほうがよい。

---

# 3. Exp15 Phase B のレビュー

## 3-1. MUST FIX ③: Phase B は設計どおり走らせても `NO_ROBUST_LIGHT_REFERENCE` になる

§0 の実測のとおり、cycle+density ON で `light_max` を 2.4 → 12.0（5倍）にしても
絶滅tickは 373 → 377 でほぼ変化しない。

Exp15 §10 の分類に当てはめると:

```text
全水準 0/3 VIABLE_SEED -> COLLAPSE_LEVEL
VIABLE_LEVEL が0個     -> §11「選定しない条件」に該当
                       -> SCIENTIFIC_VERDICT = NO_ROBUST_LIGHT_REFERENCE
```

**18 run・180,000 tick を投じて、この結論が出る。**

しかも `docs/環境因子追加・校正方針.md` §2.2 の成立条件5
「極端に狭い一点だけで成立する knife-edge ではなく、ある程度の parameter 幅で挙動が成立する」
に照らすと、`light_max` 軸には **edge すら存在しない**（完全に平坦）。
方針が求める「幅のある成立域」は、この軸上に原理的に無い。

### なぜ平坦なのか

前回レビューの診断がそのまま効いている。

```text
夜の生存 tick = 到達可能 reserve / 夜の支出
到達可能 reserve = repro_energy_frac × energy_capacity × matter = 0.6 × 100 × M
夜の支出 = maintenance + move + repair   (light_max を含まない)
```

`_try_reproduce` は `E ≥ 0.6·E_max` になった瞬間に必ず発火して余剰を子へ吐き出すため、
**昼をどれだけ明るくしても日没時の貯金は `0.6·E_max` を超えない。**
増えるのは個体数（＝その夜に死ぬ子）だけである。

### 変更提案（MUST FIX）

Phase B の**掃引軸を `light_max` から差し替える**ことを提案する。

```text
現状: light_max = 1.2, 2.4, 4.0, 6.0, 8.0, 12.0   (6水準 × 3 seed = 18 run)
        -> 実測上フラット。情報を持たない

提案: light_max は Phase A で成立した水準に固定し、
      「夜を越せるか」を決める軸を掃引する
        軸候補（§3-2 の remedy 実測で優先順位を決める）
          - repro_energy_frac        (到達可能 reserve の上限)
          - energy_capacity          (貯蔵容量そのもの)
          - light_day_fraction / period (夜の長さ)
```

`light_max` は Phase B から外さずに1〜2水準だけ残し、
「主軸ではないこと」を実測で示すための対照にするのが安全である。

## 3-2. どの軸なら効くか — remedy 実測

`light_max=4.0` / cycle+density ON を固定し、**他を1つずつだけ**変えて実走した（1,500 tick / 2 seed）。

| remedy | 変更 | 周期平均light | 結果 | final pop | max_gen |
|---|---|---|---|---:|---:|
| **R0** | baseline（Phase B `light_max=4.0`） | ×1.00 | **EXTINCT** 404 / 377 | 0 | −1 |
| **R1** | `repro_energy_frac` .6 → .80 | ×1.00 | **REACHED** | 34 / 18 | 6 |
| **R2** | `energy_capacity` 100 → 300 | ×1.00 | **REACHED** | 648 / 657 | 4 |
| **R3** | `period` 200 → 80（夜 100 → 40） | **×1.00** | **REACHED** | 958 / 981 | 9 / 8 |
| **R4** | `day_fraction` .5 → .8（夜 100 → 40） | ×1.60 | **REACHED** | 2764 / 2790 | 9 |
| **R5** | R1 + R2 | ×1.00 | **REACHED** | 442 / 419 | 4 |

**`light_max` 以外の4つの軸は、どれも単独で救済に成功した。**

とくに **R3 が決定的**である。

```text
R0 : period 200 / 夜100  周期平均light ×1.00  -> EXTINCT 390
R3 : period  80 / 夜 40  周期平均light ×1.00  -> REACHED pop 970 / gen 9
```

**周期平均の光量は完全に同一で、変えたのは夜の長さだけ。** それで絶滅と繁栄が入れ替わる。
これは §0 の A0 vs A2′（同一平均光量・static vs cycle）の鏡像であり、
**致命的な変数は「夜の長さ」そのもの**であることを両側から確定させている。

R4 は夜を 40 にすると同時に昼を 160 へ伸ばすので平均光量が1.6倍になり、
pop 2,780 まで伸びる。夜短縮の効果を最も強く見せるが、2軸が動いているので
**因果の同定には R3 のほうが適している。**

R1（`repro_energy_frac` 0.8）は救済するが pop 18〜34 と非常に小さい。
`docs/環境因子追加・校正方針.md` §2.2 の
「1因子が他の進化圧をほぼ消してしまわない」「knife-edge でない」という条件に照らすと、
**R1 単独は working reference として弱い。**

R2（`energy_capacity` 300）は pop 650 で成立する。ただし
`E_max = 300 × 0.8 = 240` に対し繁殖閾値が `0.6 × 240 = 144 > initial_energy 50` となるため、
**tick1一斉繁殖が起きない**という副次効果を含む。R1 と同じ交絡があるので、
採用するなら `initial_energy` を合わせて設計する必要がある。

### 変更提案（MUST FIX ③ の具体化）

Phase B の掃引軸を次へ差し替えることを提案する。

```text
現状: light_max = 1.2, 2.4, 4.0, 6.0, 8.0, 12.0
        -> 実測でフラット。VIABLE_LEVEL は0個になる

提案: light_max は Phase A で成立した値に固定し
      light_cycle_period_ticks = 80, 120, 160, 200, 240   (day_fraction=0.5 固定)
      を主軸にする
        - 周期平均光量が変わらないので、light量との交絡が無い
        - R3(80)=成立 / R0(200)=崩壊 が実測済みなので、
          この軸には確実に転移点があり、両側に振れる
        - 「幅のある成立域」を探すという校正方針 §2.2 の要求を満たせる
```

補助軸として `energy_capacity` を 100 / 200 / 300 の3水準置くと、
「夜を短くする（惑星側）」と「貯蔵を増やす（生物側）」のどちらを
working reference にするかの判断材料になる。

なお `docs/メインストリーム開発ストーリー.md` / `docs/LUCA参照モデル方針.md` の
「現実から構造・因果を借りる」原則に照らすと、
**昼夜のある惑星で生きる生物が実際に採る解は「貯蔵」と「夜間の低活動」であって、
「夜を短くする」ではない。** 惑星側を生物へ合わせるのは最後の手段としたい、
という設計判断はここで人間が下す価値がある（§4-2 も参照）。

---

# 4. その他の指摘

## 4-1. SHOULD FIX: `R_ref` の位置づけを Exp15 へ引き継ぐ

`docs/V1.8_現状総括_Exp14結果.md` §5.2 は

```text
R_ref ≲ 0.45 付近から最初の夜越しが可能
R_ref は長期 fitness / 生態系成立指標ではない
```

と正しく整理している。**この区別を Exp15 の観測量へ明示的に持ち込むことを推奨する。**

Exp15 §7 の観測量は充実しているが、`R_ref` そのものが入っていない。
run前に決定論計算できる量なので、各 arm / 各 level の `R_ref` を
`exp15_*_summary` へ**事前計算値として**入れておくと、
「実測の生死が `R_ref` の単調関数で説明できるか」を機械的に確認できる。

本レビューの実測では、`light_max` を変えても `R_ref` は変わらず、生死も変わらなかった。
**`R_ref` と実測が対応することの、これ以上ない確認になっている。**

## 4-2. SHOULD FIX: 「夜に休止できない」ことを明記する

`Config.idle_prob`（「刺激なし時に静止する確率」）は定義されているが、
**`evosim/` のどこからも参照されていない**（V1.6 で参照が消えた dead config）。

`behavior.py` の早期 return は満腹判定だけなので、
夜は energy が減り続け、**全個体が夜通し wander して `move_cost` を払い続ける。**
収入が厳密に 0 の時間帯に移動し続けることに適応的意味は無い。

これは前回レビューでも挙げたが、**A2′ の結果（時間構造そのものが致命的）を踏まえると重要度が上がる。**
夜間の低活動は:

- 全個体対称のルールなので絶対原則8（特定生態型へのボーナス）に抵触しない
- Config 項目が既に存在する
- 現実の生物が昼夜へ適応する主要な方法の一つ

なので、remedy 候補として正式に俎上へ載せる価値がある。

## 4-3. OPTIONAL: 実行前検算をワークフロー化する

Exp11（`late_drift` 閾値と tick 予算の不整合）、Exp13（`light_max` ladder）、
そして今回の Exp15 Phase B と、**「走らせる前にローカルで数十 run 回せば分かったこと」で
本番 dispatch を消費するパターンが3回続いている。**

本レビューの実走は合計 **41 run / 1,500 tick**、所要時間は数分である。
Exp15 formal の 43 run / 305,000 tick と比べれば無視できる。

→ `docs/環境因子追加・校正方針.md` か Exp チェックリストへ、次を恒久ルールとして
加えることを提案する。

```text
formal dispatch 前に、事前登録した条件のうち
  - baseline arm
  - 掃引軸の最小値と最大値
を短tick（1,000〜2,000）でローカル実走し、
「判定が両側に振れうるか」を確認する。

全水準が同じ側に張り付くことが事前に分かった掃引は、
そのまま formal へ投げない。
```

これは絶対原則13（結果を見て条件を変えない）に抵触しない。
**結果を見る前の feasibility 確認であり、事前登録の一部**だからである。

## 4-4. OPTIONAL: 文書数が増えすぎている

V1.8 関連だけで正本・履歴・訂正・チェックリスト・総括が15本以上あり、
`docs/次の実験計画.md` の優先参照順は16項目ある。

`docs/Exp14_表現型プロベナンス訂正.md` のような「後から効く訂正」が
参照順の3番目に入っている構造は正しいが、
**参照順が16項目ある時点で、実装者が全部読む前提は現実的でない。**

→ 「実装前に必ず読む5本」と「必要時に参照する履歴」を明確に2層へ分けることを提案する。

---

# 5. 前回までのレビューの自己評価

## 5-1. 当たっていたもの

- **「夜の生存は貯蔵容量で決まり、`light_max` は式に入らない」** — Phase B 実測で完全に確認。
  光量5倍で絶滅tickが 373→377
- **「`H` は light specialist では不活性」** — A1 ≡ A0 が seed1 で数値まで一致
- **「Exp15 は2×2で切り分けるべき」（V1.8レビュー S-2）** — Exp15 Phase A として採用され、正しい方向

## 5-2. 外していたもの

- **Exp14 の結果予測を外した。** 前回レビューで A1（夜なし）・A2（夜40）・A4（繁殖閾値0.8）は
  「存続する」と予測したが、実際は 116/116 全滅した。
  原因は表現型バグ（`light_absorption=0.3`）で、私は Exp14 の Config 生成器を確認していなかった。
  **計画文書に書かれた表現型を、実装コードで検証せずに信じたのが誤りである。**
  今回は同じ轍を踏まないよう、`make_exp14_configs.py` を直接 grep してから議論した
- **前回の `R` 予測は「単一の夜を越せるか」までは正しかったが、「越せれば存続する」は誤り。**
  A2′ は `R` を下げても（夜1は越えても）夜2で死ぬ。
  `docs/V1.8_現状総括_Exp14結果.md` §5.2 の
  「`R_ref` は長期成立指標ではない」という整理のほうが正確だった

---

# 6. 推奨する対応の優先順位

| 順 | 対応 | 追加run | 効果 |
|---:|---|---:|---|
| 1 | **A2′（energy等価 cycle arm）を Phase A へ追加**（§2-3） | +5 | Phase B を走らせる価値があるか決まる |
| 2 | **Phase B の掃引軸を `light_max` から差し替え**（§3-1） | ±0 | 18 run の確定的な空振りを回避 |
| 3 | **density arm を `light_max ≥ 4` でも測る**（§2-2） | +10 | 2×2 が実質1×2に潰れるのを防ぐ |
| 4 | `docs/V1.8_現状総括_Exp14結果.md` §9 を実測で更新（§1-2） | 0 | 誤った制約が次の設計へ伝播するのを防ぐ |
| 5 | `R_ref` を事前計算値として summary へ（§4-1） | 0 | 生死と `R_ref` の対応を機械確認 |
| 6 | formal 前ローカル実走を恒久ルール化（§4-3） | 0 | 同種の空振りの再発防止 |
| 7 | 夜間休止（`idle_prob`）を remedy 候補へ（§4-2） | 0 | — |

**1〜2 は追加run 0〜5 で、Exp15 の情報量を最も大きく変える。**

---

# 7. 付録 — 実走スクリプト

`docs/Exp15_実験計画確定.md` §3 の共通条件をそのまま `Config` へ与え、
§4 の表現型 HARD GATE（初期100個体の `light_absorption == 2.0`）を assert してから回している。
リポジトリのコードは一切変更していない。

```python
from evosim.config import Config
from evosim.genome import GENE_NAMES
from evosim.simulation import Simulation

BASE = dict(
    light_pattern="vertical", chem_vent_flux=0.0, nutrient_initial=2.0,
    bmr_core=0.15, memory_tau=10.0, response_gain=64.0,
    light_uptake_coef=2.0, light_uptake_half=0.6,
    energy_capacity=100.0, repro_energy_frac=0.6,
    light_cycle_period_ticks=200, light_day_fraction=0.5,
    initial_population=100, initial_energy=50.0, initial_matter=0.8,
    diagnostic_placement="random", fixed_genes=list(GENE_NAMES),
    diagnostic_gene_overrides={"light_absorption": 2.0, "chemical_absorption": 0.3},
    stats_interval=20, snapshot_interval=1000, max_population_halt=10000,
)

# Phase A 2x2 : (cycle, density, light_max)
ARMS = {"A0": (False, False, 1.2), "A1": (False, True, 1.2),
        "A2": (True, False, 1.2),  "A3": (True, True, 1.2),
        # energy等価 cycle arm (本レビューの追加)
        "A2'": (True, False, 1.2 / (0.5 * 2 / 3.141592653589793))}   # = 3.7699

for name, (cyc, dens, lmax) in ARMS.items():
    for seed in (1, 2, 3):
        cfg = Config(light_max=lmax, light_cycle_enabled=cyc,
                     primary_energy_density_response=dens, **BASE)
        sim = Simulation(cfg, seed=seed)
        assert all(abs(o.genome[5] - 2.0) < 1e-12 for o in sim.organisms)   # 表現型GATE
        ext = None
        for _ in range(1500):
            sim.step()
            if not sim.organisms:
                ext = sim.tick
                break
        print(name, seed, ext, len(sim.organisms),
              max((o.generation for o in sim.organisms), default=-1))
```

Phase B の検算は `ARMS` を
`{f"B {L}": (True, True, L) for L in (2.4, 4.0, 8.0, 12.0)}` へ差し替えるだけである。
