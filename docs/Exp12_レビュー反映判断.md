# Exp12 Opus 5レビュー反映判断

更新: 2026-09-02
状態: **人間方針に基づく反映判断確定**

対象:
- 初版: `docs/Exp12_実験計画案.md`
- Opus 5レビュー: `claude/review-v1-7-exp11-kflr82` branch の `docs/Exp11_Exp12_レビュー.md`
- Exp11正式結果: `docs/Exp11_結果考察.md`
- Exp11解釈: `docs/Exp11_考察.md`

本書はレビュー原文より優先する。実装者はレビュー原文を独自解釈して実験条件を変更せず、最終条件は `docs/Exp12_実験計画確定.md` に従う。

---

## 1. 総合判断

Opus 5の結論「初版Exp12をそのまま実行しない」は採用する。

特に次の指摘は科学的に重要であり、Exp12の設計を変更する。

1. 単純な後半傾きだけでは、**平衡へ減速収束中の軌跡**と**一定速度で小型化を継続する軌跡**を誤分類しうる
2. tick時間だけでは、`bmr_core` に伴う**世代交代速度低下**と平衡変更を分離できない
3. Exp11 B2はすでにlate driftが小さく、stationarity判定法の**陽性対照**として安価に使える
4. Matter制約との結合を正式に監視しないと、BMR単独効果と生態フィードバックを混同しうる
5. same-seedの最初の10,000 tickがExp11と一致することを、長期runのintegrity gateにすべき
6. 50,000 tickを盲目的に実行する前に、Actions実行時間の安全性を確認すべき

---

# 2. 採用する指摘

## 2.1 軌跡の「減速」を正式に扱う — 採用

初版はlate slopeが負なら遅延方向へ寄せる構造だったが、これは不十分。

例:

```text
0.8 -> 0.6 -> 0.5 -> 0.45 -> 0.43
```

はまだ低下しているが、平衡値へ近づいている可能性が高い。これを単純な「負の傾き」でdelayと判定してはならない。

したがって確定版では:

- 20–30k
- 30–40k
- 40–50k

の3区間で**符号付き正規化傾き**を測る。

さらに指数型漸近fit

```text
b(t) = b_inf + A * exp(-(t-t0)/tau)
```

を**診断**として追加する。

fitだけで科学判定は確定しない。傾き・減速・generation-space trajectoryと合わせて使う。

---

## 2.2 B2陽性対照を追加 — 採用

Exp12主目的はB1だが、判定手法自体のsanity checkとしてB2を追加する。

ただし全7値×8 seedは不要と判断する。

B2は選定実験ではなくmethod controlなので:

```text
bmr_core = 0.000, 0.100, 0.300
seed     = 1..5
```

の15 runとする。

これにより低・中・上端を覆いつつ、Exp11と完全なsame-seed比較ができる。

---

## 2.3 `bmr_core=0.030` を外し `0.200` を入れる — 採用

Exp11 B1では0.000と0.030の10k時点body_sizeが近く、長期shape確認の情報効率が低い。

確定版B1は:

```text
0.000, 0.050, 0.075, 0.100, 0.150, 0.200, 0.300
```

とする。

0.200を戻すことで高値域のshapeを0.15→0.20→0.30で確認できる。

---

## 2.4 generation中央値/Q90/maxを正式測定 — 強く採用

`max_generation` 単独では少数の最速系統に引っ張られるため不十分。

各snapshotで:

- generation median
- generation Q90
- max_generation

を保存・集計する。

さらにbody_size trajectoryを:

1. tick軸
2. median generation軸

の両方で解析する。

Exp11生データの予備確認でも、例としてB1 seed1 `bmr_core=0` は10k時点でgeneration中央値≈36である一方、高 `bmr_core` の一例では10台まで低下していた。したがって世代交代遅延は無視できず、Exp12では主解析へ格上げする。

---

## 2.5 Matter coupling診断 — 採用

late windowでbody_sizeとMatter状態の変化が強く同期する場合を `MATTER_COUPLED` として明示する。

単純な水準同士の相関は共通トレンドで偽相関になりやすいため、snapshot間の**差分**を使う。

30–50kについて:

```text
Δbody_size vs Δfree_nutrient_fraction
Δbody_size vs Δbiomass_fraction
Δbody_size vs Δpopulation
```

のSpearman相関をseedごとに測る。

これはrunを無効化するintegrity failureではないが、強い結合が多数seedで再現した場合は「BMRの直接サイズ選択だけで説明した」とは結論しない。

---

## 2.6 first-10k same-seed再現性 — 強く採用

Exp12はExp11と同じ初期条件・科学コードで、終了tickだけを延長する。

したがって同じ環境・bmr_core・seedの最初の10,000 tickはExp11と一致しなければならない。

正式runでは全runについて:

- `stats.csv` のtick<=10,000の科学列
- snapshot 1k–10k

をcanonical化してExp11 artifactと比較する。

不一致は `INTEGRITY_FAIL`。科学判定を行わない。

---

## 2.7 50k実行時間のpreflight — 採用

50,000 tickは初版どおり本実験長とするが、正式matrix dispatch前にruntime gateを置く。

既存Exp11 Actions実績と、必要なら代表条件の短いruntime pilotから50kのwall timeを見積もる。

```text
job timeout = 350 min
正式dispatch許可目安 = 予測 worst-case <= 300 min
```

300分超が予測される場合、科学条件をその場で短縮せず `RUNTIME_PREFLIGHT_FAIL / REVIEW` として停止する。

実験結果を見てrun長を後付け変更しない。

---

# 3. 部分採用・変更して採用

## 3.1 指数fitの `tau` をrun長決定に直接使う — 部分採用

Opus 5は既存10kデータからtauを推定してrun長を決める案を提示した。

ただしExp11 10kだけでは、高bmr条件でfit window依存性が大きく、`b_inf`/`tau` が不安定になりうる。

よって:

- Exp11からtauを推定すること自体は実施
- 50kが明らかに不足しそうかを見る参考値にする
- **10k fitだけでrun長を可変にしない**

とする。

50k後もtau/fitが不安定なら `WINDOW_INSUFFICIENT` を正式結果として許容する。

---

## 3.2 `p_low=0.21` の扱い — 閾値単独使用を廃止

Exp11の0.21は事前登録判定には必要だったが、Exp12の長期平衡判定では硬すぎる。

Exp12では:

```text
p_021 = fraction(body_size <= 0.21)
p_023 = fraction(body_size <= 0.23)
p_025 = fraction(body_size <= 0.25)
```

を併記する。

下限側平衡の主要sentinelはmedian body_sizeと`p_023`を使い、0.21だけで結論しない。

---

# 4. 採用しない／優先しない指摘

## 4.1 B2を全7水準×8 seedで実施 — 不採用

B2はExp12の主選定対象ではなく判定法の陽性対照であるため、3水準×5 seedで十分と判断する。

主問いへの計算資源はB1 7水準×8 seedへ集中する。

## 4.2 B3長期runをExp12へ追加 — 不採用

Exp12は「Exp11 B1のbody_size shiftが平衡変更か遅延か」を解く実験。

B3まで含めると環境一般化と機構判定が混ざる。必要ならExp12後に別実験とする。

---

# 5. 確定後の重要原則

Exp12は**bmr_core恒久値を選ぶ実験ではない**。

目的は:

```text
bmr_coreによるbody_sizeシフト
= 長期平衡の変更
or
= 世代交代を含む単なる進化速度の遅延
```

を識別すること。

したがって50k後に候補値を見て閾値を変えたり、都合の良い水準を選んだりしない。

判別できなければ `WINDOW_INSUFFICIENT / REVIEW` が正しい正式結果である。

最終の実装・実行条件は `docs/Exp12_実験計画確定.md` を正本とする。
