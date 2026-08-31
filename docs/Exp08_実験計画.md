# Exp08 実験計画 — V1.4 吸収則の校正

更新: 2026-08-31
状態: **方針確定 / V1.4実装後に実行**

正本:
- `docs/V1.4_一次エネルギー吸収仕様.md`
- 本書
- `docs/Exp07_結果考察.md`

## 1. 目的

Exp08は「光とchemicalのどちらが進化的に勝つか」を調べる実験ではない。

V1.4で一次Energy吸収則を変更した直後に、以下を校正・検証する。

1. 光利用能力が実際の個体吸収量を律速するか
2. 有効表面積 `matter^(2/3)` が意図どおり作用するか
3. 光/chemicalの資源不足時の配分が個体処理順に依存しないか
4. V1.4後も光単独・chemical単独の完成戦略が生態として成立可能か
5. 恒久default候補の `light_uptake_coef` と `chem_vent_flux` の範囲を決める

まだ光+chemicalを同居させない。

## 2. Exp08で変更しないもの

- 初期ゲノムの恒久値
- mutation rule
- movement/sensoryの基本則
- reproduction
- metabolic cost
- `chem_uptake=0.5`
- n_vents=4
- vent_radius_cells=2
- chem_loss_frac=0.10
- nutrient world total
- 日照時間変動
- 捕食/死骸ルール

## 3. Phase 0 — 決定論的な吸収ベンチテスト

本番run前にseed依存しない診断スクリプトを作る。

目的:
- 数式そのものを確認
- 長時間進化runを使わずに黒字/赤字境界を見る

### 3.1 body size / surface scaling

評価matter:

```text
0.5, 0.8, 1.0, 2.0, 4.0, 8.0
```

確認:

```text
A_eff = matter^(2/3)
```

特に:

```text
matter 1 → A_eff 1
matter 8 → A_eff 4
```

を機械的に固定する。

### 3.2 光

`light_absorption`:

```text
0.3, 1.0, 2.0, 5.0
```

`light_uptake_coef`候補:

```text
1.0, 1.5, 2.0
```

各matterについて:
- 個体最大光吸収量/tick
- 現行維持費/tick
- 静止時net Energy/tick
- cell光量が上限になる条件

を表で出力する。

### 3.3 chemical

`chemical_absorption`:

```text
0.3, 1.0, 2.0, 5.0
```

`chem_uptake=0.5`固定。

同様に最大吸収・維持費・net Energyを計算する。

### 3.4 密度競争

同一セルに:

```text
1 / 5 / 20 / 100 個体
```

を置き、光/chemicalそれぞれで:
- 供給十分
- 供給不足

を作る。

個体リスト順を逆転・shuffleしても、同じ個体状態なら配分総量/各demand比が一致することを確認する。

## 4. Phase A — 光単独の生態校正

### 4.1 世界

```text
chemical source = 0
light_pattern = vertical (V1.1互換)
nutrient等 = V1.4 default
```

V1.1の光空間分布を維持し、変えるのは `light_uptake_coef`だけ。

候補:

```text
1.0 / 1.5 / 2.0
```

### 4.2 2診断条件

#### L0 — Ancestor-light fixed

```text
初期ゲノムは通常祖先
light_absorptionのみ初期値≈0.3で固定
```

目的:
> 低い光利用能力が「能力が低いのにセル光を全取得」せず、現実に吸収上限として機能した状態で祖先がどの光環境まで維持可能か。

#### L2 — Light-adapted fixed

```text
light_absorption=2.0固定
その他は通常祖先
```

目的:
> 完成した光利用能力を持つ生物がV1.4光環境で長期成立可能か。

### 4.3 規模

```text
3 light_uptake_coef
× 2条件
× 10 seed
= 60 run

60,000 tick
```

V1.4直後の校正なので、まず60kとする。
境界が曖昧な場合のみExp08bを事前登録して延長/追加seedする。

### 4.4 主評価

- 生存率 / extinction tick
- population / biomass
- 実際のlight uptake/tick
- 世界光供給に対する利用率
- mean matter / body_size
- net Energy budget
- 明暗帯別population

特にL0で低い `light_absorption` があるにもかかわらず高率でセル光を全量利用していないことを確認する。

## 5. Phase B — chemical単独の再校正

V1.4ではchemical吸収も `matter` → `matter^(2/3)` へ変わり、処理順biasも除去するため、Exp07の成立境界を短縮版で再確認する。

### 5.1 条件

```text
light = 0
chemical_absorption=2.0固定
初期配置=vent
chem_uptake=0.5固定
```

`chem_vent_flux`候補:

```text
8 / 16 / 24 E/tick/vent
```

理由:
- 8: Exp07で成立した現V1.3 default
- 16: 典型ventセルで約1.23 E/tick供給
- 24: 典型ventセルで約1.85 E/tick供給

### 5.2 規模

```text
3 flux × 10 seed = 30 run
60,000 tick
```

### 5.3 主評価

- 生存率
- population / biomass
- chemical source利用率
- stock
- vent滞在率
- body_size / matter
- 1個体当たりchemical uptake

Exp07のように通常祖先bootstrapはここでは再実行しない。
まず完成chemical型の生理・生態がV1.4吸収則でも成立することを確認する。

## 6. Exp08総規模

進化run:

```text
Phase A 60 run
Phase B 30 run
合計 90 run × 60,000 tick
```

加えてPhase 0の決定論的ベンチテスト。

GitHub Actionsで同一OS/Python/numpy環境を固定する。

## 7. パラメータ選定原則

### 7.1 `light_uptake_coef`

「光利用型を弱くしたいから」という理由で選ばない。

以下を確認する:
1. `light_absorption`が個体吸収上限として実際に働く
2. 低能力祖先が一匹だからとセル光全量を使えない
3. 完成光利用型は光単独環境で持続可能
4. 光の広域性は残る
5. 個体当たりEnergyが常に供給上限へ張り付く設計にしない

静止祖先の理論的break-evenが `light_uptake_coef≈1.29` 付近なので、1.0/1.5/2.0で赤字側〜黒字側を跨ぐ。

### 7.2 `chem_vent_flux`

目標:

```text
世界全体: 光より小さい
局所vent: 光より高い供給密度を取り得る
```

16-24を有力候補とするが、Exp08で完成chemical型の人口・stock・利用率を見て確定する。

### 7.3 `chem_uptake`

Exp08では0.5固定。

chemicalを高出力化したいという理由で供給量と吸収係数を同時に上げない。
必要なら次実験で1軸として扱う。

## 8. 判定

### Phase A

- L2が全候補で不成立 → light uptake係数/維持費/光供給の再監査
- L0とL2が全候補でほぼ同じ → light_absorptionがまだ能力差として機能していない疑い
- 係数によって明確なEnergy収支差が出る → V1.4光吸収則は機能

### Phase B

- flux8以上でExp07と同様に成立 → surface則/公平配分変更後もV1.3chemical生態は頑健
- 8だけ不安定、16/24成立 → 恒久defaultを16-24へ上げる根拠
- 24まで不成立 → chemical uptake/維持費等を再監査

## 9. Exp08で結論しないこと

- 光とchemicalのどちらが進化的に優秀か
- 多様性が増えたか
- 動物的進化が始まったか
- chemical祖先bootstrapが解決したか
- 光/chemicalを同時に感じたときの行動選択

## 10. Exp08後

吸収則とdefault供給量が確定したら、次に:

1. 光+chemicalを同じ世界へ戻す前に、異種刺激を原生生物的に比較する走光性/走化性ルールを確定
2. 通常祖先からchemical型へ進める「橋」が光存在下で生じるか診断
3. その後に日照量の低下・時間変動・季節性等を追加
4. エネルギーが不安定になることで移動/探索/死骸/捕食の相対価値が自然に上がるかを見る

動物的行動への直接ボーナスは入れない。
