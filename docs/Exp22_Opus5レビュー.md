# Exp22 結果考察 — Opus 5 レビュー

レビュー日: 2026-09-15
レビュー対象branch: `v1.11-phototrophy-plan` (`230d80f`)
対象文書: `docs/Exp22_結果考察.md`
参照: `docs/Exp22_実験計画.md` / `docs/Exp21_Exp22_Opus5レビュー.md` / Issue #75

レビュー種別: 結果レビュー。**仕様・候補値・判定基準・コードは一切変更していない。すべて変更提案である。**

検証スクリプト: `experiments/opus5_exp22_review_20260915/`

---

# 0. まず自己訂正

Issue #75 で私は依頼6 (primary を R_E にすることの妥当性) へ

> **A2 では妥当、A0 では注記が要ります。**

と答え、flux ごとの期待 R_E 表まで出した。**これは誤りだった。**

私自身が A0 について指摘した機構 — 個体が保護 reserve に張り付いているので credit は stored Energy ではなく成長へ回る — は **A2 でも同じく働く**。A2 の 48–72 h を「純粋な drain 局面」と仮定したのが間違いで、実際には turnover 後も多くの個体が H2 の残る領域で成長を続けている。

`NO_WORKING_FLUX_IN_RANGE` はその帰結であり、**§4 の診断 (stored Energy を primary にしたこと自体が不適切だった) が正しい。**

ただし表の物理部分 (credit / maintenance) は有効である。応答変数を stored Energy から total living matter へ置き換えると、実測とよく合う (§1)。

---

# 1. 総評 — credit fraction は生態効果をよく予測する

Issue #75 の表の「期待 R_E」列を「期待 Δ total living matter」と読み替えて実測と並べる。

| flux | credit / maintenance | 実測 Δmatter (raw) | zero-light 補正後 |
|---:|---:|---:|---:|
| 0.015 | 0.39% | −7.42% | −2.86% |
| 0.05 | 1.31% | −5.65% | −1.09% |
| 0.15 | 3.93% | +2.22% | +6.78% |
| 0.5 | **13.09%** | +12.40% | **+18.3%** (§3 の報告値) |
| 1.5 | **39.28%** | +55.35% | **+59.91%** |

0.5 で予測 13.1% に対し補正後 18.3% (1.4 倍)、1.5 で予測 39.3% に対し 59.9% (1.5 倍)。低 flux 域は雑音に埋もれているが、**効果が見える領域では credit fraction が生態効果を 1.0–1.5 倍の精度で予測している。**

これは Exp23 以降の flux 選択に直接使える。新しい flux 候補を出すたびに 72 run を回さなくても、`credit / maintenance` を計算すれば効果量の見当がつく。

**Exp22 は calibration として成功しており、§8 の判定に同意する。**

---

# 2. F-1 — OFF run は flux に依存しない【実証済み】

## 2.1 コード経路

`light_photon_flux_umol_m2_s` はコード中 **1 箇所**でしか読まれない。

```text
evosim/physiology.py:193   physical_light_incident_power_w()
  <- photo_power_chain_w()   … not org.phototrophy_on なら (0,0,0) を返す
```

`run_exp22.setup_paired()` は `capability_on=False` のとき `exp18_core.setup_sim()` をそのまま呼ぶだけで、OFF 側には何も追加しない。

**したがって全個体 OFF の run では flux はどこにも到達しない。**

## 2.2 実測

`experiments/opus5_exp22_review_20260915/exp22_off_run_flux_independence.py`
(A2_DYNAMIC_VENT / seed 22001 / 24 h / capability OFF):

```text
flux=0.0   population=100  total_living_matter=70.7663448673  births=100  deaths=0
flux=0.5   population=100  total_living_matter=70.7663448673  births=100  deaths=0
flux=1.5   population=100  total_living_matter=70.7663448673  births=100  deaths=0

全fluxで OFF run が完全一致 : YES
initial fingerprint 一致    : YES
```

**12 桁一致。** OFF run は flux に完全に依存しない。

## 2.3 これが §2 / §5 の解釈を変える

(environment, seed) を固定すると、**6 つの flux 水準の OFF run はすべて同一**である。したがって:

```text
誤りやすい読み : §2 の6行は6つの独立した比較である
正しい読み     : §2 の6行は「同一のOFF baseline」に対する6回のON側測定である
```

この帰結として、**§5 の「zero-light でも -4.56% が出る」は RNG trajectory divergence では説明できない。** OFF 側は完全に固定されているので、divergence が起きるとすれば ON 側だけである。つまり -4.56% は **ON 側の系統的な差**を測っている。

しかも 0 / 0.015 / 0.05 の3行は、いずれも光の寄与が無視できる大きさ (credit ≤ 1.31% of maintenance) なので、**実質的に同じ量を3回測っている**:

```text
-4.56% , -7.42% , -5.65%   ->  平均 約 -5.9%
```

## 2.4 -5.9% は既知のコストで説明できない

Issue #75 で実測した ON 側のコストは:

```text
structural N cost   : 個体 biomass N の 0.565%  (環境Nの 0.0113%)
organ upkeep 増     : maintenance の 0.06%
合計                : 1% 未満
```

**観測された -5.9% はこの 1 桁上である。**

§5 は「structural N cost は小さいので、RNG divergence が A2 で増幅された可能性が高い」としているが、§2.2 のとおり OFF 側は固定なので、この説明は成立しない。ON 側だけで -5.9% を生む何かがある。

## 2.5 推奨 — A0 の結果を報告すれば切り分けられる

**Exp22 の 72 run のうち 36 run は A0_STATIC だが、§2 には A2 の結果しか載っていない。**

A0 は (Exp21 のレビューで実測したとおり) 120 h でも飢餓死が発生せず、turnover も無い。つまり **trajectory divergence が最小の環境**である。したがって:

```text
A0 の flux=0 で ON/OFF 差が ≈ 0      -> -5.9% は A2 の divergence 増幅
A0 の flux=0 でも ON/OFF 差が負      -> ON 側に未特定の系統的コストがある
```

**この判別に必要なデータは既に手元にある。** §2 へ A0 の表を追加することを推奨する。

あわせて preflight gate に次を追加することを推奨する。

```text
G8 (提案) — OFF run flux independence
  同一 (environment, seed) の OFF run が、全 flux 水準で完全一致すること。
  一致しなければ flux が OFF 経路へ漏れており、それ自体が bug。
```

これは property test であり、将来 daylight coupling 等を足したときの回帰検出にも効く。

---

# 3. Exp23 に必要な seed 数【依頼5への回答】

§7 D2 のとおり未実装なので、ここで計算する。
`experiments/opus5_exp22_review_20260915/exp23_seed_requirement.py`。

## 3.1 雑音床 (Exp21 から)

```text
median 56.3% / min 45.6% / max 63.3% / n=8
range/SD(n=8) ≈ 2.85  ->  SD ≈ 6.21 pt , SE ≈ 2.20 pt
観測シフト 6.3 pt -> t ≈ 2.87  (報告の 7/8 と整合)
```

## 3.2 Exp22 の効果量を頻度シフトへ換算

monoculture の total living matter 比 (1+r) を per-capita 成長差とみなし、`s = ln(1+r)/72h` を Exp23 の 120 h へ外挿する。

| flux | Δmatter(72h) | s [/h] | 頻度(120h) | シフト | 必要 seed (2σ) |
|---:|---:|---:|---:|---:|---:|
| 0.15 (raw) | 2.22% | 0.00030 | 50.9% | 0.9 pt | 184 |
| 0.15 (補正) | 6.78% | 0.00091 | 52.7% | 2.7 pt | 21 |
| **0.5 (raw)** | 12.40% | 0.00162 | 54.9% | **4.9 pt** | **6.5** |
| **0.5 (補正)** | 18.30% | 0.00233 | 57.0% | **7.0 pt** | **3.2** |
| 1.5 (raw) | 55.35% | 0.00612 | 67.6% | 17.6 pt | 0.5 |

## 3.3 結論

**flux=0.5 の期待シフトは 4.9–7.0 pt で、Exp21 が 8 seed で検出した 6.3 pt と同オーダー。8 seed で足りる見込みである。**

ただし Exp22 の flux=0.5 は 3 seed 中 1 seed がほぼ中立だったので、実際のシフトが 4 pt を下回ると 8 seed では不足する (n ≈ 10–16 が必要)。

**推奨: flux=0.5 を primary、flux=1.5 を positive control として同じ seed 数で併走させる。**

0.5 が null でも 1.5 が明確に正なら「アッセイの失敗」ではなく「0.5 では効果量が小さい」と読める。結果を見てから seed を追加するのは optional stopping になるので、**seed 数は事前登録で固定すること。**

---

# 4. 依頼事項への回答

### 1. `0.5` を Exp23 primary flux とする判断は妥当か

**妥当。** §3.3 のとおり期待シフトが Exp21 の検出実績と同オーダーで、しかも §1 の credit fraction (13.1%) からも「中程度」の位置にある。1.5 (39.3%) は明らかに強すぎ、0.15 (3.9%) は §3.2 で 21 seed 必要になる。**0.5 が唯一、現実的な seed 数で測れる水準である。**

### 2. `1.5` を positive control として併用すべきか

**すべき。** §3.3 のとおり、0.5 が null だったときに「効果量が小さい」と「アッセイが壊れている」を切り分けられるのはこれだけである。この種の control が無かったことが Exp18 Phase B / Exp20 Attempt 2 の解釈を難しくした。

コストも小さい (同じ harness、seed 数も同じ)。

### 3. zero-light A2 差 (median −4.56%) の原因解釈に問題がないか

**問題がある。** §2 のとおり、OFF 側が flux に依存しないことを実証したので、「RNG trajectory divergence が A2 で増幅された」という §5 の説明は成立しない。ON 側だけで −5.9% を生む何かがあり、既知コスト (1% 未満) では 1 桁足りない。

**A0 の結果を §2 へ載せれば切り分けられる** (§2.5)。データは既にある。

### 4. R_E を candidate 判定から外す修正は妥当か

**妥当。** §0 のとおり、R_E を A2 の primary として推奨したのは私の誤りだった。population / starvation deaths / total living matter を fitness 側の主要指標にする §4 の修正に同意する。

R_E を mechanistic diagnostic として残す判断も正しい。credit が実際に maintenance を肩代わりしているかの確認には依然として使える。

### 5. Exp23 で必要な seed 数

**8 seed。** 根拠は §3。1.5 の positive control も同じ 8 seed で。

### 6. flux=0 を Config 変更で許容した実装変更を正式採用してよいか

**採用してよい。** 私は Issue #75 で `1e-6` への置換を提案したが、**`flux=0` を許容する方が素直で良い**。「light は有効だが光量ゼロ」は物理的に意味のある状態で、`1e-6` のような人工的な値を持ち込まずに済む。

ただし事前登録からの変更 (D1) なので、以下を推奨する。

```text
- validation の意味変更を pin する test を追加する
  (physical_light_enabled=True かつ flux=0 で
   photo_incident/absorbed/usable/used がすべて厳密に 0)
- 負値は引き続き拒否されることも test する
```

### 7. Exp23 前に追加すべき mechanical / statistical gate

**3 つ推奨する。**

```text
G8 — OFF run flux independence (§2.5)
     同一 (env, seed) の OFF run が全 flux で完全一致すること

G9 — A0 zero-light control の報告
     §2 へ A0 の表を追加し、-5.9% の出所を切り分けてから Exp23 へ進む

G10 — seed 数の事前固定
     §3 の計算を recommendation artifact へ残し、
     結果を見てからの seed 追加を禁止する (optional stopping 対策)
```

---

# 5. 実装・事前登録との差分 (§7) について

### D1 — flux=0 の扱い

§4 の依頼6 のとおり **採用してよい**。test で意味を pin すること。

### D2 — Exp23 必要 seed 数の見積もり未実装

§3 で計算した。`exp23_seed_requirement.py` をそのまま流用できる。

### D3 — candidate ロジックが旧 R_E 中心のまま

`NO_WORKING_FLUX_IN_RANGE` を生物学的結論として採用しないという判断は正しい。

ただし **aggregate のロジックは Exp23 前に直しておくべき**である。直さないまま次へ進むと、Exp23 の aggregate も同じ理由で誤った gate 結果を返しうる。§4 で決めた fitness 指標 (population / deaths / total living matter) で candidate を判定するよう書き換えること。

---

# 6. 維持すべき点

1. **G0 の実装が正しい。** `_absorb_light()` 冒頭の `if cfg.physical_mode: return` は、arbitrary mode の後方互換を保ちつつ physical mode の経路を完全に塞いでいる。Exp20 Attempt 1 の原因は解消された。
2. **72/72 run 完了、preflight / aggregate とも成功。** 前回までの実行ブロッカーが片付いている。
3. **§4 の自己診断。** 事前登録した primary 指標が不適切だったことを、結果を見て正直に認めている。しかも「だから閾値を下げる」ではなく「指標を変える」と正しい方向へ修正している。
4. **§7 で事前登録との差分 D1–D3 を自己申告していること。** 特に D3 で「`NO_WORKING_FLUX_IN_RANGE` を生物学的結論として採用しない」と明示したのは重要。
5. **§8 で「まだ確認していないこと」を5項目挙げていること。**
6. **§1 の位置づけ (Exp22 は「進化するか」を見る実験ではない)** を最後まで守っていること。

---

# 7. まとめ

**Exp22 は calibration として成功しており、`0.5` を Exp23 primary とする判断も妥当である。**

私の Issue #75 の R_E 推奨は誤りで、§4 の修正が正しい。ただし表の物理部分は有効で、応答変数を total living matter に置き換えると **credit fraction が生態効果を 1.0–1.5 倍の精度で予測する** (§1)。これは今後の flux 選択に使える。

Exp23 へ進む前に片付けるべきは 3 点:

```text
1. A0 の結果を §2 へ載せ、zero-light の -5.9% の出所を切り分ける
   (OFF run は flux 非依存と実証したので、RNG divergence では説明できない)
2. aggregate の candidate ロジックを R_E から fitness 指標へ書き換える
3. Exp23 の seed 数を 8 で事前固定し、1.5 を positive control として併走させる
```

1 は追加実験なしで済む (データは既にある)。

---

# 8. 検証の再現方法

```bash
git worktree add /tmp/v111 origin/v1.11-phototrophy-plan
cd /tmp/v111 && uv sync

# OFF run が flux に依存しないこと (約3分)
EVOSIM_ROOT=/tmp/v111 uv run python \
  experiments/opus5_exp22_review_20260915/exp22_off_run_flux_independence.py

# Exp23 の必要 seed 数 (simulation 不要)
uv run python \
  experiments/opus5_exp22_review_20260915/exp23_seed_requirement.py
```

**いずれもシミュレーション実験ではなく診断である。正式実験ではない。**
