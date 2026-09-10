# Exp20 結果・考察 — V1.11 Primitive Phototrophy Seeded Invasion

更新: 2026-09-10  
状態: **本番完了 / 結果レビュー済み / 次段階方針確定**

正本実験計画: `docs/Exp20_V1.11_PrimitivePhototrophy_SeededInvasion_実験計画.md`  
V1.11仕様正本: `docs/V1.11_原始Phototrophy_実装仕様_rev2.md`

---

## 1. 用語

- **phototroph**: V1.11で追加したprimitive phototrophy能力を持つ個体。光から得たEnergyをmaintenance/activity補助に利用できる。
- **ancestor**: phototrophy能力を持たない祖先型個体。
- **A0_STATIC**: 4 ventが常時ONの一定H2供給環境。各vent fluxはF0。
- **A1_TEMPORAL**: 4 ventを2組に分け、6 hごとにactive pairを交代する時間変動H2環境。瞬間総H2供給量と積算総H2供給量はA0と同じ。
- **s48_per_day**: 0–48 hでのphototroph/ancestorの相対log-ratio変化を1日あたりに換算した指標。正ならphototrophがancestorに対して相対的に有利。
- **Delta_s48**: `s48_A1 - s48_A0`。正なら、phototrophyの相対fitnessがSTATICよりTEMPORAL環境で高いことを示す。

---

## 2. 実験成立性

formal designどおり:

```text
Environment: A0_STATIC / A1_TEMPORAL
Initial photo frequency: 0 / 1 / 10 / 50%
Seeds: 20001 / 20002 / 20003
Duration: 120 h
Total: 24 runs
```

結果:

- 24/24 run完走
- aggregate artifact生成成功
- C/N/P ledger valid
- phototrophy Energy identity valid
- `photo_used <= photo_usable_max <= photo_absorbed <= photo_incident` を満足

したがって、以下の生態的結果は少なくとも保存則破綻やrun欠損による見かけの結果ではない。

---

## 3. A0_STATIC — 一定環境での結果

48 h時点:

| 初期phototroph頻度 | P0 | A0 | P48 | A48 | s48/day |
|---|---:|---:|---:|---:|---:|
| 1% | 1 | 99 | 16 | 99 | 1.199 |
| 10% | 10 | 90 | 160 | 90 | 1.363 |
| 50% | 50 | 50 | 800 | 50 | 1.382 |

3 seedすべてで同じ結果となった。

### 解釈

A0ではancestor数が48 hまでほぼ変化しない一方、phototrophは全頻度で16倍になった。これは48 hで4回のnet doublingに相当する。

したがって現在のparameter setでは、phototrophyはH2 interruption時だけの耐久能力ではなく、**H2が安定している通常環境でも大きな一般的fitness advantageを与えている**。

V1.11 rev2ではlightは直接biomassを作るEnergy源ではなくmaintenance/activity補助である。そのためA0での増殖差は、photo maintenance creditによってH2由来Energyのmaintenance消費が減り、その分が成長・繁殖側へ残ることで生じている可能性が高い。

これは機構上あり得る挙動であり直ちにbugとはしない。ただし、進化モデルとしてはphototrophyが「環境依存の選択肢」ではなく「持てば常に得な必勝形質」になる危険を示す。

事前登録したInterpretation Patternでは、これは **Pattern 2 — A0でもstrong positive sweep** に相当する。

---

## 4. A1_TEMPORAL — 時間変動環境での結果

### 4.1 ancestor-only control

初期phototroph 0%では、ancestor 100個体は約43–46 hで全滅した。

これはExp18と整合し、A1が局所H2 source interruptionに対する厳しい環境として再現されていることを示す。

### 4.2 phototroph seeded arm

phototrophを1 / 10 / 50%でseedした9 runは、すべて120 hまで集団が存続した。

48 h時点のphototroph数:

- 1%: 1 -> 1–3
- 10%: 10 -> 7–10
- 50%: 50 -> 39–55

120 h時点では:

- 1%: phototroph 1–12
- 10%: phototroph 26–48
- 50%: phototroph 124–156
- ancestor: 最終的に全条件で0

### 解釈

A1ではphototroph自身が最初から急増したわけではない。48 hまでは横ばい〜減少したrunも多い。

一方ancestorは急速に減少し、ほぼ全滅する。このためA1におけるphototrophyの主要な効果は、

> **増殖ブーストというより、H2供給が局所的に途切れる期間を耐えるための絶滅回避・生存延長効果**

と解釈するのが妥当である。

その後120 hまで存続したphototroph lineageは再増殖しているため、

```text
H2 interruption
-> ancestorは耐えられず消失
-> phototrophは低個体数でも生存
-> 条件が許す局面で再増殖
```

というecological rescueが成立したと考えられる。

したがってV1.11 phototrophy機構は、想定していた「H2 interruption耐性」を実際の集団存続まで反映できている。

---

## 5. 48 h相対fitness結果

phototroph founderありの正式な比較対象である1 / 10 / 50%について、A1とA0を同一seedでpaired comparisonした結果:

| 初期phototroph頻度 | median Delta_s48 [/day] | 3 seedの方向 |
|---|---:|---|
| 1% | +0.730 | 3/3 positive |
| 10% | +1.068 | 3/3 positive |
| 50% | +0.803 | 3/3 positive |

全9 paired comparisonsで `Delta_s48 > 0`。

したがって、

> **phototrophyのancestorに対する相対的優位性は、H2が一定なA0より、H2 sourceが時間的に途切れるA1で一貫して高い**

というExp20の主質問には肯定的に答えられる。

ただしこれは「A1でphototroph自身の絶対増殖速度が高い」という意味ではない。実際にはA1でphototrophも苦しんでおり、ancestorがさらに大きく減少するため相対fitnessが高くなっている。

---

## 6. 重要な解析上の修正 — 0%群でs48を解釈しない

current aggregateでは0% phototroph群についてもR48 / s48 / Delta_s48が機械計算される。

A1 0%群では:

```text
P0 = 0
P48 = 0
A0 = 100
A48 = 0
```

であるにもかかわらず、pseudocount 0.5のため `s48 = +2.652/day` が算出される。

これはphototrophが存在しないため、**phototrophのfitnessを意味しない数学的artifact**である。

事前登録のPrimary endpoint自体も「phototroph founderありarm（1/10/50%）」を対象としているため、今後の正式解析では:

- 0%群はR48 / s48 / Delta_s48の解釈対象から除外する
- 0%群はecological rescue評価用のancestor-only controlとして扱う
- aggregate側でも可能なら0%をprimary estimand集計から除外、またはNA表示に修正する

とする。

Exp20 formal run自体をやり直す必要はない。

---

## 7. Exp20の最終判断

### 7.1 V1.11 phototrophy機構の成立性

**合格。**

理由:

1. photon -> usable Energy -> maintenance creditのledgerが成立
2. C/N/P保存則も成立
3. A1 ancestor-onlyでは従来どおり絶滅
4. phototrophを少数seedすると全9 runで120 h survivalを達成
5. 全9 paired comparisonsでTEMPORAL環境における相対fitness上昇を確認

したがってphototrophy実装を撤回・再設計する必要はない。

### 7.2 現parameter setの生態的バランス

**未確定 / 調整必要。**

A0でもphototrophが48 hで16倍となり、強いgeneral advantageが存在する。

このまま自然innovationを有効化すると、phototrophyが一度出現した後に環境条件とほぼ無関係にsweepする可能性がある。

本シミュレーションで狙うべき状態は:

```text
安定H2環境:
ancestor ~= phototroph
または
ancestor > phototroph

H2 interruption環境:
phototroph >> ancestor
```

すなわち、phototrophyを常時有利な「必勝形質」ではなく、**環境によって価値が変化する進化戦略**にすることである。

---

## 8. 次段階の方針

次はExp21として、phototrophyの利益―コストbalanceを診断・調整する。

### Step 1 — A0 strong advantageのmechanism decomposition

いきなりparameterを弱体化する前に、A0で16倍になる原因を定量化する。

最低限、photo / ancestor別に:

```text
maintenance expenditure
photo maintenance offset
H2 biological uptake per capita
H2-derived usable Energy
stored Energy
births
matter / biomass trajectory
photo_structural_n cost
```

を比較する。

特に:

```text
photo maintenance offset / baseline maintenance
```

がどの程度かを確認し、phototrophyによって節約されたEnergyが繁殖差をほぼ説明できるかを検証する。

### Step 2 — benefit / cost sensitivity

mechanism確認後、以下のparameterを候補としてsensitivity sweepする。

- `phototrophy_radiant_to_usable_eff` : 光Energy変換効率
- photon flux : 環境側の光供給量
- phototrophy structural N cost : 光合成装置維持の構造コスト

ただし複数parameterを同時に無秩序に変更せず、どの項がfitness balanceを支配しているかを切り分ける。

### Step 3 — calibration target

目標は単にA0のphototroph増殖を止めることではなく、

1. A0では強い一方向sweepを起こさない
2. A1ではancestor-onlyが不利
3. phototrophはA1で絶滅回避能力を維持
4. A1-A0の環境依存差が残る

というtrade-off領域を探すこと。

### Step 4 — Exp21の評価指標

Exp21では相対指標だけに依存せず、以下を並列に評価する。

- phototroph absolute population trajectory
- ancestor absolute population trajectory
- lineage-specific births / deaths
- extinction time
- survival at endpoint
- final population
- population AUC
- s48（founderありarmのみ）
- Delta_s48（founderありarmのみ）

これにより「phototrophが増えた」のか「ancestorが減ったため相対的に有利に見えた」のかを分離する。

---

## 9. 結論

Exp20から得られた最終結論は以下。

> **V1.11 primitive phototrophy機構は物理・保存則上成立し、H2 source interruption環境でancestorの絶滅を回避する実効的な生存利益を与えた。phototrophの相対fitnessはSTATICよりTEMPORAL環境で全paired comparison一貫して高かった。一方、現行parameterではSTATIC環境でもphototrophが強く増殖し、general advantageになっている。そのためV1.11機構自体は採用し、次段階ではA0での強い利益の内訳を診断した上で、光Energy利益と構造コストのbalanceを調整し、環境依存trade-offを形成する。**

Exp20 formal runの再実行は不要。次はExp21へ進む。
