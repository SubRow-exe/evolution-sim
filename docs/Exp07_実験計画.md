# Exp07 実験計画 — V1.3 chemical source成立範囲の探索

更新: 2026-08-30
状態: **事前登録 / 未実行**

正本:
- `docs/V1.3_化学資源モデル仕様.md`
- 本書

## 1. 目的

Exp06では現行chemicalモデルのpositive controlまで全滅した。その後の設計監査で、chemical ventを想定しているにもかかわらず、stock依存のロジスティック増殖式を使っていたことが判明した。

V1.3ではchemicalを、**地質sourceから一定フラックスで継続供給され、局所stockとして一時蓄積し、混合・流出・酸化等で失われる一次Energy source**として再定義する。

Exp07の目的は、光との競争ではない。

> 新しいchemical sourceモデル単独で、持続可能な生態系が成立するsource flux範囲を測定し、通常祖先からの到達可能性と空間アクセスの問題を同時に診断する。

光量0.75/0.50系列、および光とchemicalの直接競争はExp07完了後まで保留する。

## 2. Exp07で光を0にする理由

Exp07では全条件 `light=0` とする。

理由:
- 新chemicalモデル単独のEnergy収支を検証するため
- 光で生存している個体がchemical成立性を隠すことを防ぐため
- source fluxとchemical生態の関係を直接読めるようにするため

Exp07で「chemical世界は光世界と違う進化形質になる」と結論することは目的ではない。

chemicalは光と同じ外部一次Energy sourceだが、V1.3では以下が異なる。
- sourceが局所ventに限定
- Energyがstockとして一時蓄積
- 未利用stockは環境損失する
- 局所stockを一時的に低濃度まで消費可能
- source fluxは生物消費に関係なく続く

したがって、光とは異なる進化圧が生じる可能性はあるが、Exp07ではまず成立性のみを主判定とする。

## 3. 固定条件

全run:

```text
light_pattern = uniform
light_max = 0.0
n_vents = 4
vent_radius_cells = 2
chem_capacity = 50.0
chem_loss_frac = 0.10
chem_uptake = 0.5
initial_population = 100
stats_interval = 20
snapshot_interval = 1000
max_population_halt = 20000
```

その他の生理・繁殖・mutation・nutrient・移動等はV1.2から変更しない。

## 4. 唯一振る世界パラメータ

`chem_vent_flux` [E/tick/vent] のみを変更する。

```text
4, 8, 12, 16, 24, 32, 48, 64
```

4 ventsなので世界全体の外部chemical sourceは:

| chem_vent_flux | world total source |
|---:|---:|
| 4 | 16 E/tick |
| 8 | 32 E/tick |
| 12 | 48 E/tick |
| 16 | 64 E/tick |
| 24 | 96 E/tick |
| 32 | 128 E/tick |
| 48 | 192 E/tick |
| 64 | 256 E/tick |

旧モデルの理論最大が約32.5 E/tickだったため、その周辺から約8倍まで広く探索する。

光V1.1の1,248 E/tickへ合わせることは目的にしない。chemicalは局所ニッチであり、より小さい総Energyでも持続可能な集団が成立すればよい。

## 5. 各fluxで3条件

### C — Chem-adapted / Vent

```text
chemical_absorption = 2.0 固定
initial placement = vent
```

目的:
> 新sourceモデルとそのfluxでchemical生態そのものが長期持続可能か。

最重要positive control。

### B — Ancestor / Vent

```text
初期ゲノム = 現行祖先
initial placement = vent
```

目的:
> 資源へ接触できている状態なら、現行祖先のchemical_absorption=0.3からchemical依存型へ進化可能か。

### D — Chem-adapted / Random

```text
chemical_absorption = 2.0 固定
initial placement = random
```

目的:
> 完成したchemical利用能力があっても、ventへの空間アクセス・探索がボトルネックになるか。

A（Ancestor / Random）は今回省略する。Bの進化bootstrapとDの空間accessという2つの障害を同時に含み、原因診断として情報量が低いため。

## 6. 本番規模

```text
8 flux
× 3 diagnostic conditions
× seed 1-10
= 240 run

ticks = 60,000
GitHub Actions / 同一数値実行環境
```

matrix 240でGitHub Actions上限256以内。

60kまで走らせる理由:
- Exp06では初期Energy/stockで一時的に人口増加してから200 tick以内に崩壊した
- 一過性の繁殖ではなくsource flowのみで多数世代が継続することを確認したい
- 長期population・stock・birth/deathが準定常になるかを見る

高fluxで `max_population_halt=20000` に到達した場合は実験失敗ではなく、**supercritical / carrying capacityが安全上限を超えた科学的結果**として扱う。

## 7. Pilot

本番前に実装健全性だけ確認する。

```text
flux = 4, 16, 64
condition = C/B/D
seed = 1
5,000 tick
9 run
```

Pilotで変更可能:
- source合計が設定値と一致しない
- stock更新式/台帳不整合
- light flowが0でない
- Config/placement/fixed gene不良
- output不良/crash

Pilotの生物学的結果を見てflux範囲を変更しない。

## 8. 主評価

### 生態成立性
- 60k生存率
- extinction tick
- `max_population_halt`到達率/tick
- population時系列
- 50k→60k population傾向
- births / deaths
- biomass

### chemical収支
- external chemical source累積
- chemical environmental loss累積
- overflow累積
- biological chemical uptake累積
- total chemical stock
- source利用率 = uptake / external source
- stockの時間平均/変動

### 進化bootstrap
B条件:
- mean/median chemical_absorption
- `chemical_absorption >= 0.5 / 1.0 / 1.5` 到達seed数と初回tick
- lineage population

### 空間access
D条件:
- vent_cell_frac
- vent occupancy
- mean distance to nearest vent（実装可能なら追加）
- occupied cells / centroid
- chemical背景GIF

### 参考形質
- body_size
- matter
- sensory_range
- movement_power
- reproduction_investment

ただしExp07は成立性診断であり、lineage sweepや「chemical型の最終最適形質」について強い結論を出さない。

## 9. 判定ロジック

### 段階1 — Cの成立境界

各fluxでCが長期持続するかを見る。

- Cが全fluxで絶滅
  - source flux不足だけでなく、uptake/生理/初期population/局所carrying capacity等を再監査
  - V1.3 source式だけではchemical niche成立に不足

- あるflux以上でCが生存
  - chemical一次生産のecological viabilityが成立
  - その境界を以後の診断基準にする

- 高fluxでpopulation halt
  - 供給過多側を示す。恒久default候補から外すか追加微調整する

### 段階2 — Bとの比較

Cが成立するfluxでBが:

- 成立 → 現行祖先からchemical利用へ到達可能
- 絶滅 → chemical生態は可能だが初期chemical_absorption/変異幅/進化上の谷を疑う

### 段階3 — Dとの比較

Cが成立するfluxでDが:

- 成立 → 完成chemical型はrandom配置からventへ定着可能
- 絶滅 → sensory/探索/vent密度・面積が主要ボトルネック

## 10. 恒久defaultの選び方

Exp07結果後、`chem_vent_flux`を「光と同程度になるように」決めない。

候補条件:
1. Cが10/10または高率で60k持続
2. population haltを常態化させない
3. chemical stockが常時capacity張り付きでも常時0でもなく、消費と環境損失が両方観測できる
4. 可能ならB/Dの診断にも意味がある範囲

境界周辺が粗い場合のみ、Exp07bとしてfluxを狭く追加する。

## 11. Exp07後の展開

### C成立・B成立・D成立

複数Energy経路を比較する最低条件が揃う。

次:
- V1.1互換 `vertical` 光 + 新chemical sourceを同居
- 光/chemical両経路が自然にどう使い分けられるか比較
- これを初めて「一次Energy戦略間の競争/共存」実験として扱う

### C成立・B不成立

初期ゲノム/standing variation/変異幅を1軸ずつ診断。

### C成立・D不成立

sensory_range / 行動 / vent密度・面積を1軸ずつ診断。

### C不成立

source以外のchemical生理収支・局所初期密度を再監査。

## 12. 当面残す懸念

1. chemical uptakeが個体リスト順の逐次処理であり、stock不足時に順序biasがあり得る
2. chemical diffusion/advectionをまだ表現しない
3. `chem_loss_frac=0.10`は実時間校正されていない
4. initial_population=100をvent上へ置くC/Bは局所過密を起こし、成立に必要なfluxを高める可能性がある
5. tickの現実時間対応が未定義

これらはExp07の成立性結果を見て優先順位を決める。

特に4について、Cが高fluxでも不自然に崩壊する場合は「chemical sourceが弱い」と即断せず、founder density / local carrying capacityを次の診断候補にする。

## 13. 過去結果との関係

Exp03〜05の観測値・sweep・光利用経路内部での比較は保持する。

撤回/修正する解釈:

> 複数の一次Energy戦略が十分成立可能な世界で、自然選択により光利用型が勝った。

Exp06によりこれは支持されない。

V1.3/Exp07は、まず複数戦略を比較可能な世界を成立させるためのモデル整合性修正と基礎診断である。
