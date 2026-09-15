# Exp24 実験計画 — de novo Phototrophy single-origin invasion assay

更新: 2026-09-16  
状態: **DRAFT / CLAUDE-OPUS REVIEW REQUIRED BEFORE IMPLEMENTATION**  
対象version: **V1.11**

関連:

- `docs/Exp23_結果考察.md`
- `docs/Exp23_実験計画.md`
- `docs/Exp22_結果考察.md`
- `docs/Exp22_Opus5レビュー.md`
- `evosim/genome.py` structural innovation implementation

**この文書はレビュー前のpreregistration draftである。レビュー完了前にformal runを開始しない。**

---

## 1. 背景

Exp23では、最初からPhototrophy ONの個体50、OFFの個体50を用意したdirect competitionにより、A2_DYNAMIC_VENTで十分な光があるとPhototrophy系統が自然選択で増えることを確認した。

しかしこれはstanding variationに対する選択であり、

> Phototrophyを持たない集団から能力が新規に生じ、そのrare mutant lineageが生き残り・増える

という「能力の起源」までは検証していない。

現行コードではPhototrophyはcontinuous mutationとは別のstructural innovationとして実装されている。

- 初期iLUCA: Phototrophy capability OFF
- OFF親からの出生時に `phototrophy_innovation_prob` でOFF→ON
- innovation直後の子は `light_absorption >= phototrophy_seed_absorption`
- ON能力は子孫へ継承される
- 現在のdefault innovation probability: `1e-4 / birth`
- default loss probability: `1e-3 / birth`

Exp24では、この実装経路を使ってPhototrophyを**実際の出生時innovationとして発生させる**。

---

## 2. Exp24の目的

Exp24の主目的は、

> **全個体Phototrophy OFFから開始し、出生時に自然発生した最初のPhototrophy innovation 1系統が、光環境に応じて生存・増殖できるかを直接比較すること**

である。

見る流れは以下。

```text
全個体 OFF
  ↓
出生時 structural innovation
  ↓
Phototrophy ON newborn が1個体出現
  ↓
能力を子孫へ継承
  ↓
光なし / 中程度の光 / 強い光で系統の運命を比較
```

Exp23の50:50競争より一段自然な、**rare de novo originからのinvasion test**と位置付ける。

ただしExp24は「structural innovationの現実的な発生率」を推定する実験ではない。計算時間内に起源イベントを確実に観測するため、innovation probabilityを実験上加速する。

---

## 3. default innovation率をそのまま使わない理由

現行default:

```text
phototrophy_innovation_prob = 1e-4 per birth
```

Exp23のflux=0条件では、120hあたり総出生数は中央値約241 births/runだった。

したがって120hでの期待innovation数はおよそ

```text
241 × 1e-4 = 0.0241 events/run
```

であり、1回以上起きる確率は約2.4%にすぎない。

このままでは8 seedを実行しても大半のrunでPhototrophyが一度も出現せず、計算予算内で「出現後の選択」を評価できない。

よってExp24では、**起源の待ち時間だけを圧縮するexperimental acceleration**として

```text
phototrophy_innovation_prob = 0.01 per birth
```

を候補とする。

これはdefaultの100倍だが、Phototrophyのfitnessを直接変更する値ではない。

重要:

> Exp24から「Phototrophyが現実に1%/birthで生じる」と解釈してはいけない。

Exp24で評価するのは**innovationが1回起きた後のrare lineageの運命**である。

`0.01`の妥当性はClaude/Opusレビューで必ず再確認する。

---

## 4. single-origin design

recurrent innovationが何度も起きると、Phototrophy個体が増えた理由を

- 最初のmutant lineageが自然選択で増えた
- 新しいinnovationが繰り返し供給された

に分離できなくなる。

そのためExp24では**single-origin design**を採用する。

### waiting phase

- 初期100個体は全てPhototrophy OFF
- `phototrophy_innovation_prob = 0.01`
- 最初のOFF→ON innovationを待つ
- waiting上限: **240 physical hours**

### first origin発生時

最初のinnovationを検知したtickで以下を記録する。

- origin time
- founder organism ID
- parent ID
- founder position
- founder matter
- founder Energy
- founder genome
- population size
- vent turnover phase

そしてそのrunでは直ちに

```text
phototrophy_innovation_prob = 0
```

へ切り替え、**追加の独立originを禁止する**。

### follow-up phase

最初のorigin発生から **240 physical hours** 追跡する。

したがって1 runの総時間は可変で、最大480h。

この方式なら、以後存在するPhototrophy ON個体は原則として最初のfounderの子孫だけとなる。

---

## 5. Phototrophy loss

Exp24ではfirst originの選択・定着を単純化するため、proposalとして

```text
phototrophy_loss_prob = 0
```

とする。

理由:

- Exp24の新規問いは「OFF→ON originがrare stateから成立するか」
- ON→OFF lossを同時に入れると起源と喪失の2過程が混ざる
- recurrent innovationもfirst origin後にOFFにするため、対称性よりも解釈可能性を優先する

lossをdefault `1e-3/birth` のまま残すべきかはレビュー項目とする。

---

## 6. continuous gene mutation

Exp24ではPhototrophy capabilityの起源だけを検証する。

したがってExp23と同様、continuous genesは全て固定する。

- initial jitter OFF
- continuous mutationによるgene drift OFF
- predation innovation OFF
- Phototrophy structural innovationのみON

innovationでPhototrophyが獲得された瞬間、現行実装どおり

```text
light_absorption >= phototrophy_seed_absorption = 0.01
```

が与えられる。

以後、その値は固定したまま子孫へ継承する。

これによりExp24は「能力の起源 + その能力への自然選択」に限定される。

---

## 7. 環境

Exp23と同じ **A2_DYNAMIC_VENT** のみを使う。

理由:

- Exp23でPhototrophyへの自然選択を確認済み
- vent relocationによるH2供給変動がある
- standing variation実験との直接比較が可能

H2 source calibration、C/N/P倍率、vent turnover設定等はExp23から変更しない。

---

## 8. photon flux条件

Exp23と同じ3条件を使う。

| condition | photon flux [µmol photons m^-2 s^-1] | 役割 |
|---|---:|---|
| F0 | 0.0 | negative control: 装置コストのみ |
| F1 | 0.5 | primary working flux |
| F2 | 1.5 | positive control |

light patternはuniform constant、day/night cycleはOFFのままとする。

---

## 9. paired originの重要性

最初のPhototrophy originが出る前は全個体がOFFなので、photon fluxは生理へ影響しない。

したがって同一seedのF0/F1/F2は、first originが起きるまでは

- population
- positions
- births/deaths
- RNG trajectory

が完全一致するはずである。

この性質を利用し、**同じseedの3 fluxで同じfirst originを発生させ、その同一rare mutantの運命だけを光量で比較する**。

formal pair成立条件:

- first origin tick一致
- founder ID一致
- parent ID一致
- founder initial state一致

これが崩れたseedは結果を解釈せず、mechanical failureとして扱う。結果を見てseedを差し替えない。

---

## 10. seed数

proposal:

```text
8 seeds: 24001–24008
```

3 flux × 8 seeds = **24 runs**。

Exp21/Exp23と同規模のseed数を維持し、paired designでseed差を抑える。

seed数はformal run前に固定し、結果を見た後に追加しない。

---

## 11. primary endpoint

first origin発生を `tau = 0` と定義する。

primaryは **tau=240h時点のfirst-origin Phototrophy lineageの個体数と頻度**。

記録:

```text
N_photo(tau)
f_photo(tau) = N_photo / N_total
```

主要時点:

- tau = 0
- +24h
- +48h
- +96h
- +120h
- +168h
- +192h
- +240h

initial frequencyは1個体 / その時点の総個体数なので、おおむね1%未満～数%となる。

50:50から始めたExp23と違い、Exp24では**rare mutantのinvasion dynamics**を見る。

---

## 12. secondary endpoints

各runで以下を記録する。

### origin event

- first innovation time
- founder ID / parent ID
- population at origin
- vent phase at origin

### founder lineage fate

- lineage extinctionの有無・時間
- N_photo max
- final N_photo
- final f_photo
- Phototrophy lineage births
- Phototrophy lineage deaths
- starvation deaths
- total living matter of photo lineage

### milestones（診断）

- N_photo >= 2 の初回時刻
- N_photo >= 5
- N_photo >= 10
- f_photo >= 1%
- f_photo >= 5%

milestone到達を成功判定そのものにはせず、成長速度の説明に使う。

---

## 13. proposed success criteria

rare originではExp23のように50%から大きく頻度が動くことは期待しない。

したがって、absolute frequency閾値ではなく**同一originのpaired fate difference**を重視する。

### Strong support proposal

primary F1=0.5について:

1. paired-origin gateが成立したseedのうち、少なくとも **6/8 seed** で
   `N_photo(+240h, 0.5) > N_photo(+240h, 0.0)`
2. median `N_photo(+240h)` が F0よりF1で大きい
3. founder-lineage survival at +240h がF0よりF1で高い
4. positive control F2=1.5がF1以上の効果を示す
5. flux増加に伴い、median N_photoまたはmedian f_photoが概ね単調増加する

### Inconclusive

- first origin後240hでもほぼ全条件1個体前後
- seed間方向が大きく不一致
- F2 positive controlでもF0との差がない

この場合は、すぐinnovation率をさらに上げるのではなく、rare-founder時の選択効果と人口動態を診断する。

### Mechanical failure

- 同一seedのflux間でfirst origin tick / founderが一致しない
- first origin後に追加innovationが発生する
- loss=0なのにON→OFFが起きる
- lineage inheritanceが壊れる
- ledger gate不成立

---

## 14. preflight / Gate

formal run前に最低限以下を検証する。

### G0 — initial state

- initial population = 100
- Phototrophy ON = 0
- `light_absorption=0` for all initial organisms

### G1 — structural innovation path

OFF親の出生時innovationでのみPhototrophy ONが生じること。

### G2 — seed phenotype

innovation直後のnewbornが

```text
phototrophy_on = True
light_absorption = 0.01
```

を持つこと。

### G3 — inheritance

loss=0・追加innovation=0条件で、ON founderの子孫がONを継承すること。

### G4 — no continuous bypass

Phototrophy OFF個体がcontinuous mutationだけで `light_absorption > 0` にならないこと。

### G5 — single-origin lock

first innovation検知後にinnovation probabilityが0へ切り替わり、以後innovation event countが増えないこと。

### G6 — pre-origin flux independence

同一seedのF0/F1/F2がfirst origin直前まで完全一致すること。

### G7 — paired first origin

同一seedで first origin tick / founder ID / parent ID / initial founder stateが一致すること。

### G8 — physical light identities

- flux=0ではphoto incident/absorbed/usable/usedが0
- OFF個体ではfluxに依存せずphoto powerが0
- legacy light flow = 0

### G9 — C/N/P + Energy ledger

Exp22/23と同じ保存則gateをPASSすること。

### G10 — completeness

- 8 seeds × 3 flux = 24 formal trajectories
- origin未発生runもsilent skipせず `NO_ORIGIN_WITHIN_WINDOW` として必ずartifactに残す

---

## 15. formal outputs

各run:

- `effective_config.json`
- `origin_event.json`
- `timeseries.csv`
- `summary.json`
- ledger/gate summary

aggregate:

- `exp24_per_run.csv`
- `exp24_origin_pairing.csv`
- `exp24_flux_response.csv`
- `exp24_aggregate.json`

aggregateには最低限以下を含める。

- origin occurrence count / condition
- paired-origin gate results
- N_photo(+240h) distribution
- f_photo(+240h) distribution
- founder survival fraction
- paired F1-F0 / F2-F0 differences
- extinction times
- completeness status

---

## 16. Exp24で言えること / 言えないこと

### Exp24成功時に言えること

> **Phototrophyを持たない集団から、出生時structural innovationとしてPhototrophyが新規出現し、そのrare mutant lineageの運命が光環境によって変わる。十分な光では同一originがより生き残り・増殖しやすい。**

これはExp23のstanding variation selectionから一段進み、**de novo origin + inheritance + selection**を一つのrunでつなぐ結果になる。

### まだ言えないこと

- default `1e-4/birth`という低い起源率のまま自然時間でPhototrophyが進化する頻度
- recurrent innovation/lossを含むmutation-selection balance
- continuous gene evolutionとの共進化
- realistic day/night cycleでの長期適応
- Phototrophyの歴史的起源機構そのもの

特にinnovation probability=0.01は計算時間短縮のためのexperimental accelerationであり、進化速度の物理的推定には使わない。

---

## 17. Exp24後の想定

Exp24でsingle rare originの成立が確認できた場合、次段では初めて

> **recurrent innovation / lossを止めず、全個体OFFから長時間自由進化させる**

実験へ進む。

これはExp25候補とし、Exp24と混ぜない。

---

## 18. Claude / Opusレビュー依頼項目

実装前に以下を重点レビューする。

1. default `1e-4/birth`をExp24で直接使わない判断は妥当か
2. accelerated `0.01/birth` はwaiting-time圧縮として妥当か
3. first origin後にinnovationを0へするsingle-origin designは問いに対して妥当か
4. `phototrophy_loss_prob=0` とするべきか、default `1e-3`を残すべきか
5. waiting上限240h + post-origin 240hは十分か
6. first originがflux間で完全pairingできるという前提はコード上正しいか
7. first-origin後、全ON個体をfounder descendantsとみなしてよいか
8. 8 seedで十分か
9. Strong supportの6/8という基準は妥当か
10. Exp24で追加すべきmechanical gate / lineage trackingはあるか
11. single-origin assayよりrecurrent-innovation assayを先にすべき理由があるか
12. Exp24成功後に「de novo Phototrophy evolution」と呼べる範囲をどう限定すべきか

---

## 19. 一文要約

**Exp24は、全個体Phototrophy OFFから開始し、出生時structural innovationで生じた最初のPhototrophy mutant 1系統だけを追跡し、同一originをflux 0 / 0.5 / 1.5でpaired比較することで、rare de novo originが光依存自然選択によって定着方向へ進めるかを検証する実験である。**
