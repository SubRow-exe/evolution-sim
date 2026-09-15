# Exp21 結果考察 / Exp22 実験計画 — Opus 5 レビュー

レビュー日: 2026-09-15
レビュー対象branch: `v1.11-phototrophy-plan` (`4359b29`)
対象文書: `docs/Exp21_結果考察.md` / `docs/Exp22_実験計画.md`
参照: `docs/Exp21_実験計画.md` / `docs/V1.11_選択圧直接測定_実験ロードマップ.md`

レビュー種別: Exp21 は結果レビュー、Exp22 は実行前の計画レビュー。
**仕様・候補値・判定基準・コードは一切変更していない。すべて変更提案である。**

検証スクリプト: `experiments/opus5_exp21_exp22_review_20260915/`

---

# 0. 総評

**Exp21 は妥当であり、結論も支持できる。** 単一集団内の2 lineage競争、lineage追跡、mutation OFF、8 seed、A0 negative control という設計は、この計算環境で選択圧を測る方法として正しい。`assign_lineages` が simulation RNG を消費しないことを実行時に検証している (G9) のも丁寧である。

前回まで4回連続で成立しなかった「進化を観測する実験」が、**測り方を変えたことで初めて成立した**。これは方法論の転換が正しかったことの実証であり、V1.9 から持ち越されてきた宿題に区切りがついたという §8 の判断に同意する。

**Exp22 の計画も質が高い。** 特に G0–G5 の preflight、OFF run にも同じ flux を与える設計 (§8)、候補抽出ルールの事前固定 (§12)、主張してよい/いけないことの明示 (§14) は、Exp20 Attempt 1 の失敗から正しく学んでいる。

そのうえで、候補値を実装へ当てて検算したところ **3 点の問題**が出た。

```text
M-1 §6 の flux = 0 は Config validation を通らない (構築不能)。
    結果として §2 H4 の zero-light cost control が実行できない
M-2 structural N cost が実質ゼロ (個体 biomass N の 0.565%、環境 N の 0.011%)。
    50x CNP stock では N が非律速なので、trade-off の cost 側が存在しない
M-3 §12.1 が R_E で候補を選ぶが、R_E は実行前に解析的に予測できる。
    一方 Exp23 competition の検出力を決めるのは人口統計効果であり、
    そちらは R_E からは予測できない
```

M-3 に関連して、**Exp22 の結果は実行前にかなりの部分が予測できる**。予測値は §2.3 に置いた。これは計画が悪いという意味ではなく、Exp22 の情報価値が「R_E がいくつか」ではなく「機構が理論どおり動くか」「R_E が生態的効果へどう翻訳されるか」にあることを意味する。

---

# 1. Exp21 の評価

## 1.1 統計的強度

報告値: A2 で median 56.3%、8 seed 中 7 seed が 50% 超、範囲 45.6–63.3%。A0 は median 50.0%。

符号検定:

```text
P(X >= 7 | n=8, p=0.5) = (C(8,7)+C(8,8)) / 2^8 = 9/256 = 0.035  (片側)
```

単独では境界的だが、**A0 が median 50.0% であることとの対比が効いている**。「A2 でのみ頻度が動いた」という環境依存性の主張は、この2つを合わせれば支持できる。

選択係数へ換算すると:

```text
s = ln((0.563/0.437) / (0.50/0.50)) / 5 day = 0.051 /day
```

## 1.2 A0 対照は検出力を持たない【実測確認済み】

§3 の「A0 では median 50.0%」が (a)「差が出なかった」なのか (b)「頻度が原理的に動けなかった」なのかを、Exp21 harness (`run_exp21.run_one`) をそのまま再実行して確認した。

`experiments/opus5_exp21_exp22_review_20260915/exp21_control_power.py`、seed 21001 / 120 h:

| | births (long / baseline) | deaths (long / baseline) | 最終 (long / baseline) | long割合 |
|---|---:|---:|---:|---:|
| **A0_STATIC** | **150 / 150** | **0 / 0** | 200 / 200 | **50.0%** |
| A2_DYNAMIC_VENT | 138 / 130 | 61 / 69 | 127 / 111 | 53.4% |

**A0 は死亡が 0、かつ出生数が完全に一致している。** つまり A0 の 50.0% は観測結果ではなく**算術的に強制された値**であり、読みは (b) である。

この対照は「`starvation_horizon` が A0 で効かなかった」ことを示せない。**効いたとしても示せない**からである。A0 で long lineage が不利になる経路 (保護 reserve `P_full × starvation_horizon` が大きいぶん成長へ回せる Energy が減る) も同様に検出できていない。

### 提案

§3 / §5 の記述を、A0 について次のように書き分けることを推奨する。

```text
現在: A0では供給環境が安定しているため、その利点がほぼ発現しなかった
提案: A0では120hを通じて飢餓死が発生せず、両系統の出生数も一致したため、
      頻度が動く機会自体が存在しなかった。したがってA0は
      「効果がない」ことの証拠ではなく、検出力を持たない対照である。
```

環境依存性の主張そのものは、**A2 単独の 7/8 seed で独立に成立している**ので撤回する必要はない。ただし「A0 と対比して環境依存」という論法は使えないので、根拠を A2 の内部構造 (§1.2.1) へ移すほうが強い。

なお A0 で 8 seed 中どれか1つでも死亡が発生していれば話は変わるので、**全 seed の `{lineage}_deaths_cum` を artifact から確認すること**を推奨する。A0 に死亡が無いのは環境が非ストレスであることの構造的帰結なので、他 seed でも同様と予想する。

## 1.2.1 A2 の優位は出生・死亡の両方に分解できる【実測】

上表の A2 は、long lineage の優位が2成分に分かれることを示している。

```text
死亡差 : 69 - 61 = 8 個体ぶん long が有利
出生差 : 138 - 130 = 8 個体ぶん long が有利
最終差 : 127 - 111 = 16 個体
```

§5 が説明している機構 (早く省エネへ移るので生き延びる) は**死亡側を直接説明する**。

出生側は独立の効果ではなく、**生き残った long 個体が多いぶん繁殖機会も多かった**下流の帰結と読むのが自然である (死亡差と出生差がともに 8 でほぼ揃っているのはこの読みと整合する)。

**この分解を結果考察へ載せることを推奨する。** 頻度だけを報告するより、機構の主張 (生存有利) と観測 (死亡差) の対応が直接見えるので、Exp21 の結論がかなり強くなる。harness は既に両方を記録しているので追加実験は不要である。

## 1.3 機構の説明は正しいが、コスト側の記述が落ちている

§5 の説明は実装と整合している。`state = clip(runway / starvation_horizon, 0, 1)` なので、`starvation_horizon` が長いほど同じ runway でも `state` が小さくなり、早く省エネ側へ移る。

ただし実装では `state` は **`metabolic_factor` と `uptake_factor` の両方**に効く。つまり長 horizon 個体は H2 uptake も早く絞る。さらに成長が侵食できない保護 reserve が `P_full × starvation_horizon` なので、長 horizon はより多くの Energy を成長から隔離する。

**つまり長 horizon には「省エネが早い」という利点と「取り込みを絞る」「成長へ回せる Energy が減る」という不利が同居している。** A2 で正味プラスになったこと自体が結果だが、§5 が利点だけを説明していると、次に `starvation_horizon` をさらに伸ばせば有利という誤った外挿を招きうる。**単調ではなく最適値が中間にある可能性**を1行入れておくと安全である。

Exp20 Attempt 2 では ×0.5 / 0.8 / 1.2 / 1.5 を測っているはずなので、その flux-response 形状を引用できれば十分。

## 1.4 主張範囲について

§6 の3段階 (環境変化 → 形質依存 fitness 差 → 頻度変化) の記述は正確で、過剰主張していない。

ただし §8 の「physical mode で選択圧・自然選択が働くかという基盤確認は一区切りついた」は、範囲をもう一段絞って書いたほうがよい。Exp21 が示したのは:

```text
示した  : 設計者が置いた標準変異 (2 lineage) に対して選択が働く
未検証  : 突然変異が生成する変異に対して、run 長のうちに選択が働く
```

後者は Issue #69 D-5 で指摘した論点 (`light_absorption` を機能水準まで進化させるには最良ケースでも 46–92 世代、予算は 5–9 世代) がそのまま残っている。Exp21 は mutation OFF なので、この問いには触れていない。

**「standing variation に対する選択の成立」は確認できた、と書き分けることを推奨する。** これは減点ではなく、次に何が未確認かを正確にしておくためである。

---

# 2. Exp22 — 実測にもとづく指摘

## 2.1 M-1 — `flux = 0` は構築できない【MUST FIX】

§6 は水準として `0` を挙げ、「negative control + structural cost のみを見る」としている。また §2 H4 は「flux=0 で phototrophy ON に利益はない。一方 structural N cost が効けば ON 群はわずかに不利になり得る」としている。

しかし `evosim/config.py` の validation は:

```python
if self.physical_light_enabled:
    ...
    if self.light_photon_flux_umol_m2_s <= 0.0:
        raise ValueError("light_photon_flux_umol_m2_s は正でなければなりません。")
```

であり、`physical_light_enabled=True` のまま `flux=0` にすると **Config 構築時に ValueError で落ちる** (実測確認済み)。

回避策として `physical_light_enabled=False` にすると、今度は構造N assembly が同じフラグで gate されている:

```python
# evosim/simulation.py
if cfg.physical_light_enabled:
    self._assemble_photo_structural_n()
```

ため assembly が走らず、**cost 側も消える**。つまりどちらに倒しても H4 は検証できない。

### 提案

```text
(a) 水準 0 を「flux = 1e-6 等の実質ゼロ」に置き換える
    -> physical_light_enabled=True のまま、credit は無視できる大きさになり、
       構造N cost だけが残る。H4 の意図をそのまま満たせる
(b) または H4 を Exp22 の対象から外し、別途 N 律速条件下の実験とする (M-2 参照)
```

**(a) を推奨する。** 計画の他の部分を変えずに済み、G5 の paired-state 要件とも矛盾しない。

## 2.2 M-2 — structural N cost が trade-off として機能しない【MUST FIX】

`experiments/opus5_exp21_exp22_review_20260915/exp22_structural_n_cost.py` の実測:

```text
apparatus の構造N要求 (1個体)  : 6.2116e-18 mol
個体 biomass の N              : 1.0995e-15 mol
個体内での比率                  : 0.565 %

環境 fixed N 総量 (t=0)         : 5.4973e-12 mol
初期100個体分の構造N要求        : 6.2116e-16 mol
環境Nに占める比率               : 0.0113 %
```

Exp17 Phase C1 で採用された 50x CNP stock では N は非律速である (Exp17 結果で C/N/P limiter が 0% だったことと整合)。したがって:

- 個体レベル: 構造N は biomass N の 0.6% 程度で、成長を律速しない
- 環境レベル: 100個体で環境 N の 0.01% しか消費せず、枯渇しない

**結果として、Exp22 は benefit 側だけを測ることになる。** §2 H4 が期待する「cost が効いて ON がわずかに不利になる」状況は、この環境では発生しない。

### 提案

cost を実際に効かせたいなら **N 律速条件が必要**で、Exp17 で校正済みの 10x / 30x stock がそのまま使える。ただしそれは Exp22 の 1軸校正という趣旨 (flux だけを振る) と衝突する。

したがって推奨は:

```text
Exp22 では「cost 側は現環境では無効であり、benefit のみを測っている」
ことを §2 H4 の注記として明記する。
N 律速下の cost 検証は別実験 (Exp24 候補) として分離する。
```

これは Exp22 を弱める話ではなく、**得られた working flux が「cost を無視した場合の下限」である**ことを記録に残すためである。後で N 律速環境を入れたとき、同じ flux では足りなくなる可能性がある。

## 2.3 Exp22 の結果は実行前にかなり予測できる【M-3 の根拠】

`exp22_flux_effect_table.py` の実測。phenotype は §5 の `light_absorption=0.01` (absorptance 0.995%)、maintenance は ancestor の `P_full = 0.4327 fW`。

| flux [µmol/m²/s] | P_incident | P_usable | /maintenance | 期待 R_E | §12.1 判定 |
|---:|---:|---:|---:|---:|:--|
| 0 | — | — | — | — | **構築不可** |
| 0.015 | 1.7083 fW | 0.00170 fW | 0.393% | 0.39% | FAIL |
| 0.05 | 5.6944 fW | 0.00567 fW | 1.309% | 1.31% | **PASS** |
| 0.15 | 17.0831 fW | 0.01700 fW | 3.928% | 3.93% | PASS |
| 0.5 | 56.9436 fW | 0.05666 fW | 13.094% | 13.09% | PASS |
| 1.5 | 170.8309 fW | 0.16998 fW | 39.283% | 39.28% | PASS |

期待 R_E の根拠: 飢餓局面では E は概ね maintenance 速度で減るので、credit が maintenance の x% を肩代わりすれば E の減少が x% 遅くなり、積分比 R_E は一次近似で x% になる。

**したがって §12.1 の preferred candidate は 0.05 が最有力**と予測する。ただしマージンが閾値 +1% に対して 31% しかないため、seed ばらつき次第で 0.05 が落ちて 0.15 になる可能性も現実的にある。

この予測が当たるかどうか自体が G1 (機構が理論どおり動くか) の検証になるので、**この表を Exp22 の事前登録へ含めることを推奨する。** 実測が表から大きく外れたら、それは flux 校正の問題ではなく実装の問題である。

## 2.4 M-3 — 候補選択規則が Exp23 の検出力と接続していない【MUST FIX】

§12.1 は `R_E(48-72h)` で preferred candidate を選ぶ。しかし §15 が示すとおり、次段 Exp23 は **competition assay** であり、その検出力を決めるのは R_E ではなく **lineage 頻度の変化量**、すなわち人口統計効果である。

R_E は §2.3 のとおり解析的に予測できる量なので、それで候補を選ぶと「予測できる量で選んで、予測できない量で失敗する」構図になりうる。Exp20 Attempt 2 の計画で検出力が4桁足りなかったのと同種の問題である。

### Exp21 が提供する較正値

Exp21 の実測から、competition assay の雑音床を見積もれる。

```text
報告値 : median 56.3% , min 45.6% , max 63.3% , n=8
n=8 の正規分布で期待される range/SD ≈ 2.85
-> SD ≈ (63.3 - 45.6) / 2.85 ≈ 6.2 ポイント
-> SE(n=8) ≈ 2.2 ポイント
-> 観測された 6.3 ポイントのシフトに対し t ≈ 2.9  (7/8 と整合)
```

したがって **2σ 検出に必要な seed 数は、期待頻度シフト Δ [ポイント] に対して**:

```text
n ≈ (2 × 6.2 / Δ)^2

Δ = 6.3 ポイント (Exp21相当)  ->  n ≈ 4    (実際に 8 で検出できた)
Δ = 3 ポイント                ->  n ≈ 17
Δ = 2 ポイント                ->  n ≈ 38
Δ = 1 ポイント                ->  n ≈ 154
```

### 提案

§12.1 の候補条件へ、**人口統計効果の下限**を1つ追加する。

```text
6. A2 の 48-72h で、ON/OFF 間の
     Delta starvation deaths または Delta population
   が、Exp21 で検出できた効果量と同オーダーであること
```

さらに §13 の `exp22_working_flux_recommendation.json` へ、**その flux で Exp23 に必要な seed 数の見積もり**を含めることを推奨する。Exp22 で測った人口統計効果から上の式で逆算できる。

これがあれば、Exp23 を preregister する時点で「8 seed で足りるのか 40 seed 要るのか」が事前に分かり、Exp20 Attempt 2 の二の舞を避けられる。

---

# 3. レビュー依頼事項への回答

### 1. G0 legacy `_absorb_light()` 排除方法が十分か

**方針は十分。** §3 G0 の「capability OFF 時だけ止める gate では不十分、physical mode の Energy 経路から排除する」は正しい。

`878b8c1` で import 順は直っているが、**legacy light 経路の除去そのものはまだ入っていない**ように見える。G0 を「実行前の MUST-FIX」として残しているのは正しい。

あわせて Issue #72 で提案した **legacy parameter independence test** (physical mode で `light_max` / `light_uptake_coef` を変えても結果が変わらない) を G0 の合格条件へ入れることを推奨する。これは example test ではなく property test なので、将来別の経路が生えても検出できる。

### 2. production-step physical upper-bound test に抜けがないか

**1点抜けている。** §3 G1 の不等式:

```text
0 <= photo_used <= photo_usable_max <= photo_absorbed <= photo_incident
```

はすべて **V1.11 chain 内部の counter 同士**の関係で、Exp20 Attempt 1 で見落としたのと同じ構造である。第2の Energy 入口があっても、この鎖は成立したまま通る。

**機構に依存しない上界**を1つ足すこと:

```text
ΔE_ON - ΔE_OFF <= (photon flux, geometry, absorptance, 変換効率, dt から
                   独立計算した上界) + |maintenance 差| + tol
```

`photo_usable_max_j_cum` を真値として使わず、config から独立に計算するのが要点。なお absorptance は N 制限を含む `light_absorptance_effective()` ではなく、上界として `1 - exp(-light_absorption)` を使うこと。

### 3. OFF/ON pair を flux ごとに別 run する設計が妥当か

**妥当。** 特に §8 の「OFF run にも同じ physical photon flux を設定する」「baseline を別 flux から使い回さない」は重要で、正しい判断である。`physical_light_enabled` の有無は構造N assembly の gate も兼ねているので、OFF 側の flux を変えると比較対象が二重に変わってしまう。

### 4. flux 水準の範囲が適切か

**適切。** §2.3 のとおり、0.015 から 1.5 で maintenance の 0.39% → 39.3% を覆う 100 倍スパンになっており、「検出不能」と「支配的」の両端を挟んでいる。校正の grid としてよく置かれている。

唯一の問題は水準 `0` が構築できないこと (M-1)。`1e-6` 等へ置き換えれば解決する。

### 5. Stage-1 calibration として 3 seed / 72 h が十分か

**A0 は十分、A2 は薄い。**

common random number による paired 設計なので、pair が分岐しない限り seed 間分散はほぼ消える。A0 は死亡が少なく分岐しにくいので 3 seed で足りる。

一方 A2 は 48 h の vent turnover 後に死亡が始まり、**ON/OFF 間で最初の死亡個体が変わった時点で CRN の対応が崩れる**。§8 が「run 分岐後まで RNG 差が 0 とは仮定しない」と書いているのは正しい認識である。

ただし §12.1 が「3/3 seed で符号一致」を要求しているので、実質的に符号検定 (偶然一致確率 1/8 = 12.5%) として機能する。**Stage-1 の候補抽出としてはこれで十分**だが、結果考察で「3 seed 一致は偶然でも 12.5% で起きる」ことを明記してほしい。

### 6. primary を `R_E(48-72h)` と starvation exposure AUC にすることが妥当か

**A2 では妥当。A0 では R_E がほぼ 0 になると予想されるので、注記が要る。**

以前の実測で、A0 定常状態の個体は保護 reserve に張り付いていた (`E/E_max ≈ 0.045`、これは `P_full × starvation_horizon / E_max` と一致)。成長配分が保護 reserve を超える Energy をすべて成長へ回すためである。

この状態では **maintenance credit が増えても stored Energy は増えず、成長速度が上がる**。つまり A0 では credit の効果が E ではなく matter に現れる。

§11.1 が R_E を「Primary continuous readout」として環境共通で置いているのは、A0 に対しては不適切である。§12.2 の GENERAL_ADVANTAGE_FLAG が A0 で total living matter を見ているのは正しいので、**§11.1 を「A2 の primary」、A0 は matter 系を primary と書き分ける**ことを推奨する。

### 7. `median R_E >= +1%` 閾値が妥当か

**よく置かれている。** §2.3 のとおり、閾値が 0.015 (0.39%) と 0.05 (1.31%) の間にちょうど落ちるので、grid を意味のある形で分割する。全部通る / 全部落ちる のどちらでもない。

ただし 0.05 のマージンが 31% しかないので、**0.05 が落ちて 0.15 が candidate になるケースを事前に想定しておく**こと。どちらでも Exp22 は成功だが、「0.05 が落ちたから閾値を下げる」は結果を見た後の変更になるので禁止しておいたほうがよい。

### 8. structural N cost を含んだ ON/OFF 比較で初期条件の公平性が保たれているか

**G5 の設計は正しい。** `photo_structural_n_mol` を両者 0 から開始し ON だけが run 開始後に assembly するのは、t=0 の状態を揃えるうえで正しい選択である。

ON 側は序盤に一時的な N 取り込みハンデを負うが、§11.1 の主 window が 48–72 h なので、その頃には assembly が完了していて影響しない。

なお M-2 のとおり、**そもそも cost が小さすぎて公平性以前に効かない**ので、この点は実務上ほぼ問題にならない。

### 9. `light_cycle_enabled=False` として daylight coupling を後段へ分離する判断が妥当か

**妥当。ただし §4 の書き方を1箇所直すべき。**

§4 は「昼夜 cycle を使う formal ecological experiment へ進む前に、physical phototrophy 経路へ `daylight_factor` を接続するかを別途明示的に決定する」と書いている。これは「今は接続する/しないを選べる」と読めるが、実際には **現状の実装では接続されていない** (`physical_light_incident_power_w()` は `cfg.light_photon_flux_umol_m2_s` を直接使い、`daylight_factor` を掛けていない。legacy 経路のみが掛けている)。

つまり `light_cycle_enabled` の値にかかわらず、**V1.11 の光路は昼夜の影響を受けない**。Exp22 で `False` にするのは正しい (明示的で誤解がない) が、§4 には

```text
現状、physical phototrophy 経路は daylight_factor を参照していない。
したがって light_cycle_enabled の値は V1.11 光路へ影響しない。
Exp22 で False とするのは、この事実を config 上も明示するためである。
```

と事実を書いておくべきである。Issue #72 F-2 で指摘したとおり、これは「V1.8 day/night は phototrophy 創発後に周期圧になる」というロードマップの前提が現状成立していないという、Exp22 より先の問題にも繋がる。

### 10. Exp23 competition へ進む前に追加すべき mechanical gate

**2つ推奨する。**

```text
G6 (提案) — legacy parameter independence
  physical mode で light_max / light_uptake_coef を変えても
  Energy trajectory が変化しないこと (依頼1への回答)

G7 (提案) — competition 検出力の事前見積もり
  Exp22 で測った人口統計効果から、Exp23 に必要な seed 数を
  逆算して artifact へ残すこと (M-3)
```

G7 は gate というより引き継ぎ要件だが、Exp20 Attempt 2 の失敗を繰り返さないために最も効く。

---

# 4. 維持すべき点

1. **Exp21 の single-population 2-lineage 競争設計**。Exp20 Attempt 2 の別 run 比較から、同一世界内の頻度変化へ進めた判断は正しい。
2. **`assign_lineages` が simulation RNG を消費しないことの実行時検証 (G9)**。この種の不変条件を assert で固定するのは良い習慣。
3. **Exp21 で mutation を OFF にした判断**。選択と変異を分離して測るのは正しい順序。
4. **Exp22 §8 の「OFF run にも同じ flux を与える」**。
5. **Exp22 §12 の候補抽出ルール事前固定**、特に §12.3 の「候補なしの場合に同じ Exp 内で flux を追加しない」。
6. **Exp22 §14 の「主張してよいこと / いけないこと」の明示**。
7. **Exp22 §5 の phenotype 定数がすべて実装 default と一致していること**を確認した (`phototrophy_seed_absorption=0.01`、`photo_apparatus_n_multiplier=10.0`、`bchl_extinction_mM_cm=213.0`、`light_effective_wavelength_nm=800.0`、`radiant_to_usable_eff=0.10`)。Exp20 Attempt 1 の config 不一致を繰り返していない。
8. **§3 G2 の effective config 照合**。Issue #72 で提案した G7 が採用されている。
9. **golden regression を re-pin せず実際に修正した判断** (`a3da144` の `energy_out_cum` 二段積算の復元)。前回 re-pin しないよう進言した件で、実際に本物の regression が見つかったことになる。

---

# 5. まとめ

**Exp21 は成立しており、結論も支持できる。** 4回連続で成立しなかった進化観測が、測り方を変えたことで通った。

Exp21 について推奨する修正は 2 点のみ:

```text
- A0 は検出力を持たない対照である (死亡0・出生数一致) ことを明記し、
  環境依存性の根拠を A2 の内部構造へ移す
- A2 の優位が死亡差と出生差に分解できることを結果考察へ載せる
- §8 の主張範囲を「standing variation に対する選択の成立」へ絞る
```

**Exp22 の計画も質が高い。** 実行前に直すべきは 3 点:

```text
M-1  flux = 0 を 1e-6 等へ置き換える (現状は構築不能で H4 が実行できない)
M-2  structural N cost が現環境で無効であることを明記し、
     cost 検証は N 律速条件の別実験へ分離する
M-3  §12.1 の候補条件へ人口統計効果の下限を追加し、
     working flux recommendation へ Exp23 の必要 seed 数見積もりを含める
```

加えて、§2.3 の flux–効果量表を事前登録へ含めることを推奨する。**preferred candidate は 0.05 (期待 R_E 1.31%) が最有力**で、マージンが薄いため 0.15 になる可能性もある。実測がこの表から大きく外れた場合、それは校正の問題ではなく実装の問題として扱えるので、G1 の実質的な合格基準として機能する。

---

# 6. 検証の再現方法

```bash
git worktree add /tmp/v111 origin/v1.11-phototrophy-plan
cd /tmp/v111 && uv sync

# flux 水準と理論効果量 / flux=0 が構築できないことの確認
EVOSIM_ROOT=/tmp/v111 uv run python \
  experiments/opus5_exp21_exp22_review_20260915/exp22_flux_effect_table.py

# structural N cost の大きさ
EVOSIM_ROOT=/tmp/v111 uv run python \
  experiments/opus5_exp21_exp22_review_20260915/exp22_structural_n_cost.py

# Exp21 の A0 対照が検出力を持つか (約28分。Exp21 harness をそのまま再実行)
EVOSIM_ROOT=/tmp/v111 uv run python \
  experiments/opus5_exp21_exp22_review_20260915/exp21_control_power.py
```

**いずれもシミュレーション実験ではなく解析計算である。正式実験ではない。**
