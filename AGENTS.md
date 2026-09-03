# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/次の実験計画.md` — **現在の司令塔**
2. `docs/Exp15_実験計画確定.md` — **Exp15科学条件の正本**
3. `docs/Exp15_実装チェックリスト.md` — **Sonnet実装仕様の正本**
4. `docs/Exp14_表現型プロベナンス訂正.md` — **Exp14結果解釈への正式訂正**
5. `docs/環境因子追加・校正方針.md` — プロジェクト全体の恒久校正方針
6. `docs/V1.8_現状総括_Exp14結果.md` — Exp13/14結果・背景
7. `docs/V1.8_一次Energy生態非対称仕様.md` — V1.8物理仕様
8. `docs/Exp14_実験計画確定.md` — 履歴。**再dispatchしない**
9. `docs/Exp14_レビュー判断.md`
10. `docs/Exp13_結果考察_中間.md`
11. `docs/V1.8_Exp13_レビュー判断.md`
12. `docs/Exp13_実験計画確定.md` — 履歴。**再dispatchしない**
13. `docs/V1.7_総括.md`
14. `docs/メインストリーム開発ストーリー.md`
15. `docs/数値再現性・Actions実行環境方針.md`
16. `docs/実験結果保存方針.md`
17. `docs/バージョニング方針.md`

過去レビュー原文より、人間採否文書と現在の司令塔を優先する。

---

# 2. 現在地

```text
V1.4 / Exp08                  完了
V1.5 / Exp09                  完了
V1.6 / Exp10                  完了
V1.7 / Exp11 / Exp12          完了 / bmr_core=.15
V1.8実装                      完了 / main merge済み
Exp13                         完了 / light calibration scientific STOP
Exp13 chemical grid           完了 / 暫定候補あり
Exp14                         完了 / 116/116 raw回収
Exp14 phenotype provenance    訂正済み
Exp15科学設計                 確定
Exp15実装                     現在の最優先作業
Exp15 preflight/formal        未実行
V1.8 final acceptance         未完了
```

**現在AIが行うべきことはExp15 harness実装・test・実装監査まで。formalを勝手に開始しない。**

---

# 3. Exp14 provenance訂正

Exp14計画はlight specialist:

```text
light_absorption=2.0
chemical_absorption=.3
```

を意図したが、`make_exp14_configs.py`に`diagnostic_gene_overrides`が無かった。
formal workflowはそのgeneratorを直接使ったため、実際の116 runは:

```text
INITIAL_GENOME
light_absorption=.3
chemical_absorption=.3
```

で走った。

したがって:
- raw実測事実は保存
- Exp14内の相対傾向はactual phenotype=.3条件の探索的証拠
- Exp13/V1.7 light specialistとの定量比較には使わない
- Exp14から恒久parameterを選ばない
- Exp14を再dispatchせずExp15で正しい表現型を使う

詳細は`docs/Exp14_表現型プロベナンス訂正.md`。

---

# 4. V1.8絶対方針

```text
light
- broad
- renewable flow
- day/night
- low-average input
- surface area + intensity dependent

chemical
- localized stock
- depletable
- competitive
- high-local-return potential
- vent source replenishes
```

一次Energy直接吸収のみ:

```text
H(x,K)=x/(x+K)
```

light day/nightはhalf-sine / day_fraction=.5。
energy中立正規化しない。

絶対にしない:
- light直接fitness penalty
- chemical固定Energy bonus
- plant/cyanobacteria/chloroplast class
- oxygen field
- finite vent lifetime
- V1.8でINITIAL_GENOME.light_absorption=0
- 小型化だけを防ぐためのbmr_core再調整
- light userだけを強制静止

phototrophy起源はV1.9事項。

---

# 5. プロジェクト全体の校正原則

`docs/環境因子追加・校正方針.md`を恒久方針とする。

長期目標はiLUCA（LUCA-inspired）から多様な生物戦略、陸上移動、飛翔まで進化可能な世界を段階的に作ること。
今後、気温・重力・水深/水圧・酸素・pH・放射線・毒物など多数の環境因子を追加するため、各段階で少数因子だけを前提に厳密なglobal optimumを探さない。

```text
1. 原因・寄与を単独で切り分ける
2. 即死でも無影響でもない粗い成立域を見つける
3. 複数世代成立・意味ある選択圧・非支配的を確認
4. knife-edgeでないworking referenceを暫定採用
5. 最小限のinteraction確認後、次の環境因子へ進む
6. 多数因子が揃った段階で全体balanceを再調整
```

精密threshold探索は必要な場合だけ行う。

---

# 6. Exp15科学条件 — 変更禁止

## Phase A

```text
light specialist: light_absorption=2.0 / chemical_absorption=.3
全14遺伝子固定
light-only
light_max=1.2
seed=1..5
ticks=5,000

A0 cycle OFF / density OFF
A1 cycle OFF / density ON
A2 cycle ON  / density OFF
A3 cycle ON  / density ON
A4 A0完全duplicate sentinel
```

A0-A3はfeature flag以外を変更しない。
A0/A4はConfig完全一致・同seed科学出力一致を要求する。

A0が成立しなければ`BASELINE_NOT_VIABLE`で科学STOP。Phase Bへ自動遷移しない。

## Phase B

combined固定で`light_max`のみ:

```text
1.2 / 2.4 / 4.0 / 6.0 / 8.0 / 12.0
seed=1..3
ticks=10,000
```

他の固定値:

```text
light_uptake_half=.6
period=200
day_fraction=.5
energy_capacity=100
```

隣接2 tested levelが連続VIABLEになった最初のpairの低い側をworking reference候補とする。
成立しなければ`NO_ROBUST_LIGHT_REFERENCE`。Exp15へ追加sweepを後付けしない。

詳細は`docs/Exp15_実験計画確定.md`。

---

# 7. Exp15最重要HARD GATE

Exp14再発防止としてConfig検査だけでは不十分。

必ず`Simulation(cfg, seed)`を初期化し、初期100個体全て:

```text
light_absorption == 2.0
chemical_absorption == 0.3
```

を独立testする。

formal前に:
- fixed_genes canonical 14
- overrides actual organism E2E
- A0-A3 flag-only diff
- A0=A4
- Phase B light_max-only diff
- chemical OFF
- observation noninterference
- conservation/determinism
- full pytest

をGREENにする。

---

# 8. Exp15観測

最低限:

```text
realized light gain / organism-tick
maintenance+movement / organism-tick
repair / organism-tick
birth overhead / organism-tick
core net Energy / organism-tick
Energy/capacity distribution
light H(I,K) distribution
birth timing
population
survival/extinction
max generation
sunset/dawn reserve
```

H観測ではnight I=0を分布へ混ぜない。

観測counterはsimulationへフィードバックしない。RNG/state/update orderを変えない。

---

# 9. Exp15 Actions構造

```text
mode=preflight
mode=phase_a
mode=phase_b
```

を別dispatchとして実装する。

禁止:
- preflight成功→formal自動開始
- Phase A成功→Phase B自動開始

formal前にphase全体wall-clockを予測。
10時間超なら条件をAI判断で削らず人間へ報告。

詳細は`docs/Exp15_実装チェックリスト.md`。

---

# 10. 実装・実験品質HARD RULE

- requirement → implementation → independent test → resultを追跡
- ConfigだけでなくSimulation実個体までE2E検証
- generator/checker/testが同じ誤定数を自己検証しない
- Config / fixed_genes / collector / artifact keyを独立test
- preflightとformalを分離
- scientific STOPとtechnical FAILを分離
- scientific STOPでもartifact/reportを保存
- late window未到達はN/A
- recorder/analysis追加はRNG/state/update orderへ影響させない
- full pytest / conservation / determinism / CI Greenを正式実験前に確認
- 途中デバッグpushを乱発しない
- artifact完全性を機械検証する

---

# 11. Chemical

Exp13暫定候補:

```text
chemical_uptake_half=1.5
chem_uptake=.5
```

Exp15 light整理後に長期/探索/density validationへ戻る。

---

# 12. プロジェクト絶対原則

- 適応度を直接計算しない
- 完成した種classを作らない
- 寿命を直接設定しない
- costは物理/生理則から
- Matter保存 / Energy台帳
- RNG / 決定性
- 想定外戦略を許容
- 特定生態型へ直接bonusしない
- 遺伝子の存在と進化経路の成立を区別
- Energy戦略は単独成立性を先に確認
- 行動へ未来予測/知能を暗黙導入しない
- 結果後に同一experimentへ条件を思いつき追加しない
- 科学STOPと技術FAILを分離
- 各環境因子の局所最適化より、多因子世界で進化継続可能なrobustnessを優先する

---

# 13. V1.8をfinalizeしない条件

未完了:

```text
Exp15
light working reference
chemical long-term validation
light-only long-term viability
chemical-only long-term viability
mixed evolution validation
V1.8 ACCEPT
v1.8-final保存
```

これらが終わるまでV1.8をfinal扱いしない。

V1.8導入済み機構のworking parameter調整はV1.8 finalizationであり、V1.9へ前倒ししない。

---

# 14. V1.9以降

```text
V1.8 source物理分化
 -> V1.9 chemical-first ancestorからphototrophy創発
 -> dynamic vents/resource turnover
 -> HGT
 -> engulfment/intracellular symbiosis
 -> plastid-like integration
 -> oxygenic photosynthesis/planetary feedback
```

---

# 15. Exp15実装完了条件

AIは以下まで行う:

```text
- harness実装
- tests GREEN
- docs/Exp15_実装監査.md作成
- preflight実行可能状態
```

**preflight/formalを勝手にdispatchしない。**

技術stack: Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest
