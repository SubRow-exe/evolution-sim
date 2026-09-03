# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/次の実験計画.md` — **現在の司令塔**
2. `docs/V1.8_現状総括_Exp14結果.md` — **Exp13/Exp14結果・現在解釈・次チャット引継ぎ正本**
3. `docs/V1.8_一次Energy生態非対称仕様.md` — V1.8物理仕様
4. `docs/Exp14_実験計画確定.md` — Exp14事前登録履歴。**再dispatchしない**
5. `docs/Exp14_レビュー判断.md` — Exp14レビュー採否履歴
6. `docs/Exp13_結果考察_中間.md` — Exp13実測/原因考察履歴
7. `docs/V1.8_Exp13_レビュー判断.md`
8. `docs/Exp13_実験計画確定.md` — Exp13事前登録履歴。**再dispatchしない**
9. `docs/V1.7_総括.md`
10. `docs/メインストリーム開発ストーリー.md`
11. `docs/数値再現性・Actions実行環境方針.md`
12. `docs/実験結果保存方針.md`
13. `docs/バージョニング方針.md`

過去レビュー原文より、必ず人間採否文書と現在の司令塔を優先する。

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
Exp14                         完了 / 116/116 run回収
V1.8 final acceptance         未完了
```

Exp13/Exp14をそのまま再dispatchしない。

---

# 3. V1.8絶対方針

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

# 4. Exp14で確定した主要結果

```text
116/116 run 最終絶滅
死亡原因 = starvation
Generation 2 = 0
```

支持された要因:

1. continuous nightは大きな負荷
2. storage capacity不足も存在
3. tick1一斉繁殖は増悪因子
4. light_maxを2倍にするだけではほぼ解決しない
5. R_refは一晩越しの診断には有用だが、長期成立を説明しない

詳細は`docs/V1.8_現状総括_Exp14結果.md`。

---

# 5. 最重要の現在解釈

Exp14 A1はV1.7回帰ではない。

A1:

```text
cycle OFF
primary_energy_density_response ON
light_max=4/pi
```

V1.7型:

```text
cycle OFF
primary_energy_density_response OFF
static light
```

したがって、A1の絶滅を根拠に「V1.7型の昼だけでもEnergy赤字」と断定してはいけない。

次の最優先課題は、V1.8で同時導入した2機構を独立比較すること。

```text
cycle OFF / density OFF
cycle OFF / density ON
cycle ON  / density OFF
cycle ON  / density ON
```

新しいformal条件・Exp番号は人間判断前に勝手に確定しない。

---

# 6. 次の診断で見る量

最低限:

```text
realized light gain / organism-tick
maintenance + movement + repair / organism-tick
net Energy balance
Energy/capacity distribution
birth timing
population
survival/extinction
```

`light_max`や時間平均供給量を何に揃えるかは実験前に人間と合意する。
結果を見た後で同一experimentの比較条件を追加しない。

---

# 7. Chemical

Exp13暫定候補:

```text
chemical_uptake_half=1.5
chem_uptake=.5
```

Exp14はlight-onlyなので、この候補を否定しない。
Light側の基礎Energy収支整理後に長期/探索/density validationへ戻る。

---

# 8. 実装・実験品質HARD RULE

- requirement → implementation → independent test → resultを追跡
- Config / fixed_genes / collector / artifact keyを独立test
- preflightとformalを分離
- preflight成功後にformalへ自動遷移しない
- formal前に**実験全体**wall-clock予測を報告
- scientific STOPとtechnical FAILを分離
- scientific STOPでもartifact/reportを保存
- late window未到達はN/A
- recorder/analysis追加はRNG/state/update orderへ影響させない
- full pytest / conservation / determinism / CI Greenを正式実験前に確認
- 途中デバッグpushを乱発しない
- checkerとgeneratorが同じ誤った手書き定数を共有しない

---

# 9. プロジェクト絶対原則

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

---

# 10. V1.8をfinalizeしない条件

未完了:

```text
light working reference
chemical long-term validation
light-only long-term viability
chemical-only long-term viability
mixed evolution validation
V1.8 ACCEPT
v1.8-final保存
```

これらが終わるまでV1.8をfinal扱いしない。

---

# 11. V1.9以降

```text
V1.8 source物理分化
 -> V1.9 chemical-first ancestorからphototrophy創発
 -> dynamic vents/resource turnover
 -> HGT
 -> engulfment/intracellular symbiosis
 -> plastid-like integration
 -> oxygenic photosynthesis/planetary feedback
```

メインストリーム方針は現時点で変更しない。

---

# 12. 実験結果保存

`docs/実験結果保存方針.md`に従う。

GitHub:
- 結果考察
- aggregate plot/table
- runtime prediction vs actual
- scientific/technical verdict

raw:
- Actions artifact / external storage

技術stack: Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest
