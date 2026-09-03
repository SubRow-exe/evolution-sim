# Exp14 実験計画確定 — light昼夜絶滅mechanism切り分け

更新: 2026-09-03
状態: **人間方針確定 / 実装・実行前**

関連:
- `docs/Exp13_結果考察_中間.md`
- `docs/V1.8_一次Energy生態非対称仕様.md`
- `docs/Exp13_実験計画確定.md`（Exp13事前登録の履歴。結果後に書き換えない）

---

# 1. 背景

Exp13 Phase A1では:

```text
light_max = 0.8〜4.0
全8水準 ×5 seed
```

がすべて10k前に絶滅し、`selected_light_max`を決められなかった。

特に`light_max=4.0`では:

```text
初期100
→ 最初の昼に440〜503まで増殖
→ 最初の夜明けまでに8〜16程度へ崩壊
→ 次の昼に再繁殖
→ 次の夜で再崩壊
→ 全seed starvation extinction
```

が見られた。

したがってExp14では **light_maxを闇雲に上へ延長する前に、何が絶滅を作っているかを切り分ける。**

---

# 2. Exp14の問い

主要仮説:

```text
H1: 1周期の平均light量そのものが不足
H2: 100 tick連続の完全暗期が現在の代謝/貯蔵時間スケールに対して長すぎる
H3: 昼の急速繁殖がEnergy reserveを子へ分配し、夜越し能力を落としている
```

Exp14はこの3要因を小さいdiagnostic matrixで分離する。

これはworking `light_max`を最終決定する実験ではない。

---

# 3. 原則

- V1.8のEnergy吸収式そのものは変更しない
- `bmr_core=0.15`を変更しない
- 初期genomeを各環境へ適応させて救済しない
- chemical条件を再sweepしない
- 進化OFF
- 全遺伝子固定
- diagnostic変更以外を同時に変えない
- 結果を見て同じExp14内で条件を後付け追加しない

Exp13 A2 chemical grid結果はそのまま保存する。

暫定chemical候補:

```text
chemical_uptake_half = 1.5
chem_uptake = 0.5
```

ただしA2b/A3未実施なので正式確定ではない。

---

# 4. 共通baseline

Exp13 A1と同じlight specialist:

```text
light_absorption = 2.0
chemical_absorption = 0.3
その他 = INITIAL_GENOME
全14遺伝子固定
initial_population = 100
initial_energy = 50
initial_matter = 0.8
placement = random
light_pattern = vertical
chemical = OFF
primary_energy_density_response = True
```

baseline:

```text
light_cycle_enabled = True
light_cycle_period_ticks = 200
light_day_fraction = 0.5
light_max = 4.0
repro_energy_frac = 0.6
```

各条件:

```text
seed = 1..3
ticks = 2,000
```

2,000 tickならbaselineの絶滅を十分再現しつつ、period=200で最大10周期観測できる。

---

# 5. 条件

## A0 — Exp13 baseline再現

```text
cycle ON
period = 200
light_max = 4.0
repro_energy_frac = 0.6
```

目的:
- Exp13 boom-bust再現
- Exp14 recorder/collectorが正しく現象を拾うことの基準

---

## A1 — 同じ時間平均light、夜だけ除去

```text
cycle OFF
light_max = 4 / pi ≈ 1.2732395447
repro_energy_frac = 0.6
```

half-sine + day_fraction=.5 の`light_max=4.0`は一周期時間平均factorが`1/pi`。

したがってcycle OFFで`light_max≈1.27324`にすると、各cellの長時間平均供給量をほぼ維持したまま **連続暗期だけ除去** できる。

解釈:
- A1がA0より大きく改善 → 平均light不足だけでなく「連続夜」が主要因

---

## A2 — 同じ平均light、昼夜周期を短縮

```text
cycle ON
period = 80
light_day_fraction = 0.5
light_max = 4.0
repro_energy_frac = 0.6
```

```text
40 tick daylight
40 tick darkness
```

平均light量・昼夜比率は維持し、最大連続暗期を100→40 tickへ短縮する。

解釈:
- A2がA0より大きく改善 → period=200が現在の代謝/貯蔵時間スケールに対して長すぎる可能性

---

## A3 — 夜長は同じ、総light量を増加

```text
cycle ON
period = 200
light_day_fraction = 0.5
light_max = 8.0
repro_energy_frac = 0.6
```

解釈:
- A3がA0より大きく改善 → 総light不足の寄与が大きい
- 昼のpopulation boomだけ増えて夜崩壊が改善しない/悪化 → light量単独増加では根治しない

---

## A4 — 夜・光量は同じ、繁殖Energy閾値だけ上げる

```text
cycle ON
period = 200
light_day_fraction = 0.5
light_max = 4.0
repro_energy_frac = 0.8
```

その他の繁殖ルールは変更しない。

目的:
- 昼間にEnergyを得た直後の過剰繁殖と、夜越しreserveの関係を診断する
- 初期Energy=50が`repro_energy_frac=.6`条件で繁殖しやすい影響も弱める

解釈:
- A4がA0より大きく改善 → reproduction/reserve tradeoffが主要因の一つ

A4は恒久的な繁殖仕様変更候補ではなく、**diagnostic intervention**である。

---

# 6. run数

```text
5 conditions × 3 seeds × 2,000 tick
= 15 formal simulation runs
```

Exp14ではこれ以上の条件を同一実験へ後付けしない。

---

# 7. 必須観測

既存:
- population trajectory
- births_cum
- deaths / starvation
- total_energy
- flow_light_cum
- light_cycle_factor
- light_supply_rate
- movement

Exp14で明確に追加/集計:

```text
population at sunset / dawn
births per daylight interval
deaths_starvation per darkness interval
daytime peak population
night minimum population
night_min / preceding_day_peak
Energy per living organism
organism Energy/capacity distribution:
  mean / median / p10 / p90
```

できれば日没直前・夜明け直後のEnergy/capacity distributionを明示的に保存する。

Recorder追加は観測のみとし、RNG/state/更新順へ影響してはいけない。

---

# 8. Exp14前のtechnical修正

## 8.1 late metric semantics

Exp13集計で、early extinctionなのに`late_pop_ok=True`となる表示があった。

Exp14前に:
- late windowへ到達していないrunをlate PASSに数えない
- `False`または`N/A`として区別
- unit testを追加

## 8.2 scientific STOPとtechnical FAILの分離

Exp13は`LIGHT_CALIBRATION_FAIL / REVIEW`という科学結果で停止したが、Actions全体が赤い`failure`になった。

今後:

```text
SCIENTIFIC_STOP / REVIEW
```

はtechnical failureと区別する。

最低限:
- report/artifactを必ずupload
- summaryへscientific stop reasonを明示
- crash / test fail / artifact欠落 / integrity違反だけをtechnical FAILとする

---

# 9. 読み方

Exp14は単一PASS/FAILでなく因果診断。

### A1改善

```text
same mean Energy + no night
```

で改善するため、連続暗期が重要。

### A2改善

同じ平均供給・同じday fractionでperiodだけ短くして改善するため、**環境変動時間スケール vs 生体時間スケール**が重要。

### A3改善

夜長を維持しlightだけ増やして改善するため、総供給不足が重要。

### A4改善

同じ光・同じ夜で繁殖閾値のみ変えて改善するため、繁殖によるreserve放出が重要。

### 複数条件が改善

原因は単独ではなくinteraction。

Exp14結果を受け、次実験で必要最小限のfactorial/parameter mapを設計する。

### どれも改善しない

V1.8 light uptake、Energy capacity、BMR、movement cost、初期条件、reproduction transfer等をmechanism auditし、単純light map再開はしない。

---

# 10. Exp14の終了条件

15 run完全性を確認し、条件ごとに:
- extinction/complete
- extinction time
- cycle-by-cycle population
- cycle-by-cycle births/starvation
- Energy reserve distribution

を比較できれば終了。

Exp14内ではworking `light_max`を確定しない。

---

# 11. runtime運用

正式dispatch前に **Exp14全体の予想wall-clock** を報告する。

1 run時間だけでなく:
- 15 run
- 2,000 tick
- max-parallel
- wave数
- preflight/collect

を含む全体概算を出す。

実行後はprediction vs actualも記録する。

---

# 12. Exp14後

想定:

```text
Exp14 原因切り分け
  ↓
原因が明確
  ↓
次実験で light_max / cycle period / 必要ならreproduction-reserve interaction を適切に地図化
  ↓
working lightを選定
  ↓
Exp13で保留したchemical長期確認・mixed worldへ戻る
```

Exp13の未実施Phase Bを、そのまま条件変更してExp13として再開しない。結果後の条件変更は別実験番号で追跡する。
