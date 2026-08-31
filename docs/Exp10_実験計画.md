# Exp10 実験計画 — V1.6 temporal biased random walk 診断・校正

更新: 2026-08-31
状態: **人間判断済み / 実装・実行待ち**
実装・実行担当: **Claude Code または Codex**

正本:
- `docs/V1.6_行動則仕様.md`
- `docs/V1.6_Exp10_レビュー.md`
- `docs/Exp09_結果考察.md`

## 1. 目的

V1.6の行動則が、周囲の最良セルを直接探索せず、**現在位置で感じるlight / chemicalの時間変化だけから自然なbiased random walkを生むか**を検証する。

Exp10は進化実験ではない。まず行動則そのものを軽量synthetic arenaで校正し、その後full simulationで生態を破壊しないことまで確認する。

## 2. 検証する行動則

```text
連続座標でlight / chemicalを補間して知覚
↓
無次元responseへ変換
↓
能力加重平均でQを算出
↓
短期記憶との差 ΔQ を算出
↓
ΔQ > 0 : random walkの曲がりを弱める
ΔQ < 0 : random walkの曲がりを強める
```

`response_gain = 0` を pure random walk control とする。

現行V1.5 WTAは、実測上ほぼ固着しているためExp10の主性能比較対象にはしない。必要な回帰・参考診断に限る。

## 3. Phase 0 — 実装停止条件

長時間実験前に以下を全件Greenにする。

1. light / chemical双線形補間がセル中心で元field値と一致
2. セル境界で知覚値が不連続にならない
3. 知覚補間を導入しても吸収量・field更新式はV1.5から変わらない
4. `0 <= Q < 1`
5. 全abilityを同率で2倍してもQ不変
6. ability 0の刺激はQへ寄与しない
7. 初回 `Q_memory=Q_now`, `ΔQ=0`
8. EMA memory更新が仕様式どおり
9. `ΔQ=0` で `sigma_eff=wander_turn_sigma`
10. `ΔQ>0` で曲がりが弱く、`ΔQ<0` で強い
11. `response_gain=0` でbaseline random walkと同seed・同条件の軌跡が完全一致
12. 一次EnergyのWTAターゲティングがV1.6経路で使われない
13. 観測追加がRNG・行動分岐へ影響しない
14. Energy / Matter保存、数値健全性
15. V1.6内部のseed決定論

1件でも失敗したらPhase Aへ進まない。

## 4. Phase A — synthetic arenaによる高速校正

通常の生態simulationではなく、死亡・繁殖・Energy/Matter収支などを切った**移動専用診断環境**を使う。production worldへ不要な特殊環境を恒久追加しない。

### 4.1 環境

- **K0 uniform**: light / chemicalとも空間一定。偽bias検出
- **K1 light-Y**: lightのみY方向勾配
- **K2 chemical-X**: chemicalのみX方向勾配
- **K3 orthogonal**: lightは+Y、chemicalは+X
- **K4 conflict**: lightは+Y、chemicalは-Y

### 4.2 固定表現型

Exp09との連続性を持たせる。

- light specialist: light 2.0 / chemical 0.3
- chemical specialist: light 0.3 / chemical 2.0
- generalist: light 1.0 / chemical 1.0

他の刺激能力は診断上0または無効化し、一次Energy行動だけを見る。

### 4.3 パラメータ候補

```text
memory_tau    = 3 / 10 / 30
response_gain = 4 / 16 / 64 / 256
```

計12組。加えて `response_gain=0` をrandom controlとする。

### 4.4 seed

最低10 seed。
synthetic arenaは軽量なので、実装コストが低ければ20 seedまで増やしてよい。ただしパラメータ軸そのものは事後追加しない。

### 4.5 主観測

- `delta_q`
- light / chemicalのΔQ寄与
- `sigma_eff`
- 平均移動方向 / 集団重心drift
- high-Q領域滞在率
- 軌跡の直進性
- K3でのX/Y両軸drift

### 4.6 Phase A Green

最低条件:

1. **K0**: gain>0でも方向driftなし。gain=0との差は統計誤差内
2. **K1/K2**: 対応表現型でrandom controlよりhigh-Q領域滞在率が
   - 10 seed中8 seed以上で改善
   - 改善量中央値 +5 percentage points以上
3. **K3 generalist**: X/Yの両方向が期待符号となるseedが10中8以上
4. **K4**: light specialistとchemical specialistが期待する逆方向へ偏り、generalistは両寄与を受ける
5. Greenが単独1点ではなく、少なくとも隣接する複数パラメータ組で成立

### 4.7 default候補の選び方

結果を見て恣意的に最良値を選ばない。

Green領域の中から:

1. **最小response_gain**
2. 同gainなら**最短memory_tau**

の順で最終候補を1組選ぶ。

「効く中で最も弱い変更」を採る。

## 5. Phase B — full simulation生態検証

Phase Aで選ばれた**1候補だけ**を通常simulationへ持ち込む。

### 5.1 比較

- control: `response_gain=0` pure random walk
- treatment: Phase A選定 temporal sensing

### 5.2 条件

- B1 light-only / light specialist
- B2 chemical-only / chemical specialist
- B3 mixed / light specialist
- B4 mixed / chemical specialist
- B5 mixed / generalist

固定表現型を基本とし、進化はOFF。

### 5.3 実行規模

```text
5条件 × 2行動則 × 20 seed × 10,000 tick
= 200 run
```

まずここまでを必須実行とする。

### 5.4 主観測

- 生存 / population
- high-Q領域滞在率
- light / chemical Energy flow
- 平均移動量
- Q / ΔQ / sigma_eff
- vent滞在率
- vent中心からの距離帯別:
  - ΔQ_light
  - ΔQ_chemical
  - sigma_eff
  - 滞在率
  - Energy取得

距離帯は少なくとも `0–1 / 1–2 / 2–4 / 4+ cell` 相当で層別する。

### 5.5 重要停止条件 — chemical-only

V1.6では定位保持を失うため、chemical-only生態を壊さないことを必須条件とする。

B2 treatmentで:

```text
20 seed中18 seed以上が10,000 tickまで生存
```

を最低条件とする。

これを満たさない場合、temporal sensingの局所行動がPhase Aで正しくてもV1.6 default化は停止し、世界スケール・移動則の不整合として再検討する。

## 6. Phase C — 残り時間を使った長時間頑健性確認

Phase A/BがGreenの場合のみ実施する。

対象:

- light-only
- chemical-only
- mixed generalist

比較:

- gain=0 control
- temporal treatment

優先規模:

```text
3条件 × 2行動則 × 20 seed × 30,000 tick
= 120 run
```

計算時間に十分余裕がある場合のみ、**新しいパラメータ条件を増やすのではなく**、同じ最終候補について最大50,000 tickまで延長する。

目的は10kでは見えない遅い生態崩壊・極端な分布偏り・移動コストの副作用を検出すること。

## 7. 10時間計算枠の使い方

計算時間を埋めること自体を目的にしない。優先順位は固定する。

1. Phase 0を完全に通す
2. 軽量Phase Aを十分なseedで実行
3. 最終1候補へ絞る
4. Phase B 200 runを必須実行
5. 残り時間をPhase Cの**seed数・tick延長**へ使う

パラメータ候補を結果を見て追加することは禁止する。

Exp09実績（5,000 tick run 約2.2 core-min）から、Phase Bは十分現実的な規模であり、Phase Aを軽量化したことで10時間枠の大部分を本物のfull simulationと長時間確認へ配分できる設計とする。

## 8. Exp10最終Green条件

1. Phase 0全件Green
2. 一様環境で偽biasなし
3. 単一刺激gradientでrandomより高Q領域へ有意な偏り
4. K3でgeneralistがlight / chemicalを同時統合
5. 効果が単一パラメータ点だけに依存しない
6. B2 chemical-onlyが20 seed中18以上生存
7. V1.5の吸収・Energy/Matter物理を壊していない
8. V1.6内部seed決定論Green
9. Phase Cを実施した場合、長時間で新たな致命的崩壊がない

## 9. Exp10で結論しないこと

- temporal sensing自体が進化するか
- specialist / generalistの長期進化的優劣
- 感覚器コスト
- spatial / directional sensingの進化
- nutrient / corpse / predationの行動則妥当性
- 全刺激統合

これらはExp10後の独立軸とする。

## 10. 結果保存

従来方針に従い、正式結果ではGitHubへ最低限:

- 結果考察
- NOTES
- Phase Aパラメータ図
- trajectory / drift図
- high-Q滞在率比較
- vent距離帯別図
- 代表GIF/PNG

を保存する。全生データはActions artifact / Google Driveへ保存する。

## 11. 実装・実行担当への注意

コード編集、テスト、workflow作成、Exp10実行は Claude Code または Codex が行う。

本書は人間判断済みの事前登録である。結果確認後にパラメータ候補・Green閾値・条件を都合よく追加変更しない。実装上どうしても成立しない条件が判明した場合は、実験を走らせる前に理由を文書化し、人間判断を求める。
