# Exp15 V1.9 結果・考察

更新: 2026-09-07
状態: **ATTEMPT 2 PHASE A SCIENTIFIC PASS / PHASE B PENDING WORKFLOW FIX**

Exp15はV1.9 physical iLUCAが成立し、世代交代できるかを確認したうえで、新規3形質の進化価値を検証する実験である。

---

# 1. Attempt 1 — physical baseline FAIL

対象run: `33859051915`

結果:

```text
5/5 seedで約2.2–2.3分以内に全滅
max generation = 0
Phase B = preregistered gateによりSKIP
```

保存則・H2 field自体は正常だった。

根本原因はgrowth/anabolism Energy allocationで、precursor assimilationが外部Energy収入と無関係にstored Energyを大量消費し、maintenance/homeostasisより先にEnergy reserveを空にしていた。

定量的には初期個体のgrowth demandがH2 incomeを大きく上回り、初期Energyを約125 sで消費する計算が実測130–140 s全滅と一致した。

判断:

- H2濃度を後付けで増やして救済しない
- storageを増やして救済しない
- growth rateだけを恣意的に下げない
- LUCA-like physiologyとEnergy allocationを文献拘束で再設計する

Attempt 1は失敗として保持する。

---

# 2. Attempt 2 — literature-constrained LUCA-like proxy

実装commit: `ee9f181612b24c39d5bd092f8cd0310dfcde2cc7`
GitHub Actions run: `33871356278` (`Exp15 V1.9 LUCA Proxy`)

主要変更:

```text
anaerobic H2-dependent CO2-fixing acetogen-like LUCA proxy
physical H2 uptake / ATP / maintenance / growth parameters
maintenance-first / homeostatic-reserve-protected growth allocation
H2 source reference = 10 mM
```

growthは

```text
P_full * starvation_horizon
```

に相当するhomeostatic Energy reserveを侵食しない。余剰Energyのみanabolismへ使用する。

## 2.1 6-hour sanity

```text
100 / 100 alive
deaths = 0
Matter mean: 約0.500 -> 0.552
Energy conservation PASS
Matter conservation PASS
```

Attempt 1の2分全滅は解消し、単なる延命ではなく実際にMatter growthが起きた。

## 2.2 Formal Phase A

5 seed x 10 physical daysを固定iLUCAで実行。

| seed | final N | max generation | stop |
|---:|---:|---:|---|
| 15001 | 2979 | 5 | duration complete |
| 15002 | 3021 | 5 | duration complete |
| 15003 | 2934 | 5 | duration complete |
| 15004 | 2956 | 5 | duration complete |
| 15005 | 3009 | 5 | duration complete |

全seedで10日間生存し、全seedがmax_generation=5へ到達した。

generation interval medianは各seedで約55 h前後。

したがって事前登録gate:

```text
>= 3/5 seeds reach max_generation >= 5
```

に対し、実データは

```text
5/5 PASS
```

である。

**科学的にはPhase A adequacy gate PASS。**

---

# 3. Phase Bが実行されなかった理由

Actions workflow上ではgate jobがsuccess終了した後、Phase BがSKIPされた。

しかしindividual artifactsを直接確認すると5/5 seedがgeneration 5へ到達しているため、これは科学的FAILではない。

原因はgate/aggregate側がPhase A summary artifact pathを期待どおり収集できなかったworkflow integration issueと判断する。

従って記録は:

```text
Exp15 Attempt 2 Phase A = SCIENTIFIC PASS
Phase B = NOT YET RUN (workflow gate artifact collection bug)
```

とする。

Attempt 2を「gate fail」と解釈してはならない。

---

# 4. Exp15から得た主要知見

1. SI単位へ移行するだけでは生物学的に成立しない。Energy allocation semanticsが必要だった。
2. LUCA-like acetogen proxy + maintenance-first allocationにすると、H2 physical environment内で生存・成長・分裂が再現性高く成立する。
3. baseline 10 mM / D=5e-9 / tau=900 s / square sourceは、少なくとも10日・5世代の成立を支える。
4. fixed iLUCAの成立確認は完了したので、次は新規3形質の進化価値を検証できる。

---

# 5. 次のPhase B

workflow gate処理を修正したうえで、Attempt 2 Phase Aと同じbaseline・seed方針を維持してPhase Bを実行する。

進化ONは以下3形質だけ:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

その他の遺伝子、phototrophy/predation innovationは固定/OFF。

目的は、環境を生存可能に調整することではなく、**現在のV1.9環境に対してこの3つの生理戦略が自然選択に使われるか**を確認すること。

Exp16環境ロバストネスの結果から、Phase B前にbaseline environmentを再調整する必要はない。

---

# 6. Version

Attempt 1 -> Attempt 2のLUCA proxy導入とmaintenance-first Energy allocationは、人間判断によりV1.9へ包含済み。

Exp15は全Attemptを通して**V1.9**。
