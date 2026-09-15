# Exp23 結果考察 / Exp24 実験計画 — Opus 5 レビュー

レビュー日: 2026-09-16
レビュー対象branch: `v1.11-phototrophy-plan` (`ade02af`)
対象文書:
- `docs/Exp23_結果考察.md`
- `docs/Exp24_実験計画.md` (`docs/Exp24_レビュー依頼.md` の12項目に回答)

参照: `docs/Exp22_Opus5レビュー.md` / Issue #76 / Actions run `34951226448`

レビュー種別: 結果レビュー + 実装前計画レビュー。
**仕様・候補値・判定基準・コードは一切変更していない。すべて変更提案である。**

検証スクリプト: `experiments/opus5_exp23_review_20260916/`

---

# 0. 要約

| | 判定 |
|---|---|
| Exp23 の結論 | **支持する。しかも公開された解析より証拠は強い。** |
| Exp23 の解析方法 | seed の対応構造を使っていない。**SHOULD FIX** |
| seed 23008 の扱い | 「検出できなかった seed」ではなく **退化した replicate**。**SHOULD FIX** |
| Exp24 の 6/8 基準 | **検出力 0.3–2.6%。MUST FIX** |
| Exp24 の single-origin lock | 統計的に致命的。**MUST FIX** |
| Exp24 の primary flux = 0.5 | single-founder assay では不適。**MUST FIX** |
| Exp24 の pairing 前提 (G6/G7) | **コード上正しい。そのまま進めてよい。** |

Exp23 は成功である。問題は次の Exp24 にあり、**現行計画のままでは機構が正しく働いていても
ほぼ確実に "Inconclusive" が返る。**

---

# 1. Exp23 — 公開値の独立再現

Actions run `34951226448` の各 run job ログに出力された summary から、24/24 run の
`final_f_photo` を取得し、公開表を再計算した。

| flux | median | mean | min | max | >50% |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.4965 | 0.4938 | 0.4444 | 0.5225 | 3/8 |
| 0.5 | **0.5565** | 0.5670 | 0.5000 | 0.6739 | **7/8** |
| 1.5 | **0.6317** | 0.6347 | 0.5000 | 0.7714 | **7/8** |

`docs/Exp23_結果考察.md` §2 の中央値・範囲・カウントは**すべて一致した。**

さらに seed 23007 / flux 0.0 をローカルで再実行したところ、
`final_f_photo = 0.4444444444444444` が CI と bit 一致した
(`f0_calibration.json` の `f0_mol_s = 4.890000722073717e-11` も一致)。
**数値再現性に問題はない。**

事前登録 gate との照合:

```text
F05: f_photo > 0.5 の seed 数 = 7/8   (>= 7 が strong support) -> PASS
F05: median f_photo = 0.5565          (>= 0.53)                -> PASS
```

**Exp23 の成功判定は正しい。**

---

# 2. Exp23 — 公開された解析は自分の結果を過小評価している

## 2.1 seed は対応ありブロックである

Exp23 は同一 seed の flux 0.0 / 0.5 / 1.5 で

- initial population
- lineage 割当 (blake2b, flux非依存)
- first origin 以前の dynamics

が完全に共通である。しかも Issue #76 で確定したとおり、**capability OFF 個体に flux は
物理的に到達しない**ので、flux を変えても共通部分は一切動かない。

つまり seed は **対応ありブロック**であり、`f_photo(0.5)` を定数 0.5 と比べるのではなく
**同じ seed の `f_photo(0.0)` と比べるのが正しい対照**である。

これは重要で、事前登録した「`f_photo > 0.5`」という帰無仮説は実は正しくない。
Exp22 で確認された apparatus の ON 側コストがあるぶん、光がなければ ON 系統はわずかに
不利なはずで、実際 flux 0.0 の中央値は 0.4965 / 平均 0.4938 と 50% をわずかに下回る。
定数 0.5 を基準にすると、この不利分だけ検出を損している。

## 2.2 対応あり解析の結果

各 seed 内の差:

| seed | Δ(0.5−0.0) | Δ(1.5−0.0) | Δ(1.5−0.5) |
|---:|---:|---:|---:|
| 23001 | +0.0190 | +0.0478 | +0.0288 |
| 23002 | +0.1263 | +0.1742 | +0.0479 |
| 23003 | +0.0689 | +0.0958 | +0.0269 |
| 23004 | +0.1008 | +0.2884 | +0.1875 |
| 23005 | +0.0254 | +0.0569 | +0.0315 |
| 23006 | +0.0164 | +0.1818 | +0.1654 |
| 23007 | +0.2295 | +0.2823 | +0.0528 |
| 23008 | 0.0000 | 0.0000 | 0.0000 |

```text
Δ(0.5−0.0): positive 7 / negative 0 / tie 1   符号検定 片側 p = 0.0078
Δ(1.5−0.0): positive 7 / negative 0 / tie 1   符号検定 片側 p = 0.0078
Δ(1.5−0.5): positive 7 / negative 0 / tie 1   符号検定 片側 p = 0.0078
```

さらに強いのは **seed ごとの単調性**である。

```text
seed 23001: 0.5225 < 0.5415 < 0.5703  YES
seed 23002: 0.4909 < 0.6172 < 0.6651  YES
seed 23003: 0.5025 < 0.5714 < 0.5983  YES
seed 23004: 0.4831 < 0.5839 < 0.7714  YES
seed 23005: 0.4930 < 0.5183 < 0.5499  YES
seed 23006: 0.5137 < 0.5301 < 0.6955  YES
seed 23007: 0.4444 < 0.6739 < 0.7267  YES
seed 23008: 全て 0.5000 — 情報なし
```

**情報のある 7 seed すべてで `f(0.0) < f(0.5) < f(1.5)` が厳密に成立している。**
3値の順序がランダムなら 1 seed あたり 1/6、7 seed 全部そろう確率は
`(1/6)^7 = 3.6e-6`。

公開文書は「flux 増加に対する中央値の応答は単調増加だった」と中央値の単調性しか
書いていないが、実際には**全 seed で個別に単調**である。これは中央値の単調性より
はるかに強い主張で、書かないのはもったいない。

## 2.3 SHOULD FIX

1. per-seed の 24 値の表を `docs/Exp23_結果考察.md` へ載せる (aggregate artifact にはあるが読めない)
2. primary 解析を「定数 0.5 との比較」から「同一 seed の flux 0.0 との対応あり比較」へ格上げする
3. seed ごとの単調性 7/7 を主結果として書く

これは事前登録の変更ではない。事前登録 gate は既に PASS しており、
**追加解析としてより強い証拠を提示するだけ**である。

なお §12 G9 の mirror-assignment diagnostic は、この対応あり解析があれば
本質的に不要になる。同一 seed で同じ割当を3 flux に使っている以上、割当バイアスは
差分で完全に打ち消される。

---

# 3. Exp23 — seed 23008 は「検出できなかった seed」ではない

seed 23008 は 3 flux すべてで `final_f_photo = 0.5` ちょうどである。

`docs/Exp23_結果考察.md` §6 は
「頻度が動かなかったことと生理的効果が存在しないことを同一視しない」
と書いており、方向としては正しい。しかし実際にはもう一段強いことが言える。

seed 23008 の flux 0.0 と flux 0.5 をローカルで再現した (どちらも
`final_f_photo = 0.5` が CI と一致)。timeseries は次のとおり。

```text
seed 23008 / flux 0.0
   t_h  N_OFF   N_ON      N   bOFF    bON   dOFF    dON      mOFF       mON
   0.0     50     50    100      0      0      0      0   25.0000   25.0000
  12.0     50     50    100      0      0      0      0   29.9836   29.8072
  24.0     50     50    100      0      0      0      0   35.6025   35.0334
  48.0     50     50    100      0      0      0      0   51.8585   50.4370
  72.0    100    100    200     50     50      0      0   75.2649   72.0615
  96.0    114    102    216     64     52      0      0  110.7141  104.3303
 120.0    200    200    400    150    150      0      0  159.3878  150.7339
```

```text
seed 23008 / flux 0.5
   t_h  N_OFF   N_ON      N   bOFF    bON   dOFF    dON      mOFF       mON
   0.0     50     50    100      0      0      0      0   25.0000   25.0000
  48.0     51     50    101      1      0      0      0   51.5168   51.3868
  72.0    100    100    200     50     50      0      0   74.4803   74.8216
  96.0    111    117    228     61     67      0      0  108.0152  110.2389
 120.0    200    200    400    150    150      0      0  154.9876  160.2700
```

**両条件とも deaths = 0 / 0、births = 150 / 150。**

この seed では資源が律速せず、全個体が同期して 2 回分裂しているだけである
(100 -> 200 -> 400、系統あたり 50 + 100 = 150 births)。
死亡が一度も起きず、出生が系統間で厳密に対称なので、

> **`f_photo` は 0.5 に数学的に固定されている。**

これは「選択が検出されなかった」のではなく、**この run には lineage frequency を
動かしうる demography が存在しない**ということである。

なお Exp21 の A0 対照で私が退化と指摘したときの数字も
births 150/150、deaths 0/0 で、**まったく同じ署名**である
(`docs/Exp21_Exp22_Opus5レビュー.md`)。

## 3.1 ただし 23008 は無情報ではない — biomass endpoint は効果を検出している

同じ run の `total_living_matter` を見ると:

| flux | OFF | ON | ON/OFF |
|---:|---:|---:|---:|
| 0.0 | 159.388 | 150.734 | **0.9457 (−5.43%)** |
| 0.5 | 154.988 | 160.270 | **1.0341 (+3.41%)** |

**frequency が構造的に動けない seed でも、biomass は光に応答している。**

しかも flux 0.0 の −5.43% は、Exp22 / Issue #76 で私が指摘した
「zero-light の ON 側系統的 penalty 約 −5.9%」と**独立に一致する**。
Exp23 は A2 / 120 h / 競争条件という別のセットアップだが、同じ大きさのコストが出ている。

これは Exp22 のコストが RNG divergence ではなく実在の ON 側コストであることの
3 つ目の証拠になる (コード経路 / OFF-run 恒等性 / 本 seed の biomass)。

**このことは結果考察に書く価値がある。**

## 3.2 SHOULD FIX

- 23008 を「ON が増えなかった 1 seed」として 8 の分母に数えるのをやめ、
  **frequency endpoint については degenerate replicate として明示的に分離する**
  (`n = 7 informative + 1 degenerate`)
- ただし §3.1 のとおり biomass endpoint では有効な replicate なので、
  run 全体を捨てないこと
- preflight に退化検出 gate を追加する:
  > competition run の births が系統間で厳密に対称、かつ deaths が 0 の区間が
  > run の大半を占める場合、その run は lineage frequency を動かしうる
  > demography を持たない。FAIL ではなく `DEGENERATE` として記録する。

これは Exp21 の A0 対照で私が指摘したのと同じ退化モードである
(`docs/Exp21_Exp22_Opus5レビュー.md`)。同じ形が2度出ているので、
gate 化して自動検出する価値がある。

---

# 4. Exp23 — 解釈上の注意 2 点

## 4.1 選択は連続競争ではなく turnover shock 2回で起きている

seed 23007 / flux 0.0 のローカル再現 timeseries:

```text
 t_h  N_OFF  N_ON    N    f_photo  bOFF  bON  dOFF  dON
 0.0     50    50  100     0.5000     0    0     0    0
12.0     50    50  100     0.5000     0    0     0    0
24.0     50    50  100     0.5000     0    0     0    0
48.0     50    50  100     0.5000     0    0     0    0
72.0     46    44   90     0.4889    36   32    40   38
96.0     53    57  110     0.5182    65   64    62   57
120.0    55    44   99     0.4444    85   78    80   84
```

**最初の 48 h は出生も死亡も 0 である。** 個体は成長しているだけで、demography は
まったく動かない。実際の出生・死亡は vent relocation (48 h ごと) の直後に集中する。

つまり Exp23 の 120 h run で系統頻度を動かす「試行」は実質 **2 回の turnover shock**
しかない。観測された頻度シフトは連続的な競争の積分ではなく、
**2 回の大量死亡・再生産イベントの結果**である。

これは結論を否定しないが、以下を意味する:

- seed 間のばらつきが大きいのは自然 (試行回数が少ない)
- 「selection coefficient」を 1/h で報告すると連続過程のように見えてしまう
- run を長くする (= turnover 回数を増やす) と効果は安定するはず

**SHOULD FIX**: 結果考察に「demography は turnover 駆動で、120 h は turnover 2 回分」
と明記する。

## 4.2 final N を併記していない

`f_photo` だけが報告されているが、これは `N_ON / N_total` であり、N によって
推定精度がまったく違う。公開値からは N を復元できない
(`f_photo` の最小分母は N の下限にしかならない。実際 seed 23007 / flux 0.0 は
最小分母 9 だが真の N は 99 だった)。

**SHOULD FIX**: 各 checkpoint の `N_OFF` / `N_ON` / `N_total` を結果考察に併記する。
timeseries.csv には既にある。

---

# 5. Exp24 — MUST FIX: 事前登録した 6/8 基準は検出力 0.3–2.6%

ここが本レビューの主眼である。

## 5.1 何が問題か

Exp24 §13 の strong-support 基準は

```text
paired-origin gate を通った seed の 6/8 以上で
N_photo(+240h, flux=0.5) > N_photo(+240h, flux=0.0)
```

である。founder は **1 個体**なので、この endpoint は
「1 個体から始まる系統が 240 h 後に何個体残っているか」という
branching process の実現値そのものである。

そして Exp23 の実測から、この系の人口動態は **臨界に近い**。

seed 23007 / flux 0.0 の実測 (§4.1):

```text
120 h で births = 163, deaths = 164, N: 100 -> 99
b ≈ 0.0136 /individual/h
d ≈ 0.0137 /individual/h
r = b - d ≈ 0
```

Exp24 §3 が引用する「flux=0 の総出生数中央値 ≈ 241 births/run」と
flux=0 の最終 N 中央値からも、ほぼ同じ `b ≈ 0.0185`, `d ≈ 0.0171`,
`r ≈ +0.0014 /h` が出る。

**臨界に近い branching process では、1 個体から始まる系統はほとんど絶滅する。**

## 5.2 定量

線形 birth-death 過程 (Kendall 1948 の解析解) で計算した。
利益が出生側に出る場合と死亡側に出る場合の両方を示す。
選択係数は Exp23 の中央値 `f_photo` の logit 傾きから推定
(`s(0.5) = 0.00201 /h`, `s(1.5) = 0.00461 /h`)。

### founder 1 個体の 240 h establishment probability

| flux | side | P_est(240h) |
|---:|---|---:|
| 0.0 | — | **0.223** |
| 0.5 | birth | 0.263 |
| 0.5 | death | 0.288 |
| 1.5 | birth | 0.315 |
| 1.5 | death | 0.386 |

つまり **どの条件でも founder lineage は 6–8 割の run で絶滅する。**

### paired endpoint の分布

| flux | side | P(>) | P(=) | うち両方絶滅 | P(<) |
|---:|---|---:|---:|---:|---:|
| 0.5 | birth | 0.237 | 0.576 | 0.572 | 0.186 |
| 0.5 | death | 0.256 | 0.559 | 0.554 | 0.185 |
| 1.5 | birth | 0.291 | 0.537 | 0.533 | 0.172 |
| 1.5 | death | 0.352 | 0.483 | 0.477 | 0.165 |

**約半数の seed で `0 対 0` の tie になる。** tie は `N_photo(0.5) > N_photo(0.0)` を
満たさないので失敗としてカウントされる。

### 6/8 基準の検出力

| flux | side | P(>) | P(>=6/8) | P(>=7/8) |
|---:|---|---:|---:|---:|
| 0.5 | birth | 0.237 | **0.003** | 0.000 |
| 0.5 | death | 0.256 | **0.005** | 0.000 |
| 1.5 | birth | 0.291 | **0.010** | 0.001 |
| 1.5 | death | 0.352 | **0.026** | 0.004 |

**primary (0.5) の検出力は 0.3–0.5%。positive control (1.5) ですら 1–3%。**

機構が完全に正しく動いていても、Exp24 は 97% 以上の確率で
「Inconclusive」を返す。

### 感度解析

flux=0 の最終 N を 55–500 まで振っても結論は変わらない。

| N_final | b | d | r | P_est(0.0) | P_est(0.5) | P(>=6/8) |
|---:|---:|---:|---:|---:|---:|---:|
| 55 | 0.02668 | 0.03166 | −0.00498 | 0.064 | 0.088 | 0.000 |
| 80 | 0.02241 | 0.02427 | −0.00186 | 0.120 | 0.160 | 0.000 |
| 118 | 0.01847 | 0.01709 | +0.00138 | 0.223 | 0.288 | 0.005 |
| 200 | 0.01392 | 0.00814 | +0.00578 | 0.486 | 0.600 | 0.105 |
| 350 | 0.01006 | 0.00000 | +0.01006 | 1.000 | 1.000 | 0.115 |
| 500 | 0.00808 | 0.00000 | +0.00808 | 1.000 | 1.000 | 0.101 |

N_final >= 350 の行は deaths が 0 に張り付く非物理な極限だが、
**その極限まで含めても検出力は最大 0.12 程度**で 0.8 には遠く届かない。

## 5.3 これは Exp20 Attempt 2 と同じ失敗形である

`docs/Exp20_Attempt2_Opus5レビュー.md` で指摘したのと同型の問題である。
endpoint の分散を見積もらずに seed 数と判定基準を決めている。

**formal run を開始する前に検出力計算を必ず実施する**ことを、
Exp25 以降の恒久ルールとして `docs/実験結果保存方針.md` か
`AGENTS.md` に追記することを提案する。

---

# 6. Exp24 — MUST FIX の修正案

## 6.1 single-origin lock をやめ、per-origin tagging にする

Exp24 §4 は first origin 検知後に `phototrophy_innovation_prob = 0` へ切り替える。
その動機 (「増えた理由が最初の系統の選択か、供給の繰り返しかを分離できなくなる」)
は正当だが、**分離は供給を止めることではなく、origin ごとに tag を付けることで達成できる。**

`p = 0.01/birth` を維持した場合の origin 供給量:

```text
240 h: births ≈ 525  -> 期待 origin 数 ≈  5.25
480 h: births ≈ 1257 -> 期待 origin 数 ≈ 12.6
```

single-origin lock は **1 run あたり 12 個の独立 replicate を 1 個に捨てている。**

提案:

- innovation を止めない
- innovation event ごとに一意の `photo_founder_id` を付与する
- founder ごとに独立した invasion replicate として追跡する
- endpoint を「origin あたりの establishment 確率」にする

これで解釈可能性は保たれ、replicate 数が 10 倍以上になる。

## 6.2 primary flux を 1.5 にする

Exp23 では primary を 0.5 にしたのが正しかった。50 個体から始めるので
drift は小さく、0.5 の効果でも見える。

しかし **founder 1 個体の invasion assay では話が違う。** 1 個体から始まる系統の運命は
drift が支配し、signal が drift を上回るには選択係数がずっと大きい必要がある。
上表のとおり 0.5 と 0.0 の establishment 確率差は 4–7 pt しかないのに対し、
1.5 と 0.0 は 9–16 pt ある。

提案:

```text
primary        : flux 1.5   (de novo origin が定着しうることの実証)
secondary      : flux 0.5   (推定値と CI を報告。検定はしない)
negative control: flux 0.0
```

「0.5 でも見える」は Exp23 が既に示している。Exp24 の新しい問いは
「rare origin から始まっても選択が効くか」であり、それはまず強い光で示すのが筋である。

## 6.3 post-origin window を 240 h より長くする

臨界に近い過程では、生存確率は `t -> inf` で `1 - d/b` に収束する。
絶対値は下がるが**条件間の相対差は広がる**ため、window を伸ばすと
必要 origin 数はむしろ減る。

| window [h] | P_est(0.0) | P_est(0.5) | n/群 (0.5) | P_est(1.5) | n/群 (1.5) |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.223 | 0.288 | 707 | 0.386 | 123 |
| 480 | 0.143 | 0.219 | 405 | 0.337 | 75 |
| 960 | 0.099 | 0.189 | 237 | 0.325 | 51 |
| 1920 | 0.080 | 0.184 | 166 | 0.324 | 42 |
| ∞ | 0.075 | 0.183 | 149 | 0.324 | 39 |

(両側 alpha=0.05, power=0.80, death-side advantage)

**240 h は「定着したかどうか」を決めるには短すぎる。**
§4.1 のとおり 240 h は turnover 5 回分でしかない。
960 h (turnover 20 回) なら必要 origin 数が flux 0.5 で 707 -> 237、
flux 1.5 で 123 -> 51 まで下がる。

## 6.4 まとめた設計案

```text
環境        : A2_DYNAMIC_VENT (Exp23 と同一)
flux        : 0.0 / 0.5 / 1.5  (primary = 1.5)
innovation  : 0.01 /birth を run 全体で維持 (lock しない)
loss        : 0
founder追跡 : innovation event ごとに photo_founder_id を付与
window      : origin 後 960 h (または総 run 長を固定して origin ごとに打ち切り)
seeds       : 16 (3 flux x 16 = 48 runs)
供給見込み  : 1 run あたり origin 25 以上 -> 1 群 400 origin 以上
primary     : origin あたりの establishment 確率 (flux を説明変数とする二項/logistic)
secondary   : founder lineage サイズ分布、milestone 到達時刻
```

これなら flux 1.5 (必要 51) も flux 0.5 (必要 237) も十分カバーできる。

計算量の注意: 1 job で 3 flux を回すと Actions の `timeout-minutes: 300` に当たる。
**flux を別 job へ分ける**こと。

## 6.5 single-origin design を残したい場合

mechanism demonstration としてなら価値がある。その場合は
**仮説検定ではなく実証として位置づけ、成功基準から 6/8 を外す**こと。

```text
Exp24a (mechanism, 8 seeds, single-origin):
  G0-G10 が PASS し、origin が発生し、継承され、
  生き残った系統の軌跡が Exp23 で測った s と整合することを示す。
  -> 「機構が動く」ことの実証。検定はしない。

Exp24b (selection, §6.4 の設計):
  origin あたり establishment 確率の光依存性を検定する。
```

---

# 7. Exp24 — レビュー依頼 12 項目への回答

## Q1. default `1e-4/birth` をそのまま使わない判断は妥当か

**妥当。** §3 の計算 (241 births × 1e-4 = 0.024 events/run) は正しい。
私の推定でも 240 h で期待 origin 数 0.05、480 h で 0.13 にしかならない。
待ち時間圧縮は必要である。

## Q2. accelerated `0.01/birth` は妥当か

**妥当。** 理由は2つ。

1. `structural_mutate()` は capability 状態に関わらず **出生ごとに必ず RNG を 2 回消費する**
   (`evosim/genome.py` の `r_photo = rng.random()` と `_r_predation = rng.random()`)。
   したがって innovation 確率を変えても RNG 消費数は変わらず、determinism と
   flux 間 pairing は壊れない。
2. innovation 確率は Phototrophy の fitness を一切変えない。
   変えるのは起源の待ち時間だけである。

ただし §6.1 のとおり、**この高い供給を lock で捨てるのはもったいない。**

## Q3. first origin 後に innovation を 0 にする single-origin design は妥当か

**問いに対しては妥当だが、統計的に成立しない。** §5 / §6.1 を参照。
解釈可能性は per-origin tagging で確保できる。

## Q4. `phototrophy_loss_prob` は 0 にすべきか、default `1e-3` を残すべきか

**0 でよい。** 理由:

- founder lineage は多くても数個体・数出生なので、`1e-3/birth` の loss が
  効く確率は 1% 未満。科学的にはほぼ何も変わらない。
- 一方で loss > 0 だと `phototrophy_on` が「founder の子孫」の同義でなくなり、
  Q7 の前提が崩れる。

つまり loss=0 は**コストゼロで解釈を単純化する**。採用してよい。
ただし Q7 の回答のとおり、founder tagging は別途入れること。

## Q5. waiting window 240h + post-origin 240h は十分か

**waiting は十分すぎるほど。post-origin は不十分。**

- waiting: 期待 origin 数 5.25、`P(origin なし) = e^-5.25 = 0.5%`。
  240 h で十分。ただし §4.1 のとおり **最初の 48 h は出生が 0** なので、
  実効的な待ち時間は 240 h ではなく約 192 h であることに注意。
- post-origin: §6.3 のとおり 240 h では短い。960 h 以上を推奨。

## Q6. first origin が flux 間で完全 pairing できるという前提はコード上正しいか

**正しい。** 2つの独立した根拠がある。

1. **コード**: `light_photon_flux_umol_m2_s` が読まれるのは
   `evosim/physiology.py:193` (`physical_light_incident_power_w()`) の 1 箇所だけで、
   そこへ到達するのは `photo_power_chain_w()` 経由のみ。この関数は
   `not org.phototrophy_on` なら即 return する。全個体 OFF の間は到達不能。
   さらに `structural_mutate()` は出生ごとに固定回数の RNG を消費する (Q2)。
2. **実測**: Issue #76 で、capability OFF の集団を flux 0.0 / 0.5 / 1.5 で走らせ、
   `total_living_matter = 70.7663448673` が完全一致することを確認済み。

したがって G6 / G7 は通るはずである。**通らなかったら本当に bug なので、
gate として残す価値は高い。**

## Q7. first origin 後、全 ON 個体を founder の子孫とみなしてよいか

**`innovation = 0` かつ `loss = 0` ならよい。しかしそれに依存すべきではない。**

理由: `evosim/simulation.py` の子生成は

```python
child = Organism(self.next_id, org.id, org.lineage_id, ...)
```

であり、**子は親の `lineage_id` を継承する**。innovation で生まれた founder は
OFF の親の `lineage_id` を持つので、Exp23 で使った「`lineage_id` が `on_ids` に
含まれるか」という判定は Exp24 では使えない。

現行提案 (innovation=0, loss=0) なら `phototrophy_on` が founder 子孫と同値になるが、
これは2つの設定に暗黙依存した脆い前提である。

**MUST FIX**: `Organism` に `photo_founder_id` を持たせ、
innovation 時に自分の id を、以後は親から継承する。
recurrent innovation (§6.1) へ進むときにも必須になる。

## Q8. 8 seed で十分か

**不十分。** §5.2 / §6.3 のとおり、single-origin design なら flux 1.5 で 123 origin、
flux 0.5 で 707 origin が必要 (240 h window)。
§6.4 の recurrent + per-origin tagging 設計なら 16 seeds で足りる。

## Q9. strong-support の 6/8 基準は妥当か

**妥当でない。** 検出力 0.3–2.6%。§5.2 を参照。

## Q10. 追加すべき mechanical gate / lineage tracking はあるか

**ある。3 つ。**

### G11 — same-tick multiple origin

`structural_mutate()` は出生ごとに呼ばれ、1 tick に複数の出生が起きうる。
single-origin lock を tick 末で適用すると、**同一 tick 内に 2 個以上の founder が
生まれうる**。

gate: origin tick の新規 ON 個体数が厳密に 1 であることを assert する。
あるいは lock を出生ループの内側で適用する。

### G12 — founder apparatus assembly

innovation で生まれた founder は OFF 親から `photo_structural_n_mol` を
受け取れない (`n_transfer` が 0)。したがって **founder は BChl apparatus を
局所 fixed N からゼロから組み立てる必要がある** (`_assemble_photo_structural_n`)。
組み立てが終わるまで photo credit は 0 である。

Exp23 の ON 個体は t=0 の成体だったので、この立ち上げコストは測っていない。
**founder の apparatus assembly 完了時刻と、その間に失った credit を記録すること。**
§5 の establishment 確率推定はこの立ち上げを無視しているので、
**実際の P_est はさらに低い可能性がある。**

### G13 — degenerate run 検出

§3.1 の退化検出 gate を Exp24 にも入れる。

## Q11. single-origin assay より recurrent-innovation assay を先にすべき理由があるか

**ある。統計的な理由で、recurrent を先にすべきである。**

recurrent innovation は 1 run あたり 10 個以上の独立 origin を供給する
(§6.1)。single-origin design はそれを 1 に絞る。
必要 origin 数が 50–700 の桁である以上、**recurrent 以外に到達手段がない。**

「解釈が混ざる」という懸念は per-origin tagging で解消できる (Q7 / §6.1)。

したがって Exp24 §17 の「Exp25 で recurrent へ進む」という順序は逆にすべきである。

## Q12. 成功時に「de novo Phototrophy evolution」と表現できる範囲

以下は言える:

> 実装された structural innovation 経路により Phototrophy capability を持たない
> 集団から能力が新規に出現し、子孫へ継承され、その系統の定着確率が
> 光量に依存する。

以下は言えない:

- 「Phototrophy が自然な速度で進化する」— `p = 0.01/birth` は default の 100 倍
- 「Phototrophy が集団に固定される」— 定着確率が数十%でも固定とは別物
- 「起源機構の再現」— 実装は capability flag の切替であって生化学ではない
- mutation-selection balance に関する何か — loss を 0 にしているため

特に **innovation 確率を上げていることを結論文へ必ず明記する**こと。
Exp24 §16 は既にそう書いており、その姿勢は維持してほしい。

---

# 8. 維持すべき点

- **Exp23 の設計そのもの。** Issue #75 で推奨した 8 seeds / primary 0.5 /
  positive control 1.5 をそのまま実装し、結果を見て seed も flux も動かしていない。
  事前登録の運用として模範的である。
- **Exp22 で R_E が primary として不適だったという自己診断を Exp23 へ反映したこと。**
  lineage frequency を primary に据えた判断は正しく、実際に効果が出た。
- **flux=0 を negative control として正式に走らせたこと。** これがあるおかげで
  §2 の対応あり解析が可能になっている。設計時点でこれを入れたのは good call。
- **`docs/Exp24_レビュー依頼.md` を分離して「レビュー前に実装しない」と明記したこと。**
  Exp20 の手戻りを踏まえた運用改善として有効に機能している。
- **Exp24 §16「まだ言えないこと」の書き方。** 加速した innovation 率を
  進化速度の推定に使わないと明記している点は維持すること。

---

# 9. SHOULD FIX (Exp23 側、軽微)

`docs/実験結果保存方針.md` が要求する成果物のうち、Exp23 では以下が未作成:

- `experiments/exp23_phototrophy_competition/NOTES.md`
- `experiments/exp23_phototrophy_competition/figures/` (集計プロット + `README.md`)

最低限、flux vs final f_photo の per-seed プロットと、
代表 seed の f_photo(t) 時系列プロットは価値がある
(§4.1 の「48 h まで何も起きない」構造は図にすると一目で分かる)。

---

# 10. 再現方法

```bash
git worktree add /tmp/e23 origin/v1.11-phototrophy-plan
cd /tmp/e23 && uv sync

# Exp23 の対応あり解析 (simulation 不要、即座に終わる)
python experiments/opus5_exp23_review_20260916/exp23_paired_statistics.py

# Exp24 の検出力計算 (simulation 不要、数秒)
python experiments/opus5_exp23_review_20260916/exp24_single_origin_power.py

# 公開値のローカル再現 (1 run 約 10 分)
uv run python experiments/exp18_v1101_dynamic_vent/phase0.py phase0_local.json
uv run python experiments/exp23_phototrophy_competition/run_exp23.py \
  --seed 23007 --flux 0.0 --hours 120 --calibration-dir . --outdir repro_23007_f00
```

**いずれも正式実験ではなく診断である。**
