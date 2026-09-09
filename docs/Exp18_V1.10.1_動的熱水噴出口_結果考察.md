# Exp18 — V1.10.1 動的熱水噴出口 結果・考察

更新: 2026-09-09  
状態: **ATTEMPT 1 PARTIAL COMPLETE / Phase Bは計算時間制限により未完**

正本計画:

- `docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md`
- `docs/V1.10.1_動的熱水噴出口_実装方針.md`

実行:

- GitHub Actions run: `34179590147`
- formal head SHA: `649151cf70f41547513053d4ebac41f900391c78`

---

## 1. Exp18の目的

Exp18の中心目的は、H2の**総供給量そのものを極力変えず**に、熱水噴出口の時間変動・位置turnoverを与えたとき、固定iLUCAおよび進化可能集団へどのような選択圧が生じるかを確認することであった。

V1.10.1では、従来の「source cellを常に10 mMへ戻すDirichlet source」から、実測した有限H2 fluxを供給するvent表現へ移行した。

またV1.10で確定したC/N/Pについては、Exp17 Phase C1のhuman decisionに基づき、初期100個体の要求量に対して50 biomass-equivalentsを配置し、background exchangeはOFFとした。

---

# 2. Phase 0 — source機構検証

Phase 0は全項目PASSした。

旧V1.10の4 source / 10 mM Dirichlet環境を6 h warm-upし、定常状態で実際に必要だったH2補給量を測定した結果:

```text
F0 = 4.890000722073717e-11 mol/s / vent
4 vents total = 1.9560002888294868e-10 mol/s
```

確認結果:

- finite-flux source ledger: PASS
- H2 field nonnegative / finite: PASS
- concentration gradient形成: PASS
- static vs temporalの積算H2供給量一致: 完全一致
- vent turnover geometry / RNG再現性: PASS
- organism RNGとの独立性: PASS
- dt=5 s / 10 s convergence: PASS
  - final H2 stock差 約0.56%
  - radial concentration差 約0.38%

### Phase 0結論

**V1.10.1のfinite-flux / temporal / turnover vent機構は、少なくとも数値・ledger・再現性の面では成立している。**

したがってPhase A以降で生じた生態差は、まず環境条件そのものの差として解釈してよい。

---

# 3. Phase A — fixed iLUCA / 10日

全continuous genes固定、3 seeds (`18001-18003`) で4条件を比較した。

| 条件 | vent条件 | 生存 | 最終個体数 | 最大世代 | 解釈 |
|---|---|---:|---:|---:|---|
| A0 | static finite flux | 3/3 | 2287–2352（平均2311） | 5 / 5 / 5 | 安定control |
| A1 | temporalのみ | 0/3 | 0 | 0–2 | 強すぎる時間変動 |
| A2 | turnoverのみ | 3/3 | 37–670（平均345） | 6–9 | 強いが持続可能 |
| A3 | temporal + turnover | 2/3 | 0–26（平均10.3） | 0–9 | 生存限界付近 |

全complete runでC/N/P ledgerは有効であり、Energy ledger residualも十分小さかった。

---

## 3.1 A0 — finite flux化だけならiLUCAは成立

A0は全seedで10日生存し、最終個体数は約2300、最大世代は5だった。最終starvation-active fractionは全seedで0だった。

V1.10のDirichlet source環境より個体数はやや低下したが、これは無限に濃度を固定するsourceから有限flux sourceへ変更したことによる自然な差と考えられる。

### 結論

**有限flux化そのものはiLUCAの成立を壊していない。**

---

## 3.2 A1 — H2総量が同じでも時間変動だけで全滅

A1では、常に2 ventsだけをONとし、ON ventは2F0を供給することで、世界全体の瞬間総fluxをA0と同じ4F0に維持した。

Phase 0でもstaticとtemporalの積算source molは完全一致している。

それにもかかわらず3/3 seedが絶滅した。

このことから、現在のiLUCAにとって重要なのは単純なH2総量だけではなく、**H2が時間的に連続して利用できること**である。

H2 loss時定数は900 s（15 min）に対してventのOFF区間は6 hであるため、OFFになった領域ではH2環境が比較的速く悪化する。一方、現在のiLUCAには新しいactive sourceへ安定して追従・移動し続ける能力が十分でないと考えられる。

### 結論

**6 h ON / 6 h OFFという時間変動は、現在の祖先には強すぎる。**

---

## 3.3 A2 — vent位置turnoverは強いが持続可能な進化圧

A2では48 hごとに4 ventsのうち1 ventをrelocateした。

3/3 seedが10日生存したが、最終個体数は37 / 328 / 670とA0より大幅に低かった。

一方、最大世代は6 / 8 / 9であり、A0の5より深くなった。

これはA2が快適な環境という意味ではない。むしろvent移動に伴って多数の個体・lineageが失われる一方、新しいH2供給位置を利用できた一部lineageが局所的に繁殖し、世代を深くしたと解釈するのが自然である。

つまりA2では、

```text
vent移動
→ 旧source周辺のpopulation contraction
→ 新sourceを利用できたlineageの再増殖
```

という局所絶滅・再増殖に近い挙動が生じている可能性が高い。

### 結論

**A2は集団を完全には壊さず、かつA0との差が十分大きい。現時点で最も扱いやすいdynamic working environment候補である。**

---

## 3.4 A3 — Phase Aでは基準を満たしたが生存限界付近

A3はtemporal + turnoverを同時に適用した最も厳しい条件である。

結果は:

```text
seed 18001: final N = 5, max generation = 6
seed 18002: extinction, max generation = 0
seed 18003: final N = 26, max generation = 9
```

事前登録したPhase B選択基準:

```text
>= 2/3 seeds survive 10 d
AND
median max_generation >= 3
```

をA3が満たしたため、事前登録ルールどおりPhase B dynamic armにはA3を採用した。

ただし最終個体数は極めて小さく、すでにPhase Aの時点で**生存限界にかなり近い条件**であることが示されていた。

---

# 4. Phase B Attempt 1 — 20日 / 2×2進化実験

Phase Bは以下の4 arms × 5 seeds × 20日として事前登録した。

```text
B0 STATIC-FIXED
B1 STATIC-EVOLVE
B2 DYNAMIC(A3)-FIXED
B3 DYNAMIC(A3)-EVOLVE
```

しかし、GitHub-hosted runnerの実運用上限に到達し、static側の複数runが約6 hでcancelされたため、Phase Bはformal comparisonとして完了していない。

aggregateに完全な`summary.json`として取り込めたのは11 / 20 runsである。

---

## 4.1 Dynamic側: B2 / B3は5/5すべて完走したが、全seed絶滅

### B2 DYNAMIC-FIXED

```text
5/5 extinction
median max generation = 1
population final = 0 (all seeds)
```

### B3 DYNAMIC-EVOLVE

```text
5/5 extinction
median max generation = 1
population final = 0 (all seeds)
```

B3 seed 18101の例では:

```text
extinction time = 31.4 h
births = 100
starvation deaths = 100
max generation = 0
vent turnover count = 0
```

つまり進化可能にしても、**最初の本格的な世代交代・選択が進む前に餓死している**。

B3では全5 seedでturnover countが0であり、48 hの最初のvent relocationより前に全滅した。B2でも5 seed中4 seedはturnover前に全滅し、1 seedだけが1回目のturnoverまで到達した。

### 解釈

Phase AではA3が2/3 seedで10日生存したが、Phase Bの別seed集合 (`18101-18105`) ではfixed/evolveとも5/5絶滅した。

したがってA3は、

> **平均的に持続可能なdynamic環境ではなく、初期位置・確率揺らぎに強く依存する生存限界環境**

と判断するのが妥当である。

またB3がB2を救えなかったことを「3形質には適応効果がない」と解釈してはいけない。今回のA3では絶滅が速すぎ、進化が作用するための世代数・変異蓄積時間そのものがほぼ与えられていない。

### Phase B dynamic結論

**A3は長期進化実験のworking environmentとしては強すぎる。**

---

## 4.2 Static側: 生態は安定するが計算量が増大

B0 STATIC-FIXEDで唯一20日完走したseed 18104は:

```text
final population = 3256
max generation = 6
starvation-active final = 0
stop = duration_complete
```

であり、static finite-flux環境そのものは長期でも安定している。

一方、B0/B1の多くは個体群が大きいまま計算を続けるためwall-clock計算時間が増大し、GitHub Actions上で約6 h経過した時点でcancelされた。

B1_STATIC_EVOLVE seed 18103では、実行開始が02:20 UTC、cancelが08:20 UTCであり、約6 h連続実行後に`The operation was canceled`となった。

workflowには`timeout-minutes: 480`を指定していたが、実際にはGitHub-hosted runner側の制約により完走できなかった。

cancelされたrunについてもpartial artifact（主にsnapshots等）は保存されているため、Attempt 1の途中経過として保持する。

### 解釈

今回の計算時間増大はdynamic vent実装自体だけが原因ではない。

A3では個体数が急減・絶滅するため、20日指定でもwall-clock上は早く終了した。一方staticでは数千個体が長期間存在し続けるため、**個体数依存の計算量増加が長期runの主要ボトルネックとして顕在化した**。

今後、より長い進化期間・複数代謝・追加環境変数・多数seedを扱う場合、この問題は再発する可能性が高い。

---

# 5. 観測指標の単位バグ

Exp18のdiagnostic `H2_HABITABILITY_MOLM3` に単位換算ミスがある。

現在:

```python
H2_HABITABILITY_MOLM3 = 248e-6
```

しかし:

```text
248 µM = 0.248 mmol/L
1 mmol/L = 1 mol/m^3
therefore 248 µM = 0.248 mol/m^3
```

であり、正しくは:

```python
H2_HABITABILITY_MOLM3 = 0.248
```

現在値は1000倍低い。

このバグが影響するのは:

- `h2_habitability_fraction`
- `h2_habitable_occupancy_fraction`

などのdiagnostic readoutである。

H2 diffusion/source、H2 uptake、Energy physiology、死亡、生殖、vent scheduleには使用されていないため、**Phase A/Bの生存・個体数・世代数などの主要結論を無効にはしない。**

ただしこの2指標はAttempt 1では科学的解釈に使用せず、次回run前に修正する。

---

# 6. Exp18 Attempt 1 総合考察

Exp18 Attempt 1から、以下はかなり強く言える。

### 6.1 finite-flux sourceは成立

V1.10.1で導入したfinite-flux H2 sourceは数値・ledger・dt収束性の面で成立した。

### 6.2 H2総供給量だけでは生態は決まらない

A0とA1では世界全体のH2供給fluxを同じにしたにもかかわらず、A0は安定増殖、A1は3/3絶滅した。

したがって**供給の時間・空間構造そのものが強い生態・進化圧になる。**

### 6.3 temporal fluctuationは現在のiLUCAに特に強い

6 h ON / 6 h OFFは、位置turnoverよりはるかに強い影響を与えた。

現在の祖先は長時間のsource interruptionへ追従・耐久する能力が不足している。

### 6.4 A2は有望、A3は強すぎる

A2は全seedで生存しながらpopulation contractionと深い世代交代を生じたため、今後の進化圧として扱いやすい。

A3はPhase Aの事前基準をぎりぎり満たしたが、別seedで5/5絶滅したため、長期進化実験用のworking conditionとしては不安定すぎる。

### 6.5 今回は3形質の進化効果を評価できていない

B3-EVOLVEも全滅したが、1世代前後で絶滅しているため、

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

がdynamic環境でどう進化するかについて、今回のAttempt 1から結論は出せない。

### 6.6 長期計算基盤が新たなボトルネックになった

static側の20日runがwall-clock 6 hを超え、formal 2×2比較を完遂できなかった。

今後の長期進化実験に向けては、GitHub Actionsを本番長期計算環境として使い続けるのではなく、checkpoint/resumeを含む長期実行基盤を別途整備する必要性が明確になった。

---

# 7. Exp18の現在の判定

```text
V1.10.1 vent mechanism validation : PASS
Phase A fixed-iLUCA comparison     : COMPLETE
Phase B evolution comparison       : INCOMPLETE
Exp18 overall                      : PARTIAL COMPLETE / PAUSED
```

Exp18 Attempt 1は破棄しない。

正式な結果として:

1. Phase 0/Phase A全結果
2. Phase B dynamic 10 complete runs
3. B0 static 1 complete run
4. static側cancel / partial artifacts
5. GitHub Actions計算時間制約
6. habitability diagnostic単位バグ

をすべて保存する。

---

# 8. 今後の扱い

新しい長期計算環境を用意するまでは、6 h以内で完了可能な実験・検証を優先する。

Exp18を再開する場合は、Attempt 1の結果を見なかったことにしてA3をそのまま再実行するのではなく、**human decisionによるAttempt 2**として明示的に設計変更する。

候補としてはPhase Aで最も扱いやすかったA2をdynamic working conditionとし、run duration / seed数を現在の計算環境で完走可能な範囲へ再設計することが合理的である。

ただしAttempt 2の具体条件は本書では確定しない。別途事前登録してから実行する。

---

## 最終要約

> **V1.10.1の有限・動的H2 source機構は成立した。H2総供給量が同じでも時間・空間変動だけで非常に強い選択圧が生じることを確認した。位置turnover単独（A2）は強いが持続可能で、temporal+turnover（A3）は現在のiLUCAには不安定すぎる。Phase BではA3環境でfixed/evolveとも5/5絶滅し、進化効果を評価する前に集団が消失した。一方static側は個体数増加によりwall-clock計算時間が爆発し、GitHub Actionsの実行上限で多数runが未完となった。したがってExp18 Attempt 1は部分完了として保存し、長期計算基盤を整備しつつ、当面は6 h以内で完了できる追加検証へ移行する。**
