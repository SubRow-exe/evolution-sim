# Exp20 Attempt 2 修正・再実験計画 — Opus 5 レビュー

レビュー日: 2026-09-10
レビュー対象branch: `v1.11-phototrophy-plan` (`08451df`)
対象文書: `docs/Exp20_Attempt2_修正・再実験計画.md` / 改訂後の `docs/Exp20_結果考察.md`

レビュー種別: 実行前の計画レビュー。**仕様・候補値・判定基準・コードは一切変更していない。すべて変更提案である。**

検証スクリプト: `experiments/opus5_exp20_attempt2_review_20260910/`

---

# 0. 結論

**改訂そのものは正確で、原因分析・撤回範囲・修正要求はいずれも妥当である。** 特に §2.1 の「capability OFF時だけ止めるgateでは不十分」、§2.2 の「V1.11の累積counterをそのまま真値として使用せず独立に計算する」、G6 の legacy parameter independence は、私が提案した内容より的確な形になっている。

一方、**Attempt 2 を今の設計のまま走らせても、主質問には答えられない。**

legacy 経路を無効化した状態 (= Attempt 2 の想定状態) で primary endpoint を実測した結果:

```text
A0_STATIC  freq=0.50 : 3 seed とも 6/12/18/24 h すべて 50/50 -> s_early = +0.000 (分散ゼロ)
A1_TEMPORAL freq=0.50: s_early = +0.631 / -1.330 / +0.379  (seed 20001-20003)
                       mean -0.107 , SD 1.067 , 符号 2正/1負
A1_TEMPORAL freq=0.10: phototroph lineage が 14 h で消失 -> 有効点2 -> NA
```

V1.11 機構の理論効果量は maintenance の **+0.334%** で、これを s_early へ換算すると **約 +0.0099/day**。実測された seed 間 SD は **1.067/day**。

```text
信号/雑音 = 0.0093
2σ検出に必要な seed 数 ≈ 46,000
Attempt 2 の設計    = 3 seeds
```

**検出力が約4桁足りない。** バグを正しく直しても、この endpoint と seed 数では Pattern A と Pattern B を区別できない。

したがって:

```text
F-1 [MUST] Attempt 1 の formal config が事前登録と不一致 (light_cycle)。
           Attempt 2 も同じ記述のままで、再発する
F-2 [SHOULD] V1.11 光路が daylight_factor を掛けていない。
           day/night は phototrophy へ原理的に効かない
F-3 [MUST] primary endpoint は A0 で恒等的に 0、低頻度 arm で NA、
           2x4 設計のうち A1/50% でしか機能しない
F-4 [MUST] 検出力が4桁不足。24 run を走らせても答えが出ない
F-5 [SHOULD] Pattern に「phototrophy が正味で不利」が無い
F-6 [note]  G2 の独立上界は absorptance を N非制限側で取るべき
```

**推奨は §10 の順序を入れ替えること** — photon flux calibration を Attempt 2 の後ではなく先に、しかも確率的 24 run ではなく **同一seedのペア決定論比較**で行う (§5)。

---

# 1. 実測 — primary endpoint は評価できるか

`experiments/opus5_exp20_attempt2_review_20260910/attempt2_endpoint_power.py`。
`Simulation._absorb_light` を無効化 (= R1 適用後の想定状態) し、Attempt 2 §3 の formal condition で 24 h 走らせ、§5 の手順どおり ln(P_t/A_t) を 6/12/18/24 h で取って一次回帰した。

| seed | env | 6h P/A | 12h P/A | 18h P/A | 24h P/A | 有効点 | s_early |
|---:|---|---:|---:|---:|---:|---:|---:|
| 20001 | A1_TEMPORAL | 29/37 | 16/17 | 9/8 | 5/4 | 4 | **+0.631** |
| 20002 | A1_TEMPORAL | 36/34 | 12/20 | 4/10 | 2/5 | 4 | **−1.330** |
| 20003 | A1_TEMPORAL | 34/35 | 20/18 | 7/9 | 3/2 | 4 | **+0.379** |
| 20001 | A0_STATIC | 50/50 | 50/50 | 50/50 | 50/50 | 4 | **+0.000** |
| 20002 | A0_STATIC | 50/50 | 50/50 | 50/50 | 50/50 | 4 | **+0.000** |
| 20003 | A0_STATIC | 50/50 | 50/50 | 50/50 | 50/50 | 4 | **+0.000** |

## 1.1 A0 は恒等的にゼロ

**A0 では 0–24 h に出生も死亡も1件も起きない。** 世代間隔が約 48 h なので、最初の分裂が 24 h 窓の外にある。

別途 48 h まで走らせた結果でも `N_ph = N_an = 50` が全時刻で維持され、48 h 時点の平均 matter は phototroph 1.0249 / ancestor 1.0235 (差 0.14%) だった。

したがって A0 の `L_t` は 4 点すべてで厳密に 0、傾きも 0 になる。**3 seed すべてで同一**であり、seed 間分散も 0 である。

```text
Delta_s_early = s_early_A1 - s_early_A0 = s_early_A1 - 0
```

**A0 arm は定数を1つ足しているだけで、対比較として何の情報も持たない。** さらに副質問1「A0 で決定論的16倍sweepが消えるか」には答えられるが、「A0 で小さな利益があるか」は原理的に判定できない。分解能の下限が「1回の分裂イベント」だからである。

## 1.2 低頻度 arm は NA になる

freq=0.10 の A1 を別途走らせたところ、phototroph lineage は **14 h で消失**した (10 → 0)。有効点が 6 h と 12 h の2点しか残らないため、§5 のルール「有効な時点が3点未満なら NA」に従い NA になる。

freq=0.01 は P0 = 1 なので、founder 1個体が死んだ時点で NA が確定する。24 h 窓内に分裂は起きないので、P_t は 1 か 0 のどちらかしか取らない。

**2 environments × 4 frequencies のうち、primary endpoint が実際に数値を返すのは A1 × {10%, 50%} 程度で、意味のある推定ができるのは A1/50% だけである。**

## 1.3 A1/50% でも seed 雑音に埋もれる

唯一機能する A1/50% でも:

```text
s_early = +0.631 , -1.330 , +0.379
mean = -0.107 , SD = 1.067 , SE(n=3) = 0.616
符号 2正 / 1負
```

**3 seed で符号が割れており、方向性が出ていない。**

---

# 2. F-4 — 検出力が4桁足りない【MUST FIX】

§1.3 の雑音床に対し、V1.11 機構が生む効果量を見積もる。

前回レビューで実測したとおり、Exp20 formal config での正味は:

```text
V1.11 photo credit         = maintenance の +0.393%
phototroph の追加維持コスト = maintenance の -0.059%
正味                        = maintenance の +0.334%
```

A1 で phototroph の死亡ハザードがこの割合だけ低いと仮定する。seed 20001 の ancestor は 6–24 h で log-population が 2.22 低下している (37 → 4) ので:

```text
18 h での log-ratio 差 = 2.22 x 0.00334 = 0.0074
s_early 差             = 0.0074 x 24/18 = +0.0099 /day
```

したがって:

```text
信号/雑音   = 0.0099 / 1.067 = 0.0093
1σ検出に必要な seed = 約 11,600
2σ検出に必要な seed = 約 46,400
Attempt 2 の設計    = 3 seeds
```

**約4桁足りない。** これは「bug を直せば見える」種類の問題ではなく、**確率的な個体数比を指標に選んだ限り、この効果量では何 seed 走らせても現実的には見えない**ということである。

## 2.1 したがって Pattern A と Pattern B は区別できない

§9 の解釈事前登録は:

```text
Pattern A : A0 ~ 0 かつ A1 > A0        -> 環境依存の選択価値あり
Pattern B : A0 ~ 0 かつ A1 ~ 0         -> 効果量が小さすぎる
```

としているが、**この設計では Pattern A が真でも観測結果は Pattern B と区別できない。** §1.3 の実測 (mean −0.107 ± SE 0.616) はまさに「A1 ~ 0」に見えるが、そこから「効果量が小さい」と結論するのは誤りになりうる。区別できないだけである。

Attempt 2 を走らせて Pattern B を報告すると、**「効果量問題」という診断自体が測定不能だったことに由来する**ため、次の flux calibration の出発点が根拠を欠く。

---

# 3. 推奨する設計変更 — 確率的比較をやめ、ペア決定論比較にする

効果が小さく決定論的である以上、**seed 雑音を持ち込まない測り方が存在する。**

```text
同一 seed / 同一初期配置で、phototrophy capability だけを ON/OFF した
2 runを走らせ、連続量の乖離を測る。
```

同一 seed・同一初期状態なら RNG 系列も個体配置も一致するので、**差はすべて phototrophy に由来する。** seed 間分散が入らないため、実質的に分解能の制約がなくなる。

実際、私が A0 で行った測定はこの形になっており:

```text
48 h 時点の平均 matter : phototroph 1.0249 / ancestor 1.0235  (差 0.14%)
```

を、雑音なしで単調に検出できている。個体数比では 50/50 で何も見えなかった量である。

## 3.1 具体案

```text
Primary (機構検証):
  同一 seed でのペア run (capability ON / OFF) における
    lineage別 平均 matter 軌跡
    lineage別 累積成長量
    lineage別 平均 stored Energy
  の乖離が、V1.11 の理論上界と整合するか

Primary (A1 生態):
  lineage別 生存時間 / per-capita hazard  (§6 が既に収集している量)

Secondary:
  ln(P_t/A_t) の傾き  (今の primary。A1/50% でのみ有効と明記して降格)
```

§6 の ecological rescue endpoint は既に生存解析の量を並べているので、**§5 と §6 の主従を入れ替えるだけでほぼ足りる。**

## 3.2 §10 の順序を入れ替える

現行 §10 は「Attempt 2 で Pattern A または B が得られたら次は photon flux calibration」としているが、§2 のとおり Attempt 2 は A と B を区別できない。

**推奨: flux calibration を先に、ペア決定論比較で行う。**

```text
photon flux : 0.015 / 0.05 / 0.15 / 0.5 / 1.5 umol/m2/s
同一 seed のペア run (capability ON/OFF)、A0 と A1 各1 seed
readout: 平均 matter 乖離、生存時間差、理論上界との比

-> 「s_early の雑音床 1.07/day を超える効果量が出る flux」を特定する
-> その flux で初めて 24 run の invasion 実験を preregister する
```

これなら 10 run 程度で「どの flux から確率的実験が成立するか」が決まる。**現在の 0.015 で 24 run を走らせるより、結論が出る確率が高く、しかも安い。**

なお計算コストは制約にならない。本レビューの A1 24 h run は 1本あたり十数秒、A0 48 h run は 154 秒だった。

---

# 4. F-1 — Attempt 1 の formal config が事前登録と一致していなかった【MUST FIX】

Attempt 1 の実験計画 §3.2 は formal arm の条件として:

```text
light_cycle = OFF
```

と明記している。しかし実際の config は:

```text
light_cycle_enabled = True
light_cycle_period_ticks = 8640   (= 24 h)
```

だった (本レビューの実行時に測定。t=0 の `daylight_factor_now` は 1.0 から始まり 24 h 周期で 0 まで振れる)。

原因は `experiments/exp20_v111_phototrophy_invasion/exp20_core.py` の:

```python
LIGHT_OVERRIDES = dict(
    physical_light_enabled=True,
    light_photon_flux_umol_m2_s=0.015,
    light_effective_wavelength_nm=800.0,
    light_physical_pattern="uniform",
    phototrophy_radiant_to_usable_eff=0.10,
)
```

に `light_cycle_enabled` が含まれておらず、base config (`experiments/exp15_v19/run_exp15.py:158` の `light_cycle_enabled=True`) がそのまま継承されたことである。

**これは Exp14 と同じ失敗クラスである** — 計画文書に書いた条件が、実際に走った config と違っていた。Exp14 では `light_absorption=2.0` の予定が `0.3` で走り、実験1本を失っている。

## 4.1 Attempt 2 でも再発する

Attempt 2 §3 も同じく `light_cycle = OFF` と記載しているが、**それを実際に設定する指示がどこにも無い。** `LIGHT_OVERRIDES` に追加しない限り、Attempt 2 も同じ不一致で走る。

legacy 経路を除去した後は `light_cycle_enabled` が Energy 収支へ影響しなくなる (F-2 参照) ので実害は小さいが、`effective_config.json` が計画と食い違う状態は残り、将来 daylight coupling を実装した瞬間に静かに効き始める。

## 4.2 提案 — preflight gate に「計画との一致」を加える

G1–G6 には「effective config が事前登録の表と一致していること」の確認が無い。`AGENTS.md` §10 は `effective_config.json` を成果物へ残すことを要求しているが、**それを計画と突き合わせる gate は存在しない。**

```text
G7 (提案) — preregistration conformance
  formal run の effective_config.json が、計画文書 §3 の条件表と
  field 単位で一致することを assert する。
  一致しない field が1つでもあれば formal を開始しない。
```

Exp14 と Exp20 で2回起きているので、恒久 gate にする価値がある。

---

# 5. F-2 — V1.11 光路は daylight_factor を掛けていない【SHOULD FIX】

`evosim/physiology.py` の `physical_light_incident_power_w()` は `cfg.light_photon_flux_umol_m2_s` を直接使っており、`daylight_factor` を掛けていない。`simulation.py:410` の photo credit 計算にも掛かっていない。

一方、legacy 経路 (`simulation.py:512`) は `daylight_factor_now` を掛けている。

つまり:

```text
legacy 経路        : 昼夜あり
V1.11 physical 経路 : 昼夜なし (24時間フル稼働)
```

## 5.1 rev1 の要求が rev2 で消えている

rev1 §11 は:

> 既存daylight factorをphysical photon fluxにも掛けられる構造にするが、V1.11最初のmechanical validationではOFF

としていた。**rev2 には day/night の記述が1つも無い。** 要求が黙って落ちており、実装もそれに合っている。

## 5.2 影響は Attempt 2 より先にある

Attempt 2 に限れば、legacy 除去後は `light_cycle_enabled` が無効なので実害は無い (F-1 の記述整合性の問題だけ)。

しかし **プロジェクト全体としては重い。** V1.9 iLUCA再設計仕様 §16 と長期ロードマップは一貫して:

> V1.8 day/nightはphototrophyが創発した後に初めて意味のある周期圧となる

という前提で day/night 機構を保持してきた。現在の実装では **phototrophy が出現しても day/night は光合成へ一切影響しない。** この前提は成立していない。

Attempt 2 の結果に関わらず、**既知の制約として記録し、V1.12 以降で daylight coupling を実装するか、あるいは「V1.11 では昼夜を光合成へ結合しない」と明示的に決める**必要がある。夜に光合成が止まらない生物は、その後の storage / starvation 形質の選択圧解釈にも効く。

---

# 6. F-5 — Pattern に「phototrophy が正味で不利」が無い【SHOULD FIX】

§9 の事前登録は A (環境依存の利益) / B (効果が小さすぎる) / C (A0 でも利益) / D (説明不能) の4つだが、**「phototrophy が正味で不利」に対応する pattern が無い。**

理論上の正味は +0.334% で正だが、これは maintenance と organ upkeep だけを見た値である。実際には:

- `photo_structural_n_mol` が local fixed-N field から N を隔離する
- t=0 seeding も local field から N を取る (`test_seeding_transfers_n_from_local_field_not_from_nothing`)
- C/N/P が律速に近い局面では、この N 隔離が成長を抑える方向に効きうる

私の freq=0.10 A1 run では phototroph lineage が ancestor より先に消失した (14 h vs 49.6 h)。founder 10個体の小標本なので単独では結論にならないが、**符号が負になりうること自体は排除できない。**

```text
Pattern E (提案) — physical phototrophy が正味で不利
  A0 / A1 いずれでも phototroph が ancestor を下回る。
  この場合、benefit を上げるのではなく、まず N 構造コストの大きさが
  BChl 断面積からの見積もりとして妥当かを再確認する。
```

事前に置いておけば、負の結果が出たときに「bug では」と再監査へ戻る手戻りを防げる。

---

# 7. F-6 — G2 の独立上界について【note】

§2.2 / G2 の「physical mechanism の独立上界」は正しい設計だが、`light_absorptance_effective()` は `photo_assembly_fraction()` (構造N充足率) を含む動的な量である。

**上界としては N 非制限側、すなわち `1 - exp(-light_absorption)` を使うべきである。** 実際の N 制限された absorptance を使うと、N 隔離の実装バグがあった場合に上界自体がそれに追随してしまい、検出力が落ちる。

同様に、`daylight_factor` を将来 physical 経路へ入れる場合 (F-2)、上界計算では 1.0 を使う (最も明るい瞬間) のが安全である。

---

# 8. 維持すべき点

改訂は全体として質が高い。以下は変更しないでほしい。

1. **§2.1 の「capability OFF時だけ止めるgateでは不十分。physical modeのEnergy pathからlegacy routeそのものを排除する」** — 最も重要な一文で、正確に問題の本質を捉えている。
2. **G6 legacy parameter independence** — `light_max` / `light_uptake_coef` を変えても結果が変わらないことを test する。これは example test ではなく property test で、私が提案した内容より強い。同種の gate を今後の機構追加でも使うべき。
3. **§2.2 の「V1.11の累積counterをそのまま真値として使用せず、photon flux・geometry・absorptance・変換効率・dt等から独立に計算する」** — 「機構が自分自身を検証する」構造を断つ正しい原則。
4. **§5 の pseudocount 廃止・NA 明示・median への強制代入禁止・NA run の別報告** — Attempt 1 の指標問題への正確な処方。
5. **§6 で ecological rescue を相対 fitness から分離した**こと。
6. **§9 Pattern D (Energy上界違反・複数seed完全一致・2^n同期増殖が再発したら結果を解釈せず mechanism audit へ戻る)** — 良い停止規則。
7. **§11 異常結果 checklist** と、**§12 の「Attempt 2結果を見る前にphototrophy efficiency / N costを弱体化しない」**。
8. **改訂後 `Exp20_結果考察.md` §7 で Attempt 1 を削除せず INVALID として保持し、保持目的を4点挙げた**こと。`絶対設計原則`「歴史的experimentを現在仕様へ書き換えない」に沿っている。
9. **§8 で「A0 で完全同一になること自体を固定合否基準にしない」**とした判断。実測でも 0.14% の差は残るので、これは正しい。

---

# 9. まとめ

**バグ分析と修正要求は正確で、そのまま実装してよい。** 問題は、修正後に走らせる実験の設計である。

```text
A0 : 0-24 h に出生も死亡も無く、s_early は恒等的に 0
低頻度 arm : lineage extinction で NA
A1/50%     : 唯一機能するが SD 1.067/day、3 seed で符号が割れる
理論効果量 : 0.0099/day  ->  信号/雑音 0.0093、2σ に 46,000 seeds 必要
```

推奨する変更は3つ。

```text
1. primary endpoint を、確率的な個体数比から
   「同一 seed のペア run (capability ON/OFF) における連続量の乖離」へ変える。
   seed 雑音が入らないので分解能が桁違いに上がる。
   A1 の生態評価は §6 の生存解析を primary に昇格させる。

2. photon flux calibration を Attempt 2 の後ではなく先に行う。
   ペア決定論比較で 10 run 程度。
   「s_early の雑音床を超える効果量が出る flux」を特定してから
   24 run の invasion 実験を preregister する。

3. G7 (effective config と事前登録の一致) を preflight gate へ追加する。
   light_cycle の不一致は Exp14 と同じ失敗クラスで、
   現状の Attempt 2 記述のままでは再発する。
```

あわせて F-2 (V1.11 光路に daylight_factor が無く、day/night が phototrophy へ効かない) を既知の制約として記録してほしい。これは Attempt 2 の成否とは独立に、V1.12 以降の前提に関わる。

---

# 10. 検証の再現方法

```bash
git worktree add /tmp/v111fix origin/v1.11-phototrophy-plan
cd /tmp/v111fix && uv sync

EVOSIM_ROOT=/tmp/v111fix uv run python \
  experiments/opus5_exp20_attempt2_review_20260910/attempt2_endpoint_power.py
```

`Simulation._absorb_light` を無効化した状態 (= R1 適用後の想定) で
A0/A1 を freq=0.50・3 seed 走らせ、§5 の手順で s_early を計算し、
雑音床と理論効果量を比較する。A0 3 seed 分は個体数が減らないため
やや時間がかかる (1本あたり数分)。全6 runで概ね10分程度。

**シミュレーション実験ではなく診断である。正式実験ではない。**
