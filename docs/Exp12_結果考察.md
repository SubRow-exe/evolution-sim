# Exp12 結果・考察

更新: 2026-09-03
状態: **正式71 run完了 / 技術的Green / V1.7判断確定**

正式Actions run:
- Exp12 run `33592901348`
- head SHA `44a920cbf845ce22a2fb0c755ab655fbc954fd95`
- workflow conclusion: `success`
- 2026-09-02 13:59 JST開始 / 21:58 JST終了（約7時間59分）

正本:
- `docs/Exp12_実験計画確定.md`
- `docs/数値再現性・Actions実行環境方針.md`
- `docs/Exp11_考察.md`
- 本書

---

## 1. 技術的完全性

Exp12はPhase 0、正式71 run、collectまで正常終了した。

- Phase 0: PASS
- formal matrix: 71/71 run完了
- artifact欠落・重複なし
- Config整合性: PASS
- formal SHA整合性: PASS
- numeric environment整合性: PASS
- aggregation errorなし
- 長期解析・保存処理まで完了

したがってExp12データは技術的には有効である。

---

## 2. B1の結果

B1 = **光のみの環境 / light specialist / body_sizeのみ進化ON**。

50k後半のbody_size代表値と8 seed分類:

| bmr_core | 後半body_size中央値 | 主分類 |
|---:|---:|---|
| 0.000 | 0.2088 | LOWER_BOUND_EQUILIBRIUM 8/8 |
| 0.050 | 0.2138 | LOWER_BOUND_EQUILIBRIUM 8/8 |
| 0.075 | 0.2176 | LOWER_BOUND_EQUILIBRIUM 8/8 |
| 0.100 | 0.2238 | LOWER_BOUND_EQUILIBRIUM 8/8 |
| 0.150 | 0.2459 | INTERIOR_EQUILIBRIUM 8/8 |
| 0.200 | 0.3021 | INTERIOR_EQUILIBRIUM 7/8 + CONVERGING_NOT_PROVEN 1 |
| 0.300 | 0.4142 | INTERIOR_EQUILIBRIUM 6/8 + CONVERGING_NOT_PROVEN 2 |

B1では `DELAY_CONTINUES` は0 run。

tick-spaceだけでなくgeneration-spaceでも、`bmr_core >= 0.15` で「単に世代交代が遅いため大型に見えている」だけでは説明しにくい。

### 科学的解釈

Exp11の10k時点で見えていた大型側シフトは長期にはかなり縮小した。しかし完全には消えず、`bmr_core >= 0.15` ではbody_sizeが下限から離れた内部領域へ収束した。

したがってV1.7 `bmr_core` は:

> **極端な小型化・下限張り付きを抑制し、body_sizeの長期平衡を内部側へ移動させる機能を持つ**

と判断する。

---

## 3. B2 method controlの扱い

B2 = **光なし / chemicalのみ / chemical specialist**。

Exp12事前登録では、Exp11の10k時点でlate driftが小さかったB2を「すでにstationaryな陽性対照」とみなし、平衡判定器がそれを平衡と認識できるかをmethod controlとした。

しかし50kまで延長した結果、B2 `bmr_core=0` は10k時点のbody_size約0.77から、50kでは多くのseedで約0.4〜0.5まで低下した。

代表軌跡:

```text
seed1: 10k 0.727 -> 20k 0.490 -> 30k 0.405 -> 40k 0.378 -> 50k 0.358
seed2: 10k 0.840 -> 20k 0.688 -> 30k 0.589 -> 40k 0.492 -> 50k 0.432
seed5: 10k 0.755 -> 20k 0.563 -> 30k 0.432 -> 40k 0.409 -> 50k 0.405
```

これは「判定器がstationaryを見逃した」というより、**B2を既知のstationary positive controlと置いた前提そのものが成立していなかった**と解釈するのが自然である。

### 正式な表現

事前登録上、B2 gateを満たさなかったという履歴は消さない。

ただしV1.7の人間判断では:

```text
B2 = METHOD CONTROL ASSUMPTION INVALID / NOT A KNOWN STATIONARY CONTROL
```

と扱う。

**B2の科学run自体を「失敗」とは扱わない。**

また、B2を100k等へ延長して最終平衡を証明する追加実験は、V1.7の目的達成には不要と判断する。B2の遅い収束は、小個体群・少ない世代交代、局所chemical資源構造などによる可能性があり、今後の別テーマとして残す。

---

## 4. V1.7の最終判断

V1.7の目的は特定のbody_sizeを人為的に作ることではなく、

> 小型ほど無条件に有利な一方向性を、現実的な基礎維持代謝で崩せるか

を確認することだった。

Exp12 B1では:

```text
0.10 -> 8/8 lower-bound equilibrium
0.15 -> 8/8 interior equilibrium
```

となった。

したがって恒久defaultは:

```text
bmr_core = 0.15
```

を採用する。

理由:
1. 下限張り付きを明瞭に解除した最小側の試験値
2. 8/8 seedで内部平衡
3. 0.20 / 0.30ほど大型化方向を強くしない
4. 実験前から採用原則としていた「目的を達成する最小側」を満たす
5. 特定のbody_size値へ合わせるための事後調整ではない

V1.7では追加長期実験を行わず、この値で閉じる。

---

## 5. Exp11との関係

Exp11の10k値は平衡値ではなかった。

高bmr条件ほど世代交代が遅く、10kでは長期値より大型に見えていたため、Exp11単独で恒久値を決めずExp12へ進んだ判断は妥当だった。

Exp12により:

- `bmr_core` の効果は単なる遅延だけではない
- ただし10kで見えた効果量は過大
- 0.15が「極端小型化を解除する最小側」の候補

まで確認できた。

---

## 6. 実行時間の教訓

Exp12 workflow全体wall-clockは約7時間59分。

事前preflightの約200分は「最重い単一50k job」の概算であり、71 runを `max-parallel=20` で複数wave流すworkflow全体時間とは別物だった。

今後は必ず:

```text
A. 単一run最大時間の予測
B. matrix全体wall-clockの予測
```

を分ける。

またpopulation推移により1 tickの計算量は大きく変わるため、10k実測の単純線形外挿には不確実性を明記する。

---

## 7. V1.8へ持ち越す発見

Exp12のB1/B2比較から、lightとchemicalで収束速度・個体数・body_sizeに大きな差が見えた。

現行モデルでは既に:
- light = 毎tick供給され使われなければ消えるflow
- chemical = vent由来の局所stock、消費で減りsource/lossで更新

という差がある。

一方、個体の直接吸収は両方とも `ability × surface area` を主軸とする対称的な構造であり、さらにlightには昼夜がない。

次のV1.8では、結果を人工的に指定せず:

> **light = 広く・低い瞬間収益・周期的・再生するflow**
>
> **chemical = 局所的・高い瞬間収益・消費でstockが減る・競争されるresource**

という一次Energy源の生態的非対称性を、環境物理と吸収則から表現する。

詳細は `docs/V1.8_一次Energy生態非対称仕様.md` と `docs/Exp13_実験計画確定.md`。
