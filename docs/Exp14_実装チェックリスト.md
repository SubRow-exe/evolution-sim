# Exp14 実装チェックリスト — HARD GATE

更新: 2026-09-03

正本:
1. `docs/Exp14_レビュー判断.md`
2. `docs/Exp14_実験計画確定.md`
3. `docs/次の実験計画.md`

**本チェックリストの未確認項目が1つでもある状態でformalを開始しない。**

---

# 1. 科学条件をコードへ1:1対応

## Phase A

- [ ] A0 baseline
- [ ] A1 cycle OFF / light=4/pi
- [ ] A2 period=80
- [ ] A3 light=8.0
- [ ] A4 repro_energy_frac=.8
- [ ] A5 initial_energy=40
- [ ] A6 energy_capacity=200 / initial_energy=100
- [ ] 各3 seed / 2k
- [ ] Phase A total=21

A6は`energy_capacity`だけ変更してinitial charge fractionを変える実装にしない。

## Phase B

- [ ] period = 80,120,160,200,240
- [ ] energy_capacity = 75,100,125,150,200
- [ ] 25 cells ×3 seed =75
- [ ] initial_energy = 0.5 * energy_capacity をgeneratorで導出
- [ ] light=4.0 / day_fraction=.5 / repro=.6
- [ ] 全遺伝子固定

## Phase C

- [ ] C1 body_sizeだけmutable
- [ ] C2 reproduction_investmentだけmutable
- [ ] C3 movement_powerだけmutable
- [ ] C4 上記3形質だけmutable
- [ ] 各5 seed
- [ ] Phase C total=20
- [ ] その他遺伝子はcanonical GENE_NAMESから固定

Formal total:

```text
21 + 75 + 20 = 116
```

- [ ] generator assert=116
- [ ] independent test assert=116

---

# 2. runtime profile

- [ ] FULL/COMPACTをコード上で明示
- [ ] profile選択は科学結果ではなくpreflight runtimeだけ
- [ ] FULL: A=2k / B=5k / C=20k
- [ ] COMPACT: A=2k / B=3k / C=10k
- [ ] FULL安全率込み<=9h -> FULL
- [ ] それ以外 -> COMPACT
- [ ] COMPACT予測>10hならformalを自動開始しない
- [ ] profileをmanifest/reportへ保存

Claudeがruntimeを理由にgrid/seedを独自削減しない。

---

# 3. preflight / formal分離

Exp13再発防止。

- [ ] preflight dispatchはformal matrixを起動しない
- [ ] preflight完了後workflowがsuccess/neutralで終了
- [ ] runtime reportをユーザーへ先に提示可能
- [ ] formalは別dispatch
- [ ] formalは選択済みprofileを明示入力/manifest固定
- [ ] 同一formal SHAを全Phaseで検証

---

# 4. R_ref

- [ ] R_ref helperは実装式と同じnight cost構成を使う
- [ ] light_maxをR_refへ直接入れない
- [ ] armごとのnight lengthを正しく使用
- [ ] capacity/repro条件の差を反映
- [ ] run前predicted R_refを保存
- [ ] R_refをfitness計算やsimulation stateへ使わない
- [ ] R_refは分析専用

独立test:
- [ ] A2のR_ref < A0
- [ ] A3のR_ref ≈ A0
- [ ] A4のR_ref < A0
- [ ] A6のR_ref < A0

数値一致をcheckerと同じ手書き定数だけで自己検証しない。

---

# 5. 判定

Phase A:
- [ ] SURVIVES_SHORT =3/3
- [ ] MARGINAL =2/3
- [ ] COLLAPSE =0-1/3
- [ ] 2k到達とfinal pop>0を確認
- [ ] EXTINCTをtechnical failure扱いしない

late semantics:
- [ ] late window未到達=N/A
- [ ] N/Aを分母/分子へ混ぜない
- [ ] early extinctionがlate PASSにならない

---

# 6. Recorder / collector

必須:
- [ ] sunset population
- [ ] dawn population
- [ ] daylight births
- [ ] night starvation deaths
- [ ] daytime peak
- [ ] night minimum
- [ ] night_min / preceding_day_peak
- [ ] Energy/capacity mean
- [ ] median
- [ ] p10
- [ ] p90
- [ ] Phase C trait summary
- [ ] lineage persistence

A1:
- [ ] realized density response Hを取得/再構成可能
- [ ] per-organism light uptakeを比較可能

観測非干渉:
- [ ] recorder ON/OFFでsame seed state一致
- [ ] RNG call count/stateへ影響なし

---

# 7. Scientific STOP vs Technical FAIL

- [ ] scientific collapse/stopでActionsを赤いtechnical failureにしない
- [ ] scientific stopでもreport/artifact upload
- [ ] crash/test/integrity/artifact欠落のみtechnical fail
- [ ] summaryにscience verdictとworkflow statusを別欄で出す

---

# 8. Artifact / integrity

各run:
- [ ] config.json
- [ ] meta.json
- [ ] stats.csv
- [ ] environment/snapshot必要分
- [ ] SHA
- [ ] seed
- [ ] arm/grid key
- [ ] runtime profile

collect:
- [ ] expected 116 key
- [ ] duplicate検出
- [ ] missing検出
- [ ] unexpected key検出
- [ ] numeric environment記録

resource interruptionはINCOMPLETE_RESOURCEとして同一SHA/Config再実行可能。

---

# 9. テスト

formal前:
- [ ] Exp14 config generator unit tests
- [ ] independent matrix count tests
- [ ] A6 initial fraction test
- [ ] Phase B initial_energy derivation test
- [ ] Phase C fixed/mutable genes test
- [ ] R_ref tests
- [ ] late N/A regression test
- [ ] scientific stop workflow logic test
- [ ] collector E2E with actual recorder format
- [ ] conservation
- [ ] determinism
- [ ] full pytest
- [ ] CI Green

---

# 10. 実装トレーサビリティ

formal前に必ず作る:

| Requirement | Implementation | Independent Test | Result |
|---|---|---|---|

最低限:
- A0-A6
- Phase B grid
- Phase C mutable genes
- runtime profile
- preflight/formal separation
- R_ref
- late semantics
- scientific status separation
- recorder outputs
- artifact completeness

空欄が1つでもあればGOしない。

---

# 11. formal開始直前の報告

ユーザーへformal開始前に:

```text
chosen profile: FULL or COMPACT
formal runs: 116
phase別tick
benchmark実測
max-parallel
wave数
setup/collect見込み
安全率
Exp14全体wall-clock予測
```

を報告する。

**報告前にformalを自動開始しない。**
