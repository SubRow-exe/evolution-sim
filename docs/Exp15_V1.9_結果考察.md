# Exp15 V1.9 結果・考察

更新: 2026-09-04
状態: **PHASE A COMPLETE / GATE FAIL / PHASE B NOT DISPATCHED**

対象commit: `4dd5d769b84527dbfa76c4b800a0fd7fdd41507a`
GitHub Actions run: `33859051915` (`Exp15 V1.9 Formal`)

---

## 1. 結論

Exp15 formal Phase A は5 seedすべて正常実行されたが、**全seedで約2.2–2.3分以内に100/100個体がstarvation死し、max_generation=0** となった。

事前登録gate:

```text
>= 3/5 seeds reach max_generation >= 5
```

に対し:

```text
0/5 seeds reach max_generation >= 5
```

なので **GATE FAIL**。

workflowは設計どおりPhase Bを自動SKIPした。parameter tuning、Phase B強行、Phase C実行は行っていない。

このFAILは、Phase0で確認したH2 Energy収支仮説を否定するものではない。Phase0ではnutrient/growthを無効にしており、formal Phase Aでgrowthを有効化したことで、**growth/anabolism Energy budgetの新たなscale mismatch** が露出した。

---

## 2. Phase A結果

| seed | extinction [h] | extinction [min] | max generation | final N | cause |
|---:|---:|---:|---:|---:|---|
| 15001 | 0.03889 | 2.333 | 0 | 0 | starvation 100/100 |
| 15002 | 0.03889 | 2.333 | 0 | 0 | starvation 100/100 |
| 15003 | 0.03611 | 2.167 | 0 | 0 | starvation 100/100 |
| 15004 | 0.03889 | 2.333 | 0 | 0 | starvation 100/100 |
| 15005 | 0.03889 | 2.333 | 0 | 0 | starvation 100/100 |

全seed:

- population max = 100
- generation = 0
- birthsは初期100個体のみ
- Matter ledger residual = 0
- Energy ledger residual = ~`5e-20–8e-20 J` 程度
- H2 biological uptake / source influx = 約`3e-7`

従って、数値発散・保存則破綻・個体数爆発ではない。

---

## 3. Phase0との違い

Phase0で確認済み:

- H2 field PASS
- source近傍にnet Energy positive region
- 遠方にnet Energy negative region
- random 100個体 / reproduction OFF / 48hで7個体生存
- chemotaxis / heterogeneous exposure成立
- dt収束PASS

formal Phase Aで新たにONになった主要項は **Matter precursor assimilation / growth**。

formal runnerではnutrientを一次Energy cueとして移動ターゲットにしない修正は入れていたが、precursor uptakeとgrowth Energy消費自体は有効だった。

---

## 4. 根本原因の定量診断

### 4.1 growth Energy cost

物理baseline:

```text
1 matter = 2.8e-16 kgDW
growth_energy = 5.0e6 J/kgDW
```

したがって:

```text
1 matter synthesis cost = 1.4e-9 J = 1.4 nJ
```

### 4.2 初期iLUCAのprecursor assimilation demand

reference:

```text
nutrient uptake cap = 0.20 matter/h * nutrient_absorption
nutrient_absorption(initial) = 0.5
```

なので資源豊富時:

```text
0.10 matter/h
```

を同化しようとする。

必要power:

```text
0.10 matter/h * 1.4e-9 J/matter / 3600
= 3.89e-14 W
= 38.9 fW
```

### 4.3 H2側との比較

Matter=0.5、chemical_absorption=1.0、H2=1 mM source cellで、現reference uptake式から得られるusable powerは概算:

```text
~2.0 fW
```

したがって:

```text
growth demand / maximum local H2 income
~ 19x
```

である。

baseline maintenanceはsub-fW級なので、今回の2分全滅を説明する主項はmaintenanceではなくgrowth。

### 4.4 初期Energyとの整合

Matter=0.5, storage_capacity=1.0の初期Energyはおよそ:

```text
4.87e-12 J
```

growth demandだけで消費すると:

```text
4.87e-12 / 3.89e-14 W ≈ 125 s
```

実測の全滅:

```text
130–140 s
```

とほぼ一致する。

よって **原因仮説は定量的にも強く支持される**。

---

## 5. 設計上の問題

現在のgrowthは概念的に:

```text
precursor available
  -> uptake capまで同化要求
  -> 現在持っているEnergyで払えるだけ支払う
  -> その後maintenance
```

となっている。

このため、外部Energy流入が不足していても、**貯蔵Energyを使い切るまで最大同化速度を維持**する。

これはV1.9で導入したhomeostasisと矛盾する。

生物学的には、anabolism/growthはATP/Energy状態に応じて抑制されるべきであり、maintenanceより優先してEnergy reserveを空にする固定growth demandは不自然。

---

## 6. 次の修正方針

H2 source濃度、H2 uptake能力、maintenance、storageを今回のFAILに合わせて変更しない。
Phase0でH2単独の正負Energy領域は既に成立しているためである。

次に修正すべき軸は **growth Energy allocation**。

推奨構造:

```text
1. catabolic Energy uptake (H2 etc.)
2. basal maintenance / required physiology
3. homeostatic Energy reserve
4. surplus Energyのみをgrowth/anabolismへ配分
5. reproduction
```

少なくともgrowthに使えるEnergyを:

```text
E_growth_available = max(0,
    E - protected_homeostatic_reserve)
```

のように制限し、Energyが低いとgrowthが自然に止まる構造へ変更する。

`protected_homeostatic_reserve`をstarvation/runway machineryと接続すれば、未来予測なしに現在のEnergy状態だけでgrowth suppressionを実装できる。

重要:

- `nutrient_uptake_rate`を単純に小さくしてPASSさせない
- H2濃度を上げて救済しない
- storageを増やして救済しない
- Phase Bを強行しない

これらは症状を隠すだけで、growth allocation問題を残す。

---

## 7. Exp15の扱い

今回のrunを削除・無効化しない。

```text
Exp15 attempt 1:
  Phase A = FAIL
  reason = growth/anabolism Energy allocation mismatch revealed
  Phase B = preregistered gateによりSKIPPED
```

として正式な診断結果として保存する。

growth allocation修正後は、同じH2 physical baseline、同じseed、同じPhase A/B構造を使い、`Exp15 rerun / attempt 2` として再実行する。

Phase Cは引き続き自動実行しない。
