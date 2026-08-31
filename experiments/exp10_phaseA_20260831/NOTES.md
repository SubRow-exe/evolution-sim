# Exp10 Phase A 実測NOTES — V1.6 temporal biased random walk の校正

実行日: 2026-08-31
実行環境: ローカル (Claude Code remote container / Linux)
commit: `9d75668` の親 `7d5419d` 時点のコード
数値実行環境キー: `linux-x86_64-glibc2.39-py3.12.3-np2.5.2`
規模: 3,900 run（5環境 × 3表現型 × 13組 × 20 seed）、各 2,000 tick / 100 個体
所要: 78分（4並列）
判定: **Green**

解釈の正本は `docs/Exp10_中間報告.md`。条件・判定の正本は `docs/Exp10_実験計画案.md` §4。

## 用語

- **`memory_tau`（短期記憶の時定数）** [tick]
  現在の刺激と比べる過去の重み付け幅。EMA更新率は `alpha = 1 - exp(-1/tau)`。
- **`response_gain`（応答ゲイン）** [無次元]
  `dQ` が曲がり幅へ効く強さ。0なら pure random walk。
- **`turn_factor`（曲がり幅の変調係数）**
  `2 / (1 + exp(gain * dQ))`。1で現行baseline、1未満で直進しやすい。
- **high-Q領域滞在率**
  その表現型の `Q` が上位25%のセルに個体がいた時間の割合。
  面積で定義するので環境・表現型をまたいで直接比較できる。
- **drift**
  集団重心の移動量 [cell]。セル添字が増える向きを正とする。

## 環境（計画 §4.1）

production world へ診断専用の特殊環境を恒久追加しないため、
死亡・繁殖・吸収・生理をすべて止めた**移動専用arena**を別に用意した。

| 環境 | light | chemical | 目的 |
|---|---|---|---|
| K0_uniform | 一定 | 一定 | 偽bias検出 |
| K1_light_Y | +Y勾配 | 0 | 単一刺激 |
| K2_chem_X | 0 | +X勾配 | 単一刺激 |
| K3_orthogonal | +Y勾配 | +X勾配 | 直交 |
| K4_conflict | +Y勾配 | −Y勾配 | 逆向き |

light は 0〜1.2（本番世界の最大セル光量）、chemical は 0〜24.6
（`chemical_stimulus_half` の2倍。中央で応答0.5になり受容器の効く範囲を通る）。

## 事前登録Green条件の判定（計画 §4.6）

| tau | gain | C1 K0 | C2 grad | C3 K3 | C4 K4 | 判定 |
|---:|---:|:--:|:--:|:--:|:--:|:--|
| 3 | 4 | OK | NG | NG | NG | – |
| 3 | 16 | OK | NG | OK | OK | – |
| 3 | 64 | OK | NG | OK | OK | – |
| 3 | 256 | OK | OK | OK | OK | **GREEN** |
| 10 | 4 | OK | NG | NG | NG | – |
| 10 | 16 | OK | NG | OK | OK | – |
| 10 | 64 | OK | OK | OK | OK | **GREEN** |
| 10 | 256 | OK | OK | OK | OK | **GREEN** |
| 30 | 4 | OK | NG | NG | NG | – |
| 30 | 16 | OK | NG | OK | OK | – |
| 30 | 64 | OK | OK | OK | OK | **GREEN** |
| 30 | 256 | OK | OK | OK | OK | **GREEN** |

Green 5/12。条件5（隣接する複数組で成立）もOK
（(10,64)–(10,256) / (30,64)–(30,256) / (10,64)–(30,64) が隣接）。

**先頭10 seedだけで評価しても同じ5組がGreen**で、判定はseed数に頑健だった。

判定の細部（計画に無い部分）は `tools/summarize_exp10.py` に固定してある。

- seed比率: 「10 seed中8以上」= 80%。20 seedでも同じ80%を使う
- 「統計誤差内」(条件1): Welchのt検定で `|t| < 2.0`
- 「隣接」(条件5): 候補列で添字が1違う組

## 最終候補（計画 §4.7）

Green領域から「最小 `response_gain` → 同gainなら最短 `memory_tau`」で機械的に1組。

```text
memory_tau    = 10
response_gain = 64
```

`configs/exp10/phaseA_selection.json` に保存し、
`tools/make_exp10_configs.py` はここからしか読まない（手で選ばない）。

## 主な実測値

### K0（一様刺激）— 偽biasが厳密に無い

drift が **gain によらず完全に同一**（x = −0.06 / y = −0.01、全gain・全表現型）。
一様場では `dQ` が恒等的に0になり `turn_factor = 1` のままなので、
統計的にではなく厳密に一致する。Welch t = 0。

### K1 light-Y / lightspec — high-Q領域滞在率（中央値、tau=10）

| gain | 0 | 4 | 16 | 64 | 256 |
|---|---:|---:|---:|---:|---:|
| high-Q滞在率 | 0.2444 | 0.2472 | 0.2563 | **0.2960** | 0.5732 |
| drift_y [cell] | −0.01 | 0.32 | 1.27 | **5.32** | 16.45 |

gain=64 の改善量は **+5.2 pp** で、事前登録の閾値 +5 pp をわずかに超えて通過した。
gain=16 は +1.2 pp で落ちる。閾値が選別として機能している。

### K4 conflict — specialistが逆方向へ分かれる（tau=10, gain=64）

| 表現型 | drift_y [cell] |
|---|---:|
| lightspec | **+4.29** |
| chemspec | **−5.22** |
| generalist | −0.75 |

light は +Y、chemical は −Y に置いてあるので、期待どおりの符号。
generalist は両方の寄与を受けて中間に留まった。

### K3 orthogonal — generalist が両軸へ同時に偏る（tau=10, gain=64）

```text
drift_x = +3.79 cell   (chemical 方向)
drift_y = +3.07 cell   (light 方向)
```

単一source追従では説明できない、両刺激統合の直接的な証拠になる。

## 既知の計測上の注意

**K0（一様場）の high-Q領域滞在率は全条件で 1.0000 になる。**
`Q` が空間一定なので上位25%の閾値が定数と一致し、全セルが high-Q と判定される。
K0のGreen条件は drift で見るので判定には影響しないが、
**K0のhi_q列は意味を持たない値**として読むこと。

## 保存

- `phaseA.csv` — 3,900 run の集計結果（1 run 1行、25列）
- `meta.json` — 実行条件
- `phaseA_selection.json` — 事前登録規則による選定結果
- `phaseA_summary.txt` — 判定ログ全文
- `figures/` — 集計プロット5枚（`figures/README.md` 参照）

Phase A は移動専用arenaで個体単位の生データを持たない設計なので、
`phaseA.csv` 自体が結果の全量である（外部ストレージへ退避すべき生データは無い）。
再現は `tools/arena_exp10.py` を同一commitで実行すれば得られる。
