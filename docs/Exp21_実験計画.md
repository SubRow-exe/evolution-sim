# Exp21 実験計画 — starvation_horizon 直接競争実験

## 1. 背景

Exp20 Attempt 2では、physical modeにおいて既存3形質のfitness関連効果をpaired assayで直接測定した。

その結果、`starvation_horizon` は A0_STATIC では効果が小さい一方、A2_DYNAMIC_VENT では長い値ほど生存に有利な傾向が最も明確に確認された。

ただしExp20 Attempt 2は「別run間の性能差」を測った実験であり、同一集団内で有利な形質が実際に増える、すなわち自然選択による系統頻度変化までは確認していない。

Exp21では、この点を直接検証する。

---

## 2. 目的

**同一世界内で `starvation_horizon` の異なる2系統を競争させ、動的環境において有利な系統の頻度が実際に増加するか確認する。**

主たる問いは以下。

1. A0_STATICでは2系統の頻度は大きく変化しないか。
2. A2_DYNAMIC_VENTでは、長い `starvation_horizon` を持つ系統が増加するか。
3. その変化が複数seedで再現されるか。

これが確認できれば、physical modeで「環境変化 → 形質依存fitness差 → 集団内の系統頻度変化」という自然選択の一連の流れを初めて直接示せる。

---

## 3. 競争させる2系統

### Baseline lineage

- `starvation_horizon = 1800 s`

### Long-horizon lineage

- `starvation_horizon = 2700 s`
- baselineの1.5倍

### 共通条件

- 上記以外の全geneは同一
- initial jitterなし
- continuous mutation OFF
- structural innovation OFF
- phototrophy OFF
- predation OFF
- 初期matter / Energy / damage等の外生的初期状態は同一分布

今回の目的は進化を待つことではなく、既知の2形質値を直接競争させることなので、実験中に新しい変異を入れない。

---

## 4. 初期集団

- 総個体数: 100
- Baseline lineage: 50
- Long-horizon lineage: 50

初期配置そのものは共通の100個体配置を生成し、その後 lineage label を50:50で割り当てる。

### 割当ルール

位置による系統有利を避けるため、lineage割当は専用RNGでランダム化する。

- organism/environment RNGとは分離
- 同seedなら同じ割当を再現
- 50:50を厳密に保証

---

## 5. 環境条件

### A0_STATIC

噴出口位置が変化しない基準環境。

目的:
- `starvation_horizon` の違いだけで一方が恒常的に増えるかを確認
- A2の比較対照

### A2_DYNAMIC_VENT

噴出口が48 physical hoursごとに移動する動的環境。

目的:
- H2供給位置の変化によって一時的なEnergy不足が起こる状況で、long-horizon lineageが選択されるか確認

H2 flux等の環境パラメータはExp20 Attempt 2と同じものを使用し、今回の結果を見て環境強度を調整しない。

---

## 6. 実行時間

**120 physical hours**

A2では以下の2回のvent relocationを経験する。

- 48 h
- 96 h

72hでは1回しか変化を経験しないため、今回は120hとする。

---

## 7. seed数

**8 seeds / environment**

- A0_STATIC: 8 runs
- A2_DYNAMIC_VENT: 8 runs
- 合計: 16 runs

Exp20 Attempt 2ではA2のストレス強度がseed依存だったため、3 seedsではなく8 seedsへ増やす。

seedは事前固定し、結果を見て差し替えない。

---

## 8. 主評価指標

### Primary endpoint

各時点のlong-horizon lineage頻度

`f_long = N_long / (N_long + N_baseline)`

初期値は0.5。

主要評価時点:

- 0 h
- 12 h
- 24 h
- 48 h
- 72 h
- 96 h
- 120 h

主に見るのは120h時点の `f_long` と、その時間推移。

### 期待される選択パターン

理想的には:

- A0_STATIC: `f_long ≈ 0.5`
- A2_DYNAMIC_VENT: `f_long > 0.5`

かつA2で時間とともに増加傾向が見えること。

---

## 9. 副評価指標

lineageごとに以下を記録する。

- population
- births cumulative
- deaths cumulative
- starvation deaths cumulative
- total living matter
- mean matter
- mean stored Energy
- mean starvation state
- lineage extinction time
- fixation time（片系統のみになった場合）

平均matterやEnergyはfitnessそのものではなく、頻度変化の機構説明用として扱う。

---

## 10. 選択係数の扱い

両系統が存在する区間では、lineage比率のlogit変化から相対選択の強さを補助的に評価してよい。

ただし片系統が0になった後はpseudocountで無理に連続値へ変換しない。

- extinction
- fixation

をそのまま生物学的イベントとして記録する。

---

## 11. Gate / 実験前検証

formal run前に以下を必須確認する。

1. physical mode = ON
2. phototrophy = OFF
3. predation = OFF
4. mutation / structural innovation = OFF
5. A0/A2のeffective configが事前登録条件と一致
6. 初期個体数100、lineage 50:50
7. 2系統は `starvation_horizon` 以外のgeneが完全一致
8. lineage割当前の位置・matter・Energy・damage等が同一母集団由来
9. lineage割当RNGがorganism/environment RNGから分離
10. Energy/C/N/P ledger gate PASS

どれか1つでも失敗した場合はformal runを開始しない。

---

## 12. 成功判定

### Strong support

- A0ではlong-horizon頻度が概ね50%付近
- A2では8 seedの多くでlong-horizon頻度が増加
- A2の頻度変化がA0より明確に大きい
- vent relocation後に差が拡大する傾向が確認できる

この場合:

**physical modeにおいて、動的環境が `starvation_horizon` に対する自然選択を生み、集団構成を変化させることを直接確認した**

と判断する。

### Weak / inconclusive

- seedごとに方向が大きくばらつく
- A0/A2差がほぼない
- 120hでも頻度変化が小さい

この場合、すぐrun時間やseed数を増やすのではなく、Exp20 Attempt 2で測ったfitness効果と今回の競争結果の不一致原因を先に診断する。

---

## 13. Exp21でやらないこと

- phototrophyのflux calibration
- storage_capacityの追加調整
- reproduction_horizonの追加探索
- spontaneous evolutionを待つ長期run
- 結果を見てA2環境強度を変更すること

Exp21は `starvation_horizon` の直接競争による自然選択確認だけに限定する。

---

## 14. Exp21後の分岐

### Exp21で自然選択が確認できた場合

physical modeの選択圧検証を完了扱いとし、次にphototrophyのflux calibrationへ戻る。

### 確認できなかった場合

paired assayで得られたfitness差が、同一世界内competitionへ変換されない理由を診断する。

---

## 15. 一文要約

**Exp21は、Exp20 Attempt 2で有利と判明した `starvation_horizon = 2700 s` 系統をbaseline 1800 s系統と50:50で直接競争させ、A2_DYNAMIC_VENTで本当に自然選択による系統頻度変化が起こるかを120h・8 seedsで検証する実験である。**
