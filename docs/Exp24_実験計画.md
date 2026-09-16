# Exp24 実験計画 — de novo Phototrophy recurrent-origin establishment assay

更新: 2026-09-16  
状態: **REVISED DRAFT / SECOND CLAUDE-OPUS REVIEW REQUIRED BEFORE IMPLEMENTATION**  
対象version: **V1.11**

関連:

- `docs/Exp23_結果考察.md`
- `docs/Exp23_実験計画.md`
- `docs/Exp24_レビュー依頼.md`
- Issue #78 Exp23 / Exp24 Opus5 review
- `evosim/genome.py` structural innovation implementation
- `evosim/simulation.py`

> 旧single-origin案は破棄する。Exp24では、複数の独立Phototrophy innovationを自然発生させ、各起源を個別tagして、その定着確率が光量に依存するかを評価する。

**この文書はOpus5レビューを受けた改訂preregistration draftである。再レビュー完了前に実装・formal runを開始しない。**

---

## 1. 背景

Exp23では、Phototrophy OFF 50個体 / ON 50個体を最初から用意したdirect competitionにより、A2_DYNAMIC_VENTでPhototrophyへの正の自然選択を確認した。

一方、Exp23はstanding variationに対する選択であり、

> Phototrophyを持たない集団から能力が新規に生じ、そのrare mutant lineageが消滅するか、定着・拡大するか

という「de novo originからの進化」は未検証である。

現行コードではPhototrophyはcontinuous mutationとは別のstructural innovationとして、OFF親の出生時にOFF→ONとして発生する。

旧Exp24案では最初の1 originだけを残すsingle-origin designを予定していた。しかしIssue #78のOpus5レビューで、1 founderはdriftの影響が大きく、240h / 8 seed / 6-of-8判定では、機構が正しく働いていてもほぼ確実にInconclusiveになると指摘された。

したがってExp24は、**1回の起源を運試しする設計から、多数の独立originの定着率を測る設計へ変更する。**

---

## 2. Exp24の目的

主目的:

> **全個体Phototrophy OFFから開始し、出生時に繰り返し自然発生する独立Phototrophy innovationについて、光量が高いほどそのfounder lineageの長期生存・定着確率が高くなるかを測定する。**

概念:

```text
全個体 Phototrophy OFF
        ↓
出生時 structural innovation が複数回発生
        ↓
各OFF→ON newbornに固有 founder ID を付与
        ↓
各founderの子孫を独立に追跡
        ↓
消滅 / 長期生存 / 拡大を光量間で比較
```

Exp24が測るのは、**innovationが与えられた後のselection / driftを含むestablishment probability**である。

Exp24から、Phototrophyの現実的な起源率そのものを推定してはいけない。

---

## 3. 旧single-origin案の破棄

以下の旧案は採用しない。

- first origin後に `phototrophy_innovation_prob=0` とする
- 1 runにつき1 founderだけを追う
- 8 seed
- +240h時点の1 founder fateを6/8で判定する

理由:

- founder 1個体では遺伝的浮動が支配的
- 240hはvent turnover約5回分で、定着判定として短い
- 同じ計算量でもrecurrent innovationを捨てるため情報効率が悪い
- Issue #78の検出力評価で旧判定は不十分

したがって、**single-origin lockは実装しない。**

---

## 4. structural innovation条件

### 4.1 innovation probability

Exp24では

```text
phototrophy_innovation_prob = 0.01 per birth
```

をformal run全期間で維持する。

現行default `1e-4/birth` の100倍であり、これは計算時間内に十分なorigin数を得るためのexperimental accelerationである。

この変更はPhototrophy個体のfitnessを直接変更しない。

**結論では必ず「起源供給率を100倍へ加速した実験」と明記する。**

### 4.2 loss

```text
phototrophy_loss_prob = 0
```

とする。

Exp24ではOFF→ON origin後の定着だけを測り、ON→OFF lossを混ぜない。

### 4.3 continuous genes

Phototrophy capability起源以外の進化を混ぜないため:

- initial jitter = OFF
- continuous mutation = OFF / 全continuous genes固定
- predation innovation = OFF
- Phototrophy structural innovationのみON
- innovation直後の `light_absorption = phototrophy_seed_absorption = 0.01`

とする。

---

## 5. per-origin founder tagging — MUST IMPLEMENT

recurrent innovationでは、単純な `lineage_id` だけでは独立originを区別できない。

Exp24用に観測可能なorigin tagを追加する。

```text
photo_founder_id: int | None
```

意味:

- Phototrophy OFF個体: `None`
- OFF→ON innovationが起きたnewborn: そのnewborn固有のfounder IDを新規付与
- ON親から生まれたON子孫: 親の `photo_founder_id` を継承
- 異なるOFF→ON innovation: 必ず異なるfounder ID

このtagは**観測・集計専用**であり、行動、生理、fitness、RNG系列へフィードバックしてはいけない。

同一tickで複数のOFF→ON innovationが起きても、それぞれ別founder IDを持たせる。

---

## 6. 環境

Exp23と同じ **A2_DYNAMIC_VENT** のみを使用する。

- dynamic vent relocation: Exp23と同一
- H2 / C / N / P条件: Exp23から変更しない
- physical mode: ON
- light pattern: uniform constant
- day/night cycle: OFF

これによりExp23のstanding-variation selectionと直接接続する。

---

## 7. photon flux条件

| condition | flux [µmol photons m^-2 s^-1] | 役割 |
|---|---:|---|
| F0 | 0.0 | negative control |
| F1 | 0.5 | intermediate / Exp23 bridge |
| F2 | 1.5 | **primary positive treatment** |

### primary comparison

```text
F2 = 1.5  vs  F0 = 0.0
```

とする。

理由: rare founderではdriftが強いため、Exp23で最も強いselectionを示した1.5をprimaryにする。

F1=0.5は、Exp23との連続性とdose-response確認のため残すが、Exp24のprimary success判定をF1だけに依存させない。

---

## 8. seed数とrun数

```text
seeds = 24001–24016  (16 seeds)
3 flux × 16 seeds = 48 runs
```

結果を見てseedの追加・差し替えはしない。

同一seedを3 fluxで使用し、seedをblockとして解析する。

---

## 9. run duration とprimary origin cohort

### 9.1 formal duration

各runを

```text
1920 physical hours
```

実行する。

### 9.2 primary cohort

formal run前半

```text
t_origin <= 960 h
```

に発生した独立originだけを**primary eligible origins**とする。

これにより、primary cohortの全originを必ず

```text
origin後 +960 h
```

まで追跡できる。

960h以降に発生したoriginも記録するが、+960h評価ができないためprimary解析からは除外し、secondary / descriptive扱いとする。

innovation probabilityは1920hを通して0.01のままとし、途中で供給を止めない。

### 9.3 runtime技術要件

48 run × 1920hは計算負荷が大きい。

formal開始前にrepresentative runtime preflightを行う。

- fluxごとは別matrix jobにする
- 1 job内で3 fluxを連続実行しない
- GitHub Actions timeoutに入らない場合は、**科学状態・RNG状態を完全保存するcheckpoint/resume**または等価なsegmented executionを実装する
- runtime都合でphysical duration、seed数、flux、innovation率を自動変更しない

---

## 10. primary endpoint

各eligible founder `j` について、origin時刻を `tau=0` とする。

### primary binary endpoint

```text
survive_960(j) = 1  if N_founder_j(tau=960h) > 0
                 0  otherwise
```

すなわち、**origin後960h時点でそのfounder lineageがまだ存在するか**をprimary establishment endpointとする。

ここでいう「establishment」はExp24内のoperational definitionであり、fixationを意味しない。

### run / seed level primary statistic

各seed・fluxについて

```text
establishment_rate = surviving eligible origins / eligible origins
```

を算出する。

**origin個々を独立replicateとして直接p値計算しない。** 同一run内のoriginは同じ環境履歴を共有するため、primary inferential unitはseed/runとする。

---

## 11. secondary endpoints

各founderについて:

- `N_founder(+240h)`
- `N_founder(+480h)`
- `N_founder(+960h)`
- founder lineage frequency at +240/+480/+960h
- extinction time
- maximum N
- maximum frequency
- total living matter
- births / deaths / starvation deaths
- first time reaching N>=2 / 5 / 10
- first time reaching frequency >=1% / 5%

各fluxについて:

- total innovation count
- eligible origin count
- establishment rate
- extinction-time distribution
- founder-size distribution

を出力する。

---

## 12. primary analysis

### 12.1 primary contrast

同一seedの

```text
ΔE_seed = establishment_rate(F2=1.5) - establishment_rate(F0=0.0)
```

をprimaryとする。

### 12.2 Strong support proposal

以下を全て満たす場合、Exp24 primary hypothesisをStrong Supportとするproposalを再レビュー対象とする。

1. integrity / conservation / tracking gateが全PASS
2. `ΔE_seed > 0` が **16 seed中12 seed以上**
3. median `ΔE_seed > 0`
4. seedをcluster単位としたbootstrap 95% CIでF2−F0のestablishment-rate差の下限が0を上回る
5. F2でfounder apparatusが実際にlight Energyを利用していることをledgerで確認

12/16は「結果を見て設定」した値ではなくformal前に固定する。ただしこの基準自体の妥当性は第二レビューで再確認する。

### 12.3 secondary dose response

F1=0.5を含め、

```text
F0 <= F1 <= F2
```

の方向性をseed-level establishment rate、survival curve、founder sizeで確認する。

F1がF0を明確に上回らなくても、primary F2 vs F0が支持されればExp24自体を自動FAILにはしない。

---

## 13. preflight / Gate

### G0 — initial state

- initial population = 100
- Phototrophy ON = 0
- all initial `light_absorption = 0`
- all initial `photo_founder_id = None`

### G1 — structural innovation only

Phototrophy OFF→ONは出生時 `structural_mutate()` 経路でのみ生じる。

### G2 — founder phenotype

OFF→ON newbornが

```text
phototrophy_on = True
light_absorption = 0.01
photo_founder_id != None
```

を持つ。

### G3 — founder-tag inheritance

ON founderのON子孫が同じ `photo_founder_id` を継承する。

### G4 — independent recurrent origins

異なるOFF→ON eventは異なるfounder IDを持つ。同一tick複数originにも対応する。

### G5 — no single-origin lock

最初のinnovation後も `phototrophy_innovation_prob=0.01` が維持され、新規originが継続して発生可能。

### G6 — loss disabled

`phototrophy_loss_prob=0` でON→OFFが起きない。

### G7 — no continuous bypass

OFF個体がcontinuous mutationだけでPhototrophyを獲得しない。

### G8 — pre-first-origin flux independence

同一seedのF0/F1/F2は最初のPhototrophy origin直前まで個体状態・population・RNG trajectoryが一致する。

**最初のorigin以降は光量により生態が分岐するため、後続origin tickの一致は要求しない。**

### G9 — founder apparatus assembly

OFF親由来のinnovation founderは、Phototrophy装置を局所fixed-Nから正しくassemblyする。

- assembly前はphoto Energy credit = 0
- structural N ledgerが閉じる
- assembly後のみlight利用が始まる

### G10 — physical light identities

- flux=0: incident/absorbed/usable/used photo Energy = 0
- OFF個体: fluxによらずphoto power = 0
- legacy light flow = 0

### G11 — recorder non-interference

`photo_founder_id`追加やfounder別集計がRNG・個体状態・world update順を変えない。

### G12 — conservation / integrity

- Energy ledger PASS
- Matter ledger PASS
- C/N/P ledger PASS
- formal SHA一致
- numeric environment一致
- 48/48 run completeness

### G13 — degenerate demography diagnostic

Exp23 seed23008型の「死亡0・出生完全対称でfrequencyが構造的に動けない」runを自動flagする。

flagged runを恣意的に除外せず、primary seed-level解析に含めた結果とsensitivityを併記する。

### G14 — runtime preflight

formal 1920h runのwall-clockを事前推定し、runner timeoutを超える場合はcheckpoint/resumeを実装してからformalへ進む。

---

## 14. required outputs

### per-origin table

`exp24_origins.csv` proposal:

- seed
- flux
- photo_founder_id
- founder organism ID
- parent ID
- origin tick / hour
- founder position
- founder matter / Energy
- founder genome / light_absorption
- population at origin
- vent phase at origin
- apparatus assembly completion time
- N at +240/+480/+960h
- frequency at +240/+480/+960h
- extinction time
- max N / max frequency
- survive_960
- eligible_primary

### per-run summary

`exp24_per_run.csv` proposal:

- seed / flux
- total origins
- eligible origins
- survived_960 count
- establishment_rate
- population / births / deaths
- photo Energy ledger summary
- C/N/P / Energy integrity
- degenerate-demography flag

### aggregate

- seed-level establishment-rate table
- F2−F0 paired differences
- F1−F0 secondary differences
- flux別survival curve
- origin-count distribution
- founder-size distribution
- completeness / integrity verdict

---

## 15. 解釈できること / できないこと

### 成功時に言えること

> Phototrophy capabilityがstructural innovationとしてPhototrophy非保有集団から新規出現し、子孫へ継承され、その独立founder lineageの長期定着確率が光環境に依存する。

これはExp23のstanding-variation selectionより一段進んだ、**de novo capability origin + inheritance + selection-driven establishment**の証拠となる。

### 言えないこと

- Phototrophyが現実に `0.01/birth` で発生する
- 現実的な時間尺度でPhototrophyが進化する
- 現実の光合成起源機構を再現した
- Phototrophyが集団へ必ず固定する
- mutation-selection balanceを再現した

innovation probabilityをdefaultの100倍へ加速していることを必ず明記する。

---

## 16. Exp24後

### Exp24が支持された場合

V1.11では以下の連鎖が成立する。

```text
Exp22: Phototrophyの生理的benefitを校正
Exp23: standing variationとしてPhototrophyに自然選択が働く
Exp24: de novo structural innovationとして発生した独立系統の定着確率が光で上昇
```

この時点でV1.11 Phototrophy origin/selection trackのcloseを検討する。

### Exp24が支持されなかった場合

すぐにinnovation率・光量・判定閾値を変更しない。

まず以下を診断する。

- founder apparatus assembly delay
- founder数 / eligible origin数
- extinction-time distribution
- turnover回数
- demographic degeneracy
- Exp23で測ったselectionとの差

---

## 17. 実装順序

第二レビューで承認後、Claudeは以下の順で実装する。

1. `photo_founder_id` state / inheritance / recorder追加
2. per-origin tracking tests
3. recurrent-origin config generator
4. apparatus assembly / same-tick multi-origin tests
5. conservation / non-interference tests
6. runtime preflight
7. formal 48 runs
8. completeness / integrity gate
9. aggregate
10. 結果考察

**レビュー完了前に1–10へ着手しない。**
