# Exp20 結果・考察 — Opus 5 レビュー

レビュー日: 2026-09-10
レビュー対象branch: `v1.11-phototrophy-plan` (`e279b5a`)
対象文書: `docs/Exp20_結果考察.md` / `docs/Exp20_V1.11_PrimitivePhototrophy_SeededInvasion_実験計画.md` / `docs/V1.11_原始Phototrophy_実装仕様_rev2.md`
対象コード: `evosim/simulation.py` / `evosim/physiology.py` / `experiments/exp20_v111_phototrophy_invasion/` / `tests/test_v111_phototrophy.py`

レビュー種別: 結果レビュー。**仕様・候補値・判定基準・コードは一切変更していない。すべて変更提案である。**

検証スクリプト: `experiments/opus5_exp20_review_20260910/`

---

# 0. 結論

**A0 で観測された「phototroph が 48 h で 16 倍」は、V1.11 の光機構によるものではない。**

`evosim/simulation.py` の旧 `_absorb_light()` が physical mode で無効化されておらず、旧arbitrary単位の光Energyが Joule 建ての `org.energy` へ直接加算されている。phototroph だけが `light_absorption > 0` を持つため、この経路は phototroph だけに効く。

実測:

```text
V1.11 photo credit が 30 step で与えたEnergy   : 5.1474e-16 J
legacy経路で phototroph が余分に得たEnergy      : 1.3895e-11 J
倍率                                            : 2.70e+04 倍
```

legacy経路を無効化して Exp20 の A0 / freq=0.50 / seed=20001 を 48 h 再現すると:

```text
Exp20報告 (legacy有効) : P0=50 -> P48=800  (16.00x)
本レビュー (legacy無効) : P0=50 -> P48=50   ( 1.00x)
                          A0=50 -> A48=50   ( 1.00x)
48 h時点の平均matter    : phototroph 1.0249 / ancestor 1.0235  (差 0.14%)
```

**A0 の 16 倍は完全に消える。** V1.11 機構が formal config (flux 0.015 µmol/m2/s、`light_absorption`=0.01) で生む差は 48 h で 0.14% であり、ゼロと区別できない。

さらに、A1 の primary endpoint も別の理由で解釈できない。

```text
結果考察 §6 は 0% arm の s48 = +2.652/day を pseudocount artifact として除外した。
しかし ancestor-only control は 43-46 h で全滅する (§4.1) 一方、評価時点は 48 h である。
報告値から逆算すると、10% / 50% arm の A48 も実質 0 である。
```

したがって:

```text
D-1 [CRITICAL] legacy `_absorb_light()` が physical mode で無効化されていない
D-2 A0 の 16 倍は D-1 由来。legacy を切ると差は消える (1.00x / 1.00x)
D-3 A1 の Delta_s48 > 0 は、10%/50% arm でも pseudocount artifact
    (§6 の修正では取り除けない)
D-4 Phase 0 / unit test は構造的にこの種のバグを検出できない
    (T1-T5 は `sim.step()` を一度も呼ばず、T5 は関数シグネチャの assert)
```

**Exp20 の生態的結論は撤回が必要である。** 一方、rev2 の設計変更そのもの (maintenance credit、N構造コスト、flux 0.015) は §2 のとおり良い判断であり、機構を作り直す必要はない。

---

# 1. D-1 — legacy `_absorb_light()` が無効化されていない【CRITICAL】

## 1.1 コード

`evosim/simulation.py` の `_absorb_fields()`:

```python
for key, orgs in self.org_hash.items():
    phis = [o.phi(dc, pf) for o in orgs]
    areas = [physiology.effective_surface(o.matter) for o in orgs]
    self._absorb_light(orgs, phis, areas, key)      # <- physical mode gate が無い
    self._absorb_h2(orgs, phis, areas, key)
```

`_absorb_h2()` は冒頭で `if self.cfg.physical_mode: self._absorb_h2_physical(...)` へ分岐するが、`_absorb_light()` には対応する分岐が無い。関数本体にも `physical_mode` / `physical_light_enabled` の判定は無い。

内部では:

```text
flux = world.light[key] * daylight_factor_now      # 旧arbitrary field, light_max = 1.2
raw  = light_uptake_coef(=2.0) * light_absorption * area * phi * uptake_factor * H(flux, K)
gain = min(raw, E_max - energy)                    # ← headroom で clamp
```

`raw` は arbitrary 単位だが、`org.energy` は physical mode では Joule である。`light_absorption = 0.01` でも `raw` は概ね 1e-3 order で、`E_max = 1.586e-11 J` を 8 桁上回る。したがって **clamp が常に効き、phototroph のエネルギータンクは毎 step 満タンに戻される。**

## 1.2 なぜ Exp19 まで顕在化しなかったか

capability gate が `phototrophy OFF -> light_absorption = 0` を強制していたためである。需要が恒等的に 0 なので、legacy 経路は存在しても何も起きなかった。

**Exp20 で初めて `light_absorption > 0` の個体を配置したことで、休眠していた経路が起動した。**

この問題自体は Issue #69 (F-1) および Issue #70 で「light route が物理スケール化されていない」として指摘済みだが、rev2 実装時に **V1.11 の新経路を足す一方で旧経路を塞ぐ作業が漏れた**。

## 1.3 実測

`experiments/opus5_exp20_review_20260910/exp20_legacy_light_leak.py`:

```text
photon flux              : 0.015 µmol/m2/s
light_absorption         : 0.01
P_incident               : 1.7244 fW
P_absorbed               : 0.01716 fW
P_usable (= credit)      : 0.00172 fW
ancestor maintenance     : 0.43702 fW
credit / maintenance     : 0.393 %
phototrophの追加維持コスト : +0.000259 fW
正味                      : +0.333 % of maintenance
```

30 step (300 s) 走らせた結果:

|  | phototroph | ancestor |
|---|---:|---:|
| t=0 energy | 7.8196e-12 J | 7.8196e-12 J |
| legacy ON 後 | **1.5637e-11 J** | 1.9967e-12 J |
| legacy OFF 後 | 1.7422e-12 J | 1.9967e-12 J |

`legacy ON` の phototroph は `E_max = 1.5861e-11 J` にほぼ張り付いている。ancestor は逆に 7.82e-12 → 2.00e-12 へ減っており、両者の乖離は 1 step 目から生じる。

```text
legacy経路で得た余分なEnergy : 1.3895e-11 J
V1.11 credit                 : 5.1474e-16 J
倍率                          : 2.70e+04 x
```

---

# 2. D-2 — legacy を切ると A0 の 16 倍は消える

`experiments/opus5_exp20_review_20260910/exp20_a0_legacy_off_replication.py` で、Exp20 formal config そのまま (A0_STATIC / freq=0.50 / seed=20001) を 48 h、`_absorb_light()` だけ無効化して再現した。

```text
   h   N_ph   N_an  meanM_ph  meanM_an    meanE_ph    meanE_an
  12     50     50    0.5976    0.5965  8.8202e-13  8.8021e-13
  24     50     50    0.7069    0.7102  1.0025e-12  1.0055e-12
  36     50     50    0.8465    0.8469  1.1570e-12  1.1566e-12
  48     50     50    1.0249    1.0235  1.3547e-12  1.3521e-12

48h: P0=50 -> P48=50 (1.00x) ; A0=50 -> A48=50 (1.00x)
Exp20報告値 (legacy有効): P48=800 (16.00x) ; A48=50 (1.00x)
```

48 h を通じて **phototroph と ancestor は個体数・matter・energy のいずれでも区別できない。** 平均 matter の差は 0.14%、平均 energy の差は 0.19% で、これは §1.3 の「正味 +0.333% of maintenance」と整合する。

結果考察 §3 の

> phototrophyはH2 interruption時だけの耐久能力ではなく、H2が安定している通常環境でも大きな一般的fitness advantageを与えている

および §7.2 の「A0 でも強い general advantage が存在する」という判断は、**V1.11 機構についての記述としては成り立たない。**

同様に、§8 の Exp21 Step 1「A0 で 16 倍になる原因を定量化する」および Step 2「`phototrophy_radiant_to_usable_eff` / photon flux / N cost の sensitivity sweep で利益を弱める」は、**存在しない利益を弱めようとする作業になる。** 先に D-1 を直す必要がある。

## 2.1 副次的な確認 — 「A48 = A0 で ancestor が全く増えない」は正常

結果考察 §3 の表で ancestor が 48 h で全く増えていない (99/90/50 が不変) 点は、bug ではない。legacy を切った再現でも 48 h 時点の平均 matter は 1.02 であり、分裂閾値 (matter >= 1.0 × target_size かつ runway gate) を越えたばかりである。V1.9/V1.10 baseline の世代間隔 (約 48-56 h) と整合する。

ただしこれは **ancestor が分裂閾値のすぐ手前に座っている**ことを意味する。48 h という評価時点は、ancestor の世代交代がちょうど起きるか起きないかの境界にあり、微小な差が個体数比に大きく出やすい。評価時点の選び方としては不利である (§4.2 で提案する)。

---

# 3. D-3 — A1 の primary endpoint も pseudocount artifact

## 3.1 §6 の修正では足りない

結果考察 §6 は、0% arm で `P0=0, P48=0, A0=100, A48=0` にもかかわらず pseudocount 0.5 のせいで `s48 = +2.652/day` が出る点を正しく指摘し、0% arm を解釈対象から外した。

**しかし同じ artifact は 1/10/50% arm にも及んでいる。**

計画 §8 は「A1 では ancestor-only が後半に全滅し得るため、5 日最終値だけで relative fitness を評価しない。主評価時点は 48 h とする」としていた。ところが実際の ancestor-only control は **43-46 h で全滅した** (§4.1)。つまり **評価時点 48 h は ancestor 全滅の後**であり、この緩和策は機能していない。

## 3.2 報告値からの逆算

`experiments/opus5_exp20_review_20260910/exp20_s48_pseudocount_check.py`。まず式の使い方を検証するため、§6 が報告した 0% arm の値を再現する。

```text
s48(P0=0, A0=100, P48=0, A48=0) = +2.652/day   (報告値 +2.652)  ✓
```

同じ式で、報告された `s48_A0` / `Delta_s48` / `P48` から A1 arm の `A48` を逆算する。

| freq | s48_A0 | Δs48 | s48_A1 | P48 | **逆算 A48** | A48=0 なら s48_A1 |
|---:|---:|---:|---:|---:|---:|---:|
| 1% | 1.199 | 0.730 | 1.929 | 2.0 | **3.00** | 2.902 |
| 10% | 1.363 | 1.068 | 2.431 | 8.5 | **0.10** | 2.522 |
| 50% | 1.382 | 0.803 | 2.185 | 47.0 | **0.10** | 2.277 |

**10% と 50% の arm では A48 が実質 0 である。** 報告された `s48_A1` は、A48=0 と置いたときの値 (2.522 / 2.277) とほぼ一致する。

つまり主要な 2 arm において、`Delta_s48 > 0` は分母が pseudocount 0.5 になっていることで決まっており、**phototroph の相対 fitness を測っていない。** これは §6 が 0% arm について指摘したのと同一の artifact である。

1% arm だけは A48 ≈ 3 で完全な 0 ではないが、A0=99 からの 97% 減であり、やはり ancestor の崩壊が支配している。

## 3.3 結果考察 §5 の記述は正しい方向を向いていた

§5 は既に

> ただしこれは「A1でphototroph自身の絶対増殖速度が高い」という意味ではない。実際にはA1でphototrophも苦しんでおり、ancestorがさらに大きく減少するため相対fitnessが高くなっている

と書いており、解釈としては正しい。**問題は、そこまで分かっていながら primary estimand を `Delta_s48` のまま報告している**ことである。「ancestor が全滅する」は 0% control と Exp18 から既に分かっていた事実で、`Delta_s48 > 0` はそれを言い換えているに過ぎない。新しい情報を含んでいない。

## 3.4 一方、§4.2 の ecological rescue の観察は有効

`Delta_s48` とは独立に、以下は artifact ではなく実データである。

```text
0%    : ancestor 100 -> 43-46 h で全滅 (3/3 seed)
1/10/50% : 9/9 run が 120 h まで存続
```

**「phototroph を少数でも入れると集団が絶滅を免れる」という観察自体は成立している。** ただし D-1 により、その存続が V1.11 credit によるものか legacy 経路によるものかは現時点では判別できない。D-1 修正後に再確認が必要である (§4.1)。

---

# 4. D-4 — Phase 0 / unit test が構造的に検出できない

これが最も再発しやすい問題なので、単独で扱う。

## 4.1 acceptance test が新機構の自己申告だけを見ている

`tests/test_v111_phototrophy.py` の T1-T5 は **`Simulation.step()` を一度も呼ばない。** ファイル全体で `Simulation(` は 2 箇所 (T7 の N ledger、T10 の determinism) のみで、いずれも Energy の大きさを検査しない。

T4 の実体:

```python
m_cost_p = physiology.maintenance_and_movement(phototroph, cfg, 0.0, ...)
p_inc, p_abs, p_use = physiology.photo_power_chain_w(phototroph, cfg)
photo_credit_j = p_use * cfg.dt_seconds
photo_used = min(photo_credit_j, m_cost_p)
phototroph.energy += photo_used              # <- テスト自身が credit を適用している
assert phototroph.energy > ancestor.energy
```

テストが production の `step()` を呼ばずに credit 計算を**自分で再実装し、自分の計算結果を assert している。** これは仕様の算術が正しいことしか確認できず、実装が別経路を持っていても必ず PASS する。

## 4.2 T5 は空のテストになっている

「light alone does not fund growth」を守るはずの T5 の中身:

```python
import inspect
sig = inspect.signature(physiology.photo_power_chain_w)
assert list(sig.parameters) == ["org", "cfg"]
```

**関数シグネチャを assert しているだけ**で、Energy も growth も検査していない。docstring は「API境界で保証する (静的な設計確認)」と説明しているが、この assert は引数名を変えない限り絶対に落ちない。**主張している性質と、実際に検査している性質が無関係である。**

## 4.3 preflight T20-1 / T20-2 / T20-6 も同様に盲目

| test | 意図 | なぜ D-1 を検出できないか |
|---|---|---|
| T20-1 OFF regression | phototrophy OFF で V1.10.1 へ回帰 | OFF では capability gate が `light_absorption=0` を強制するので legacy 需要は 0。**legacy 経路は phototrophy ON のときだけ効くので、OFF の regression test では原理的に検出できない** |
| T20-2 Dark | `phototrophy ON + light=0 => photo_used = 0` | `light_photon_flux_umol_m2_s=0` は V1.11 chain だけを 0 にする。legacy が使う `world.light` (`light_max=1.2`) は別 field なので生きている。`photo_used` は 0 のまま PASS |
| T20-6 photo Energy ledger | `used <= usable_max <= absorbed <= incident` | すべて V1.11 chain 内部の量。第 2 の入口については何も言わない |
| T20-3 H2 absent / light present | 「no persistent Energy storage charging from light alone」 | **この test だけは検出できたはずだが、対応する behavioral test が `tests/` に見当たらない** (T5 が §4.2 の状態) |

## 4.4 恒久的な提案 — 機構の自己申告ではなく独立な上界で縛る

新機構を足すたびに同じ穴が開く。**新機構の counter で検証するのをやめ、機構と独立な保存則型の上界を置く**ことを推奨する。

```text
T-INDEPENDENT (提案):
  同一config・同一初期状態で phototroph と ancestor を1 stepだけ Simulation.step() し、

    ΔE_photo - ΔE_ancestor  <=  photo_usable_max_j + |maintenance差| + tol

  を assert する。

  これは V1.11 credit の実装を一切参照しないので、
  「V1.11 が説明できないEnergyが入った」ことを機構非依存に検出できる。
```

同様に:

```text
T-LEGACY-OFF (提案):
  physical_mode=True のとき Simulation._absorb_light() が
  Energy を1 J たりとも動かさないことを直接 assert する。
  (実装を消すのであれば、消えたことの回帰テストとして残す)

T-DARK-STRICT (提案):
  T20-2 を「V1.11 chain が 0」ではなく
  「暗条件で phototroph の ΔE が ancestor の ΔE 以下」で判定する。
  world.light も含めて全光源を 0 にする。
```

要点は、**テストが production の `step()` を通ることと、機構の外側から量を縛ること**の 2 点である。

---

# 5. 維持すべき点

D-1 は実装漏れであって設計の誤りではない。以下は良い判断であり、変更しないでほしい。

1. **rev2 で結合点を「H2 mol あたりの bonus」から「maintenance credit」へ変えた判断** (§5)。前回レビュー §4 で提案した内容だが、実装も仕様も筋が良い。`photo_used = min(photo_credit_j, m_cost + r_cost)`、carry しない、growth へ入れない、という 3 点が明確に書かれ、コードもそのとおりになっている。
2. **N 構造コストを BChl の光学断面積から積み上げた設計** (rev2 §7)。人工 penalty ではなく物理から出しており、`photo_assembly_fraction` で N 不足時に absorptance が下がる形にしたのは自然。`_release_photo_n_to_field()` で death / division / capability loss すべてに N の戻り経路を用意し「silent loss を禁止する」と明記している点も良い。
3. **photon flux を 1.0 から 0.015 µmol/m2/s へ下げた判断**。前回レビュー R-3 の指摘に対する応答として妥当で、しかも引用していた低光量 phototroph の実測レンジとも整合する。
4. **seeded invasion design そのもの**。稀事象ではなく頻度変化を測る設計は正しく、`founder_rank_key` を blake2b の stable hash で決めて nested founder sets を保証している実装 (T20-8) も丁寧。
5. **T20-9 RNG isolation / T20-11 LUCA baseline assert**。特に T20-11 (`h2_usable_energy_j_per_mol == 2407.5` を assert し、3750 への silent fallback を禁止) は前回レビュー R-1 への的確な対応で、この種の assert をもっと増やすべきという良い先例になっている。
6. **§6 で自ら pseudocount artifact に気づき、解釈から外した判断**。結論には足りなかった (§3) が、自分の primary estimand を疑ったこと自体は正しい姿勢である。
7. **§8 Step 4 で「phototroph が増えたのか ancestor が減ったのか」を分離する指標を並べた**こと。これは §3 の問題への正しい処方箋になっている。
8. **`_assemble_photo_structural_n` の docstring が、仕様に無い実装判断 (非競合 greedy 配分) を明示している**こと。仕様との差分を隠さないのは良い習慣。

---

# 6. MUST FIX

## R-1 `_absorb_light()` を physical mode で無効化する

`_absorb_fields()` に gate を入れるか、`_absorb_light()` の冒頭で早期 return する。

**推奨は「physical mode では旧経路を完全に削除し、V1.11 chain だけを残す」**である。gate で残すと、将来また別の実験で `light_absorption > 0` を使ったときに同じ事故が起きうる。arbitrary mode の過去実験再現が必要なら、`physical_mode=False` のときだけ生きる形に閉じ込める。

あわせて `light_max` / `light_uptake_coef` / `light_uptake_half` が physical mode で参照されないことを assert する test を置く。

## R-2 Exp20 の生態的結論を撤回し、A0 / A1 を再実行する

D-1 修正後、同じ preregistration・同じ seed で再実行する。**Attempt 1 は破棄せず、`AGENTS.md` §10 のとおり Attempt 2 として履歴を残す**こと。

Attempt 1 から保持できる事実:

```text
保持できる: 24/24 run 完走、C/N/P ledger closure、A1 ancestor-only の 43-46 h 全滅、
            aggregate / artifact pipeline が動くこと
撤回が必要: A0 の 16x、A0 での general advantage という判断、
            Delta_s48 > 0 の解釈、Pattern 2 判定、§8 の Exp21 方針
```

## R-3 primary endpoint を ancestor 全滅より前へ移す

D-3。`Delta_s48` を維持するなら、**評価時点は ancestor-only control の絶滅時刻より十分前**でなければならない。ancestor-only が 43-46 h なので、48 h は不適切である。

推奨:

```text
(a) 評価時点を 24 h へ前倒しする (ancestor がまだ十分残っている)
(b) 単一時点ではなく、6/12/18/24 h の log-ratio 回帰の傾きを推定する
    (1点の pseudocount 依存を弱め、推定精度も上がる)
(c) A48 = 0 の run は「s48 が定義できない」として NA にし、
    集計で median を取る前に除外する。0 を +2.652 として混ぜない
(d) ancestor 側は log-ratio ではなく生存時間 (extinction time) で扱う。
    「絶滅したか」は比ではなく生存解析の量である
```

**(b) + (d) の併用を推奨する。** ecological rescue (§4.2) は本来 (d) の量であり、それを比の指標へ押し込んだことが §3 の混乱の原因になっている。

## R-4 テストを production の `step()` を通す形へ書き換える

D-4 / §4.4。特に:

- T5 を実際に Energy を検査する behavioral test へ差し替える (現状はシグネチャ assert)
- T4 をテスト側で credit を適用するのではなく `sim.step()` の結果で検査する
- §4.4 の `T-INDEPENDENT` (機構非依存の Energy 上界) を追加する
- T20-2 Dark を `world.light` も 0 にした上で ΔE 比較で判定する

---

# 7. SHOULD FIX

## S-1 「16 倍」を疑うべきだった兆候を checklist へ入れる

結果考察 §3 は「3 seed すべてで同じ結果となった」と書いている。P48 = 16 / 160 / 800 はいずれも P0 のちょうど 16 倍で、A48 は A0 と完全一致、しかも 3 seed で完全一致である。

**確率的シミュレーションで 3 seed が完全一致するのは、結果ではなく診断の対象である。** 実際には legacy 経路が毎 step 決定論的に E_max を満たしていたため、分裂タイミングが完全同期していた。

恒久 checklist への追加を推奨する。

```text
[ ] seed 間分散がゼロの結果を「再現性が高い」と解釈していないか
[ ] 増加率が 2^n の整数倍になっていないか (同期分裂の兆候)
[ ] 新機構の効果量が、その機構の理論的上限を超えていないか
```

3 番目が最も重要で、今回は `credit / maintenance = 0.393%` という上限が仕様から直接計算できたので、16 倍が機構では説明できないことは実行前でも分かった。

## S-2 頻度依存性が「無い」ことを正式結果として記録する

A0 で P48/P0 = 16 が 1% / 10% / 50% すべてで同一、かつ A48 = A0 が全頻度で成立している。これは **phototroph が 800 個体まで増えても ancestor に一切影響しない**、つまり資源競争も密度依存もゼロであることを意味する。

D-1 由来の結果ではあるが、この観察自体は legacy を切っても変わらない可能性が高い。Issue #69 F-2 / Issue #70 で指摘したとおり、H2 は生物的にほぼ消費されず、C/N/P も 50x stock では 48 h で律速しないからである。

計画 §9.3 は「frequency dependence」を secondary endpoint に挙げているので、**Attempt 2 では「頻度依存性は検出されなかった」を正式結果として明記する**ことを推奨する。これは V1.12 (cross-feeding) 以降の設計判断に直接効く。

## S-3 `daylight_factor_now` が 0 でないことを確認する

本レビューの診断中、Exp20 formal config の t=0 で `daylight_factor_now = 0.0218` を観測した。rev2 §11 は「V1.11 最初の mechanical validation では day/night OFF」としているが、実際には light cycle が有効なまま動いている可能性がある。

D-1 の文脈では legacy 経路が生きていたことの一部だが、**V1.11 chain 側も `daylight_factor` を掛ける設計なら、formal run の実効光量が意図と違っていた**ことになる。Attempt 2 前に確認すべきである。

## S-4 A1 の「ecological rescue」を再確認する

§3.4。`Delta_s48` が使えなくなっても、「phototroph を入れると 9/9 run が 120 h 存続した」は重要な観察である。ただし D-1 修正後は、V1.11 credit が maintenance の 0.393% しかないため、**同じ rescue が再現しない可能性が高い。**

Attempt 2 では A1 を primary に据え、以下を主要 readout にすることを推奨する。

```text
extinction time の分布 (0% vs 1/10/50%)
vent OFF 期間中の phototroph / ancestor 別 死亡率
runway の lineage 別分布
starvation-active fraction の lineage 別時系列
```

rescue が消えた場合、それは失敗ではなく「flux 0.015 では credit が足りない」という定量的な答えである。**その場合に flux を上げるのは、`環境因子追加・校正方針` の「生存側へ自動最適化しない」に抵触しないよう、独立した sensitivity 実験として行う**こと (§8 に述べる)。

---

# 8. Exp21 への提案

結果考察 §8 の Exp21 方針は、D-1 修正前提では組み直しが必要である。

## 8.1 Step 1 (A0 の 16 倍の mechanism decomposition) は不要になる

§2 のとおり、legacy を切れば A0 の差は 1.00x になる。**存在しない利益の内訳を測る作業になるので、Step 1 は削れる。**

代わりに置くべきは:

```text
Step 1' — Attempt 2 の A0 negative control
  D-1修正後、A0 で phototroph と ancestor が区別できないことを確認する。
  これは「V1.11がA0で中立である」という積極的な結果であり、
  Pattern 1 (environment-dependent advantage) の前半分そのものである。
```

## 8.2 Step 2 (benefit/cost sweep) は方向を変える

現行案は「A0 での強すぎる利益を弱める」ための sweep だが、修正後は逆に **「A1 で rescue を起こすのに必要な最小の光量はどこか」** が問いになる。

```text
photon flux : 0.015 (現行) / 0.05 / 0.15 / 0.5 / 1.5 µmol/m2/s
固定: light_absorption = 0.01、radiant_to_usable_eff = 0.10、N cost
A1 環境、freq = 10%、3 seed
readout: extinction time、120 h survival、A0 での phototroph/ancestor 差
```

1 軸だけ振る (§8 の「複数 parameter を同時に無秩序に変更しない」という判断は正しい)。photon flux を選ぶ理由は、**環境側の量であり、生理側の校正値ではない**からである。`radiant_to_usable_eff` や N cost は生物の性質なので、環境で説明できるうちは触らないほうが `環境因子追加・校正方針` の原則に合う。

## 8.3 calibration target は §8 Step 3 のままでよい

```text
1. A0 では強い一方向 sweep を起こさない
2. A1 では ancestor-only が不利
3. phototroph は A1 で絶滅回避能力を維持
4. A1-A0 の環境依存差が残る
```

これは適切な目標である。**修正後は 1 が既定で満たされる**ので、実質的に 2-4 を満たす flux 帯を探す作業になる。

## 8.4 評価指標は §8 Step 4 を採用し、s48 を主から外す

§8 Step 4 が挙げている絶対量ベースの指標群は正しい。R-3 と合わせて:

```text
primary   : extinction time / 120 h survival (生存解析)
secondary : log-ratio の傾き (6-24 h、ancestor 全滅前の窓)
参考      : s48 単一時点 (A48 > 0 の run のみ)
```

## 8.5 計算コストは問題にならない

本レビューの 48 h 再現は **154 秒** で完走した (A0、100→100 個体)。Attempt 2 を 24 run 回しても GitHub Actions の 6 h 制限には遠く届かない。Exp18 で問題になった計算量爆発は個体数が数千に達した場合であり、D-1 修正後は A0 でも個体数が急増しないため再発しない見込みである。

**Exp21 で flux sweep を 5 水準 × 3 seed × 2 環境 = 30 run 走らせても十分収まる。** 実行制約を理由に seed 数を削る必要はない。

---

# 9. まとめ

**V1.11 の機構設計は良く、rev2 での変更 (maintenance credit / N構造コスト / flux 引き下げ) はいずれも妥当である。実装も、V1.11 chain 単体を見る限り仕様どおりに書かれている。**

問題は、新経路を足したときに **旧経路を塞ぐ作業が漏れ、しかもテスト群が構造的にそれを検出できない形になっていた**ことである。

```text
D-1  legacy _absorb_light() が physical mode で無効化されていない
     -> phototroph だけが V1.11 credit の 2.70e+04 倍のEnergyを得ていた
D-2  legacy を切ると A0 の 16 倍は 1.00 倍になり、48 h の差は 0.14%
D-3  A1 の Delta_s48 > 0 は 10%/50% arm でも pseudocount artifact
     (ancestor が評価時点 48 h より前の 43-46 h に全滅するため)
D-4  T1-T5 は sim.step() を呼ばず、T5 は関数シグネチャを assert している
```

必要な対応は 4 つ。

```text
R-1  physical mode で legacy light 経路を削除する
R-2  Exp20 を Attempt 2 として再実行する (Attempt 1 は破棄しない)
R-3  primary endpoint を ancestor 全滅より前へ移す、または生存解析へ変える
R-4  テストを production の step() を通す形へ書き換え、
     機構非依存のEnergy上界 assert を追加する
```

最も価値のある恒久対策は R-4 と S-1 である。**「新機構の counter が自分自身を検証している」構造と、「効果量が機構の理論的上限を超えていないか」を確認しない運用**は、今後 V1.12 (cross-feeding)、V1.13 以降で機構を足すたびに同じ事故を起こす。今回は仕様から `credit / maintenance = 0.393%` という上限が直接計算できたので、16 倍という観測値は **実行前でも矛盾として検出できた**。

---

# 10. 検証の再現方法

```bash
git worktree add /tmp/v111 origin/v1.11-phototrophy-plan
cd /tmp/v111 && uv sync

# D-1: legacy 経路が V1.11 credit の何倍か (数十秒)
EVOSIM_ROOT=/tmp/v111 uv run python \
  experiments/opus5_exp20_review_20260910/exp20_legacy_light_leak.py

# D-2: legacy OFF で Exp20 A0 を 48h 再現 (約150秒)
EVOSIM_ROOT=/tmp/v111 uv run python \
  experiments/opus5_exp20_review_20260910/exp20_a0_legacy_off_replication.py
# legacy 有効のまま比較する場合は EXP20_LEGACY_LIGHT=on を付ける

# D-3: 報告値だけから A48 を逆算 (即時、simulation不要)
uv run python \
  experiments/opus5_exp20_review_20260910/exp20_s48_pseudocount_check.py
```

**いずれもシミュレーション実験ではなく診断である。正式実験ではない。**
