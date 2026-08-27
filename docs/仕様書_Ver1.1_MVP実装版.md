# 生物進化シミュレーション 仕様書 Ver.1.1 MVP実装版

本書は「仕様書 Ver.1.0 方針版」を実装可能なレベルまで具体化したものである。
方針版の設計原則（適応度を直接計算しない・結果を直接プログラムしない・物理/生理コストによるトレードオフ）をすべて踏襲する。

対象範囲は方針版 第66節の **最初の実用MVP**（Phase 0〜4 相当の簡易版）。

---

## 1. 単位系と時間

| 概念 | 単位 | 定義 |
|---|---|---|
| 時間 | tick | 固定タイムステップ。1 tick = 1時間単位 |
| 空間 | wu (world unit) | 連続2D座標。世界は 800 × 800 wu |
| エネルギー | E | 内部通貨。外部（光・化学）から流入し、最終的に熱として散逸 |
| 物質 | M (matter) | 身体材料。**世界全体で厳密に保存される**（外部流入なし） |

世代制は採用しない（方針版 第13節）。時間は連続的に進み、全イベントは個体ごとに発生する。

---

## 2. 世界と環境フィールド

- 世界: 800 × 800 wu、境界は壁（個体は外に出られない）
- 環境グリッド: セルサイズ 20 wu → 40 × 40 セル
- 個体位置は連続座標、環境（光・栄養・化学）はセル単位で保持するハイブリッド方式

### 2.1 光（エネルギー流入・フロー型）

- 各セルは毎tick `light_flux` のエネルギーを供給する（蓄積しない。使わなければ消える＝熱散逸）
- 空間勾配（デフォルト: 縦方向勾配）:
  `light_flux(y) = light_max × (0.3 + 0.7 × (1 − y/H))`
  → 北端が明るく南端が暗い。環境の異質性が栄養戦略分化の前提条件となる
- セル内に光利用個体が複数いる場合、`light_absorption × 有効サイズ` に比例して**分配**する
  → 光を巡る空間競争（密度依存の負のフィードバック）が自然発生する

### 2.2 化学エネルギー（ストック型・熱水噴出口）

- ランダムな4地点（噴出口）の周囲半径2セルに化学エネルギーが湧く
- 各対象セルはロジスティック回復: `C += r_chem × C × (1 − C/K_chem)`（C=0を避けるため下限0.5から回復）
- 個体は接触セルから `chemical_absorption × s_eff × uptake` を吸収（ストックが上限）

### 2.3 無機栄養（物質・厳密保存）

- 各セルが栄養ストック `N` を持つ。初期値 2.0/セル（世界合計 3200 M = 事実上の環境収容力）
- **再生しない。** 物質は「無機物 → 生体 → 死骸 → 無機物」の閉じた循環のみで移動する（方針版 第39節）
- 毎tick、隣接セルへ拡散する（係数 `nutrient_diffusion = 0.05` のラプラシアン拡散）
  → 局所枯渇と再供給が空間動態を作る

---

## 3. 遺伝子（Genome）

方針版 第10節の遺伝子リストに、第8節の「外部物質吸収能力」を `nutrient_absorption` として追加した14遺伝子。すべて非負の連続値。

| 遺伝子 | 初期値 | 範囲 | 意味 |
|---|---|---|---|
| body_size | 1.0 | 0.2–10 | 成体サイズ S（目標身体物質量） |
| membrane_strength | 0.5 | 0–5 | 膜強度（防御） |
| movement_power | 0.5 | 0–5 | 運動出力 |
| movement_efficiency | 1.0 | 0.2–5 | 運動効率 |
| sensory_range | 0.4 | 0–5 | 感覚範囲係数 |
| light_absorption | 0.3 | 0–5 | 光利用能力 |
| chemical_absorption | 0.3 | 0–5 | 化学エネルギー利用能力 |
| nutrient_absorption | 0.5 | 0–5 | 無機物質吸収能力 |
| predation_efficiency | 0.05 | 0–5 | 他個体利用（攻撃・摂取）能力 |
| corpse_digestion | 0.2 | 0–5 | 死骸分解能力 |
| repair_rate | 0.3 | 0–5 | 修復能力 |
| damage_resistance | 0.5 | 0–5 | 損傷耐性 |
| reproduction_investment | 0.4 | 0.05–0.9 | 繁殖時に子へ渡すエネルギー割合 |
| mutation_rate | 0.05 | 0.005–0.5 | 突然変異の大きさ σ（自身も進化する） |

### 3.1 突然変異

繁殖時、全遺伝子に対して:

```
g_child = clamp( g_parent × exp(N(0, σ)) + N(0, 0.01 × σ × scale_g) )
```

- 乗算的（対数正規）変異: 値のスケールに依存せず、負値が出ない
- 微小な加算項: 0 に固定された能力が再出現できる余地を残す（scale_g は遺伝子の代表スケール）
- σ = 親の mutation_rate。mutation_rate 自身は固定メタσ (0.1) で乗算的に変異し [0.005, 0.5] にクランプ
- 初期個体群には σ0 = 0.02 の乗算ジッターを与える（初期絶滅率を下げる standing variation）

---

## 4. 個体の状態

```
id, parent_id, lineage_id, generation, birth_tick
x, y, heading
energy E        （上限 E_max = 100 × s_eff）
matter M        （現在の身体物質量。s_eff = M）
damage D        （上限 D_max = 10 × s_eff × (1 + damage_resistance)）
```

- **有効サイズ s_eff = M**（現在の身体物質量そのもの）。半径 = 4 × √s_eff wu（2Dなので面積∝物質量）
- **健全度 φ = max(0.1, 1 − D/D_max)**。速度と全吸収レートに乗算される
  → 損傷蓄積が身体機能低下を招く。老化はこの帰結として創発する（方針版 第20節）

---

## 5. 生理（毎tickのエネルギー・損傷収支）

人工的なペナルティではなく、スケーリング則からコストを導出する（方針版 第22節・原則2）。

### 5.1 エネルギー消費（熱として散逸）

| 項目 | 式 | 根拠 |
|---|---|---|
| 基礎代謝 | 0.3 × s_eff^0.75 | クライバー則（代謝は体サイズの3/4乗） |
| 器官維持 | 0.05 × s_eff × Σ(5つの栄養獲得能力) | 能力は無料ではない |
| 感覚維持 | 0.02 × sensory_range² | 感覚面積∝範囲² |
| 膜維持 | 0.03 × membrane_strength × √s_eff | 膜量∝周長 |
| 耐性維持 | 0.02 × damage_resistance × s_eff | |
| 移動 | 0.05 × m × v² / movement_efficiency | 運動エネルギー則 |
| 攻撃 | 0.2 × predation_efficiency × s_eff /回 | |
| 物質吸収 | 2.0 × 吸収量 | 同化コスト |
| 修復 | 使った分（下記） | |

E ≤ 0 になった時点で死亡（死因: starvation）。

### 5.2 損傷と修復

```
毎tick:  D += 0.02 × s_eff                 （代謝性損傷）
         D += 0.005 × m × v²               （運動性損傷）
         D += 被攻撃時の正味攻撃力          （攻撃損傷）

修復:    spend = min(0.2 × repair_rate × s_eff × φ, E, 必要量)
         D −= 0.5 × spend                   （エネルギー→修復の変換効率 0.5）
```

- D ≥ D_max で死亡（死因: damage。直前に攻撃を受けていれば predation）
- `if age > lifespan: die()` は存在しない。修復投資が損傷発生を上回る系統は原理的に不老になれる（方針版 第20–21節）

### 5.3 移動

```
v_max = 3.0 × movement_power / √m × φ    [wu/tick]
```

出力/質量比から速度が決まる。大型化は速度と維持費を犠牲にする。

---

## 6. 栄養獲得（5経路すべて遺伝子依存）

| 経路 | 得るもの | レート（×φ） |
|---|---|---|
| 光 | E | セル光フラックスを重み `light_absorption × s_eff` で分配 |
| 化学 | E | 0.5 × chemical_absorption × s_eff（セルストック上限） |
| 無機栄養 | M | 0.05 × nutrient_absorption × s_eff（セルストック上限、吸収コストE併発） |
| 捕食 | E + M | 下記 6.1 |
| 死骸 | E + M | 0.5 × corpse_digestion × s_eff（死骸残量上限） |

同化効率: 捕食・死骸摂取の物質同化率は 0.7。**残り0.3は排泄物としてセルの無機栄養に戻る**（物質保存）。

### 6.1 捕食

接触時（距離 < r₁ + r₂）:

```
attack  = 2.0 × predation_efficiency_攻 × s_攻 × φ_攻
defense = 2.0 × membrane_strength_防 × s_防
net     = attack − defense
if net > 0:
    防御側:  D += net
    攻撃側:  E += min(E_防, 0.5×net) × 0.7
             M += min(M_防, 0.05×net) × 0.7   （残りは排泄→栄養フィールド）
    攻撃コスト: 0.2 × predation_efficiency × s_攻
```

「捕食者」というクラスは存在しない。攻撃・膜・移動・感覚の遺伝子の組み合わせの結果として捕食的系統が（出るなら）出る。膜が十分厚ければ攻撃は完全に無効化される。

---

## 7. 繁殖（無性生殖）

条件: `E ≥ 0.6 × E_max` かつ `M ≥ 0.8 × body_size`

```
出産オーバーヘッド: 2.0 E を燃焼
子への譲渡:  E_child = reproduction_investment × (E − overhead)
             M_child = 0.35 × M            （親から物質を譲渡＝保存）
子:          親の隣に出生、Genomeは変異コピー、generation+1、lineage継承
```

reproduction_investment が高い系統は「少数の子に厚く投資」、低い系統は「多産・薄投資」となり、r/K戦略の分化余地を作る。

---

## 8. 死亡と死骸

死因: starvation（E≤0）/ damage（D≥D_max）/ predation（攻撃起因のdamage死）/ disaster

死亡個体は死骸となる:

```
Corpse: 位置、M_c =個体のM、E_c = 個体の残E
毎tick: M_c の 0.5% → セル無機栄養（分解）
        E_c の 1% → 熱散逸
        M_c < 0.05 で消滅（残Mは栄養へ）
```

死骸は分解者戦略の資源であり、物質循環の要（方針版 第38–39節)。

---

## 9. 行動（MVP版・意図的に単純）

方針版 第42節の通り、MVPでは「検出→接近、なければランダム探索」のみ。NN進化はPhase 7。

```
1. E ≥ 0.85×E_max かつ M ≥ body_size → 待機（何も必要ない）
2. 感覚半径 R = 25 × sensory_range 内の刺激をスコア化:
     栄養セル:   nutrient_absorption × ストック
     化学セル:   chemical_absorption × ストック
     光セル:     light_absorption × フラックス
     死骸:       corpse_digestion × M_c
     他個体:     predation_efficiency × s_other
3. 最高スコアの対象へ v_max で移動（現在地が最良なら停止して吸収）
4. 刺激なし → ランダムウォーク（進行方向にノイズ、v_max×0.6）
```

**既知の設計バイアス**: 刺激タイプ間のスコア正規化は設計者の裁量が入っている。Phase 7（神経進化）でこの手書きルール自体を置き換える。

---

## 10. 災害

- ランダム災害（キー D / CLI）: 遺伝子を参照せず個体の90%をランダム死亡させる（死因: disaster、死骸化）
- 目的: ボトルネック効果・遺伝的浮動の観察（方針版 第33節）

---

## 11. 再現性

- 乱数は `numpy.random.Generator(PCG64(seed))` **1個のみ**。`random` モジュール禁止
- 個体処理はリスト順（挿入順）で決定的。set/dict順序への依存禁止
- 並列化なし。壁時計時間への依存なし
- 実行ごとに `runs/<run_id>/config.json` に**全設定値 + seed + コードバージョン**を保存
- 自動テストで同一seed 2回実行の完全一致を検証

---

## 12. データ記録

```
runs/<run_id>/
├─ config.json            全設定・seed
├─ events.csv             出生・死亡の全イベント（系統樹再構築可能）
│    birth: tick, id, parent_id, lineage_id, generation
│    death: tick, id, cause, age
├─ stats.csv              20 tickごとの集計統計
│    個体数 / 累積出生・死因別死亡 / 総エネルギー / 総生体量 /
│    栄養・化学・死骸残量 / 平均・最高年齢 / 系統数 /
│    全14遺伝子の平均と分散
├─ snapshots/snap_<tick>.csv   2000 tickごとの全個体スナップショット
│    id, lineage, generation, age, x, y, E, M, D, 全遺伝子
└─ plots/                 グラフ出力（Gキー / tools）
```

平均値だけに依存しない（方針版 第48節）: 分散を常時記録し、スナップショットからヒストグラムを生成する。

---

## 13. 保存則の検証（実装上の最重要インバリアント）

毎tick、シミュレーションはエネルギー・物質台帳を更新し、自動テストで検証する:

- **物質**: `Σ栄養フィールド + Σ個体M + Σ死骸M = 一定`（誤差 < 1e-6）
- **エネルギー**: `流入(光+化学再生) − 散逸(全コスト+死骸減衰) = Δ(個体E + 死骸E + 化学ストック)`

保存則の破れは進化結果を静かに無意味にするため、常時テストする（原則6・7の実装）。

---

## 14. 可視化

### 14.1 リアルタイム表示（pygame-ce）

- 背景: 光勾配（明度）+ 無機栄養（緑）+ 化学（紫）
- 個体: 円（半径=実サイズ）。色は遺伝子から生成 —
  **R=捕食能力, G=光利用能力, B=死骸分解能力**。役割の分化が色の分化として見える
- 死骸: 灰色
- HUD: tick、個体数、系統数、速度倍率、直近の死因内訳

### 14.2 キー操作（方針版 第57節）

```
SPACE = Pause      1/2/3 = x1/x10/x100
G = グラフ生成（plots/へPNG保存）
D = 災害（90%ランダム死亡）
R = リセット（新seed・記録上明示）
ESC = 終了
```

### 14.3 グラフ（Matplotlib）

- 個体数・出生・死因別死亡の時系列
- 全遺伝子平均の時系列（分散帯付き）＋災害イベントのマーカー
- エネルギー・物質収支の時系列
- 最新スナップショットの遺伝子ヒストグラム

---

## 15. CLI

```
uv run python main.py                          # GUI起動
uv run python main.py --headless --ticks 100000 --seed 42
uv run python main.py --config myconfig.json --out runs/
uv run python tools/plot_run.py runs/<run_id>  # 事後グラフ生成
```

描画OFFヘッドレスモードはPhase 0から必須機能（超長期実験のため）。

---

## 16. ディレクトリ構成

```
evolution_sim/
├─ main.py                CLI・エントリポイント
├─ evosim/
│   ├─ config.py          全パラメータ（dataclass、JSON入出力）
│   ├─ genome.py          遺伝子・突然変異
│   ├─ organism.py        個体状態
│   ├─ world.py           環境フィールド（光・栄養・化学）
│   ├─ corpse.py          死骸
│   ├─ behavior.py        感覚と行動決定
│   ├─ physiology.py      エネルギー収支・損傷・修復
│   ├─ simulation.py      メインループ・相互作用・繁殖・死亡・台帳
│   ├─ disasters.py       災害
│   ├─ recorder.py        events/stats/snapshots記録
│   └─ render/
│       ├─ renderer.py    pygame-ce ビューア
│       └─ plots.py       matplotlibグラフ
├─ tools/plot_run.py
├─ tests/
│   ├─ test_determinism.py    同一seed完全再現
│   ├─ test_conservation.py   物質・エネルギー保存
│   └─ test_smoke.py          既定設定で個体群が即死しない
└─ docs/（本書）
```

---

## 17. 検証実験（実装完了の定義）

| 実験 | 内容 | 合格基準 |
|---|---|---|
| Exp 0 | 突然変異OFF・安定環境 | 5,000 tickで絶滅も爆発もしない |
| Exp 1 | 既定設定・安定環境 | 20,000 tickで個体群維持、遺伝子平均が動く |
| Exp 4 | 途中で90%災害 | 個体群回復、系統数減少、分散変化が記録される |
| テスト | pytest 全通過 | 決定性・保存則・スモーク |

Exp 2/3/5（資源減少・温度・超長期）はMVP完成後にconfig変更のみで実施可能な状態にする。

---

## 18. MVP以降（方針版のPhaseへの接続）

- 温度フィールド（Phase 2）: world.py にフィールド追加、physiology.py に熱損失項を追加するだけの構造にしてある
- Pymunk物理身体（Phase 5–6）: organism の「s_eff→半径」写像を Body クラスへ差し替える。**注意: Python+Pymunkで数千個体は不可能。Phase 5着手時に物理演算の間引き・部分適用・高速化(Rust拡張等)を再検討する**
- 神経進化（Phase 7）: behavior.py の手書きルールをNNへ置換する差し替え点として設計
- 有性生殖（第12節）: genome.py の mutate と simulation の繁殖処理に閉じている
