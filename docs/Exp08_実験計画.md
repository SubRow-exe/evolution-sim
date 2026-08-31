# Exp08 実験計画 — V1.4 吸収則の校正

更新: 2026-08-31
状態: **事前条件確定 / V1.4実装後に実行**

正本:
- `docs/V1.4_一次エネルギー吸収仕様.md`
- 本書
- `experiments/exp07_actions_20260830_160556/NOTES.md`
- `docs/Exp07_結果考察.md`

## 1. 目的

Exp08は光とchemicalの「進化競争」を調べる実験ではない。

V1.4で生物側の一次Energy/資源吸収則を変更した直後に、以下を校正する。

1. `light_absorption`が実際の個体吸収上限として機能するか
2. `matter^(2/3)` の有効表面積則が意図どおり作用するか
3. light/chemical/nutrientの不足時配分が個体処理順に依存しないか
4. V1.4後も完成光型・完成chemical型の単独生態が成立可能か
5. `light_uptake_coef`の恒久default候補を絞る
6. `chem_vent_flux=8/16/24`でchemical単独生態の出力・人口・stockを比較する
7. 光とchemicalの個体吸収ceilingの相対スケールを定量化する

Exp08では光とchemicalを同居させない。

## 2. Exp08で変更しないもの

- 初期ゲノムの恒久値
- mutation rule
- reproduction
- basic metabolic cost / organ upkeep
- movement/sensoryの基本思想
- `chem_uptake=0.5`
- n_vents=4
- vent_radius_cells=2
- chem_loss_frac=0.10
- nutrient world total
- 日照時間変動
- corpse/predationのルールそのもの

V1.4のtick順変更によりcorpse/predationがpost-move hashを見る副作用はあるが、捕食強度等を追加調整しない。

## 3. Phase 0 — 決定論ベンチ

本番run前にseed依存しない診断スクリプト/テストを用意する。

### 3.1 surface scaling

matter:

```text
0.5 / 0.8 / 1.0 / 2.0 / 4.0 / 8.0
```

確認:

```text
A_eff = matter^(2/3)
matter 1 → A_eff 1
matter 8 → A_eff 4
```

### 3.2 光の収支

`light_absorption`:

```text
0.3 / 1.0 / 2.0 / 5.0
```

`light_uptake_coef`:

```text
1.0 / 1.5 / 2.0 / 3.0 / 4.0
```

各matterについて以下を表出力する。

- 個体最大light demand/tick
- セル供給上限との関係
- 現行維持費/tick
- 代謝損傷修復を含む参考net Energy/tick
- Energy容量上限
- 現行初期Energyと繁殖閾値

注意:
- 単純静止break-evenは係数≈1.29
- 修復まで含む実効break-evenは概ね1.4付近
- ただし現行祖先は初期Energyを持ち、開始時点で繁殖可能な場合がある
- よってcoef1.0を「必ず即絶滅」とは事前断定しない

### 3.3 chemicalの収支

`chemical_absorption`:

```text
0.3 / 1.0 / 2.0 / 5.0
```

`chem_uptake=0.5`固定。

光と同じmatterについて:
- 最大chemical demand/tick
- 維持費との差
- absorption=2 / 5での個体ceiling

を出す。

**同じmatter・同じabsorption値でlight/chemical双方のceilingを同じ表に併記する。**

### 3.4 密度競争

同一セルに:

```text
1 / 5 / 20 / 100 個体
```

を置き、light/chemical/nutrientで:
- 供給十分
- 供給不足

の双方を確認する。

要件:
- 個体順をreverse/shuffleしても同一状態個体の配分比が不変
- shuffleはSimulation.rngを消費しない別RNG
- 総取得=`min(供給,総需要)`
- nutrientは同化EnergyとMatter余地を含む事前demandを超えない

### 3.5 Phase 0の役割

Phase 0は数式・実装確認であり進化runの結果ではない。

本書に固定したPhase A/Bの条件はPhase0を見て同一Exp08内で変更しない。実装バグが見つかった場合のみ修正してPhase0を再実行し、本番前にGreenにする。

## 4. Phase A — 光単独

### 4.1 世界

```text
light_pattern = vertical（V1.1互換）
chem_vent_flux = 0.0
n_vents = 4 維持
```

`n_vents=0`にはしない。vent生成に伴う乱数消費を維持するため。

### 4.2 L0 — 低光利用能力固定

```text
通常祖先
light_absorption≈0.3 を固定
```

`light_uptake_coef`:

```text
1.0 / 1.5 / 2.0 / 3.0 / 4.0
```

各10 seed。

目的:
- 低い`light_absorption`が本当に個体吸収上限として機能するか
- 赤字側〜十分黒字側まで広く跨いで、生態成立と人口動態を校正する
- 1.0は負の対照候補、1.5はbreak-even近傍、3/4は高出力側

```text
5 coef × 10 seed = 50 run
```

### 4.3 L2 — 完成光型positive control

```text
light_absorption=2.0固定
light_uptake_coef=2.0固定
```

10 seed。

理由:
- matter≈0.8ではcoef1.0の時点でもabsorption2.0のdemandが多くのセルで光供給上限を超える
- coefを複数振っても供給律速で判別力が低い
- L2は「V1.4後も完成光型の生態が成立するか」のpositive controlとして1水準で十分

```text
10 run
```

### 4.4 Phase A規模

```text
L0 50 run
L2 10 run
合計60 run
60,000 tick
```

### 4.5 評価

- 生存率 / extinction tick
- population / biomass
- light uptake/tick
- 世界光供給に対する利用率
- unused light
- mean matter / body_size
- net Energy budget
- 明暗帯別population
- initial transientと後半population傾向

V1.4では光利用率がV1.3以前より大幅低下しても異常ではない。低能力個体が使えない光を未利用として捨てるのが新仕様の目的だからである。

break-even近傍条件は60k時点の生存/絶滅だけでなくpopulation推移を読む。

## 5. Phase B — chemical単独

### 5.1 条件

```text
light = 0
chemical_absorption=2.0固定
初期配置 = vent
chem_uptake=0.5固定
chem_vent_flux = 8 / 16 / 24 E/tick/vent
```

各10 seed。

```text
3 flux × 10 seed = 30 run
60,000 tick
```

### 5.2 3水準の意味

- 8: Exp07で成立したV1.3基準
- 16: 典型13セルventで約1.23 E/tick/cell
- 24: 約1.85 E/tick/cell

16/24を候補とするのは「flux8で不安定になるはずだから」ではない。

設計目標:

```text
世界総量では光より小さい
vent近傍では光帯と同等〜より高い局所供給密度
```

を作るための事前候補である。

### 5.3 評価

- 生存率 / population / biomass
- chemical source利用率
- stock
- environmental loss
- vent滞在率
- body_size / matter
- 1個体当たりchemical uptake
- demand ceilingに張り付く頻度

通常祖先bootstrapは再実行しない。

## 6. 総規模

```text
Phase A: 60 run
Phase B: 30 run
合計: 90 run × 60,000 tick
+ Phase0決定論ベンチ
```

旧案と総run数は同じだが、L2の冗長20 runをL0の広い係数探索へ振り替える。

## 7. パラメータ選定原則

### 7.1 `light_uptake_coef`

特定結果を作るために選ばない。

見るもの:
1. `light_absorption`が吸収上限として機能
2. L0で係数に応じたEnergy収支差が出る
3. L2 positive controlが成立
4. 広域光という性格を維持
5. 高能力でも全セルで常に供給上限へ張り付く世界にしない

Exp08終了後に恒久defaultを決める。

### 7.2 `chem_vent_flux`

16〜24を有力default候補とするが、単純な生存率だけで決めない。

- 局所供給密度
- population
- source利用率
- stock残量
- 個体吸収ceiling

を合わせて読む。

### 7.3 `chem_uptake`

Exp08では0.5固定。

`light_uptake_coef`と同種の「能力→実吸収速度」の変換係数であることを明記する。

chemical_absorption=5なら現行0.5でもmatter0.8で約2.15 E/tickの潜在ceilingがあり、光明部最大約1.2を超え得る。したがって「chemicalを局所高出力にしたい」という理由だけでExp08前に上げない。

Exp08後もchemical側の個体出力が不十分なら、次実験で`chem_uptake`を独立1軸として扱う。

## 8. 判定

### Phase A

- L2不成立 → light供給/吸収係数/維持費/実装を再監査
- L0が係数にほぼ非感受 → `light_absorption`またはdemand実装が機能していない疑い
- L0で係数に応じて赤字〜黒字の人口動態差 → 新光吸収則が機能
- coef1.0の一時生存は初期Energy/初期繁殖の影響を考慮し、長期trendで読む

### Phase B

- 8/16/24で成立 → V1.3chemical生態はsurface則/公平配分後も頑健
- fluxによってpopulation/stock/利用率が系統的に変化 → default校正に利用
- 24まで不成立 → `chem_uptake`/維持費/局所初期密度を再監査

## 9. 実行前停止条件

本番前に以下がGreenであること。

1. `v1.3-final`保存済み
2. V1.4コード実装済み
3. effective_surface unit test
4. light/chemical/nutrient公平配分test
5. nutrient同化Energy非負 / Matter保存
6. Energy台帳保存
7. post-moveセル参照test
8. list順不変test
9. V1.4 golden/CI基準ref設定
10. Phase0全項目Green

実装不具合のみ本番前に修正する。Phase0の算術結果を見て本書の実験条件を変更しない。

## 10. Exp08では結論しない

- 光とchemicalの進化的優劣
- chemical祖先bootstrap
- 多様性
- 動物的進化
- 日照変動への適応
- 光とchemicalを同時に感じた際の行動選択

## 11. Exp08後

1. `light_uptake_coef`と`chem_vent_flux`の恒久defaultを確定
2. 必要なら`chem_uptake`を独立1軸で追加診断
3. 光+chemical混合前に、未来予測を使わない原生生物的な異種刺激の無次元比較則を確定
4. 光存在下で通常祖先からchemical経路への進化上の橋が成立するか診断
5. その後、日照量低下・時間変動・季節性等を追加
6. 環境ストレスにより移動・探索・死骸利用・捕食の相対価値が自然に上がるか観察

動物的行動への直接ボーナスは入れない。
