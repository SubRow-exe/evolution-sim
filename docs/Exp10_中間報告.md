# Exp10 中間報告 — Phase A完了（Green）と Phase B の前提崩れ

更新: 2026-09-01
状態: **Phase A完了 / Phase B を5バッチへ分割して正式実行中（バッチ1完了）**

正本:
- 条件・判定: `docs/Exp10_実験計画案.md`
- モデル: `docs/V1.6_行動則設計案.md`
- 実測: `experiments/exp10_phaseA_20260831/NOTES.md`
- 手順: `docs/Exp10_実行手順.md`

本書は計画 §11 の

> 実装上どうしても成立しない条件が判明した場合は、実験を走らせる前に理由を
> 文書化し、人間判断を求める。

に従って書いている。**Phase B本番の条件を独断で変更していない。**

---

## 1. ここまでにやったこと

1. V1.6 を仕様どおり実装（commit `e15ee67`）
2. CI結果不変性の基準refを V1.6 実装commitへ移行（`64134ba`）
3. Phase 0（計画 §3 の15項目）を32件のテストとして実装し全通過
4. Phase A（3,900 run）を実行 → **Green**、事前登録規則で `tau=10` / `gain=64` を選定
5. Phase B本番（200 run）に着手 → **計算量の前提が実測で崩れたため停止**

## 2. Phase A — Green

詳細は `experiments/exp10_phaseA_20260831/NOTES.md`。

12組中5組がGreen、条件5（隣接する複数組で成立）もOK。
先頭10 seedだけで評価しても同じ5組がGreenで、判定はseed数に頑健だった。

§4.7（最小 `response_gain` → 同gainなら最短 `memory_tau`）が機械的に選んだ結果:

```text
memory_tau    = 10
response_gain = 64
```

![Fig.5 パラメータスイープ](../experiments/exp10_phaseA_20260831/figures/fig5_param_sweep.png)

事前登録の閾値 +5 pp が選別として機能している。K1/lightspec では
gain=16 が +1.2 pp で落ち、gain=64 が **+5.2 pp** でぎりぎり通過する。

![Fig.3 high-Q滞在率](../experiments/exp10_phaseA_20260831/figures/fig3_hi_q_residence.png)

### 偽biasが「厳密に」無いこと

K0（一様刺激）の drift は **gain によらず完全に同一**（x = −0.06 / y = −0.01）。
一様場では `dQ` が恒等的に0になり `turn_factor = 1` のままなので、
統計的にではなく厳密に一致する（Welch t = 0）。

### 複数刺激の統合

K3（直交）で generalist が両軸へ同時に偏った（drift_x = +3.79 / drift_y = +3.07 cell）。
K4（逆向き）では lightspec が +4.29、chemspec が −5.22 と期待どおり反対方向へ分かれ、
generalist は中間（−0.75）に留まった。

![Fig.4 K3/K4の空間分布](../experiments/exp10_phaseA_20260831/figures/fig4_spatial_K3_K4.png)

---

## 3. Phase B で崩れた前提 — 計算量

計画 §7 は

> Exp09実績（5,000 tick run 約2.2 core-min）から、Phase Bは十分現実的な規模

としているが、**この前提はV1.6では成り立たない**ことが実測で分かった。

### 実測（b1_light_only_lightspec_control, seed1）

Matterは全期間 **3280.00 で厳密に保存**されており、バグではない。

| tick | population | mean_body_size | 光利用率 |
|---:|---:|---:|---:|
| 20 | 196 | 0.996 | – |
| 1,620 | 867 | 0.941 | – |
| 4,020 | 1,670 | 0.681 | – |
| 6,420 | 4,878 | 0.297 | – |
| 8,080 | 6,511 | 0.226 | **65.5%** |

- **個体数が V1.5 の約300から約6,500へ、20倍以上**
- 光の利用率が **11.7%（Exp09 / V1.5）→ 65.5%（V1.6）**
- `mean_body_size` が 0.996 → 0.226 へ縮小

### なぜこうなるか

V1.5では `sensory_range` が `cell_size` を下回るため個体が事実上固着しており、
子は親の近くに置かれて同じセルの光を奪い合っていた（Exp09で移動量ゼロ）。

V1.6で動けるようになった結果、集団が光場全体へ広がって競合が緩み、
**世界の光をはるかに多く使えるようになった**。Matterは保存されているので、
増えた分は身体の小型化（同じMatter量でより多くの個体）として現れている。

小型化そのものは AGENTS.md「小型化の判断」が V1.4 の自然な選択圧として
既に許容を決めた現象で、V1.6 はそれを増幅した形になる。

### 計算量への影響

個体数20倍のため 1 run が **約40分**（10,000 tick）になり、

```text
Phase B 200 run = 約127 core-hour
  ローカル4並列  : 約31時間
  Actions 20並列 : 約7時間
```

計画 §7 の見積もり（Exp09基準）から**約18倍**ずれている。

---

## 4. Phase B を Actions で回せない技術的事情

`workflow_dispatch` は workflow ファイルが **default branch に存在しないと起動できない**。
`.github/workflows/exp10.yml` は現在 `claude/pilot-execution-plan-52spjd` に
しかないため、API から起動すると 404 が返る（実際に確認済み）。

ローカル実行用に `tools/run_exp10_phaseB.py` を用意してある
（workflowと同じ条件・同じ停止条件を同じ順で回す）が、
ローカルではDriveへの生データ転送ができない（rclone設定はGitHub secret）。

---

## 5. b2 chemical-only の暫定観測（**確定値ではない**）

Phase Bを止める前に、§5.5 の重要停止条件に直結する b2 だけ先に走らせた。
chemical-only は個体数が小さく（15〜134）runが速いため、ここまで進んでいる。

**treatment は 20 seed中12しか走っておらず、§5.5 の判定には使えない。**
以下はあくまで途中経過である。

| | control (gain=0) | treatment (gain=64) |
|---|---|---|
| 10,000 tick完走 | 18 / 20 | 8 / 12（残り8 seed未実行） |
| 絶滅 | **2 seed**（s2 が tick 5,409、s6 が 5,394 で pop=0） | 0 |
| 完走runの最終pop | 中央値 52（15〜134） | 中央値 106（82〜117） |
| vent滞在率（全期間平均） | 0.782 | 0.846 |
| 平均移動量 [wu/tick] | 0.575 | 0.692 |

生データの要約は `experiments/exp10_phaseB_partial_20260831/phaseB_b2_partial.csv`。

### 暫定的に言えそうなこと

`docs/V1.6_Exp10_レビュー.md` B-4 で私が挙げた懸念は

> V1.6は定位保持を失うため、vent滞在に依存する chemical-only 生態が
> 壊れないかが最大の懸念

だったが、**途中経過は逆を示している**。temporal sensing 側の方が
vent滞在率が高く（0.846 vs 0.782）、個体数のばらつきも小さく、絶滅が出ていない。
曲がり幅の変調が、pure random walk より vent 近傍に留まらせている可能性がある。

ただし **treatment が 12 seed しか無いので、これを結論にしてはいけない。**
§5.5 の「20 seed中18以上」の判定には残り8 seedの実行が必要である。

---

## 6. 判明した計測上の問題 — high-Q領域滞在率の退化

`hi_q_frac` は「その表現型の `Q` が上位25%のセル」に居た割合で定義した。
しかし **Qの最小値を25%を超えるセルが共有する環境では退化して常に1.0になる。**

- **K0（一様刺激）**: `Q` が空間一定 → 閾値＝定数 → 全セルがhigh-Q
- **b2（chemical-only）**: 光0なので `Q` は chemical のみで決まり、
  vent以外（96.75%のセル）が `Q=0` → 上位25%の閾値が0 → 全セルがhigh-Q

そのため計画 §8-3

> 単一刺激gradientでrandomより高Q領域へ有意な偏り

は、**b2 では現在の指標で評価できない**。b2 では `vent_cell_frac`
（control 0.782 / treatment 0.846）が意味のある空間指標になる。

K0 のGreen条件は drift で見ているのでPhase Aの判定には影響していない。

これも結果を見てから指標を作り替えるのは避けるべきなので、
**扱いを人間判断で決めていただきたい。**

---

## 6.5 Phase B の実行単位分割（人間判断で決定・2026-09-01）

V1.6による個体数増加で当初の計算量見積もりが崩れたため、
**科学条件を一切変更せず、実行単位だけ 40 run × 5バッチへ分割**した。

分割は計算負荷・Artifact回収・collect処理を安全にするためだけの措置で、
最終解析では5バッチを合わせて**元の計画どおり1つのPhase B（200 run）**として扱う。

```text
バッチ1  B2 chemical-only / chemical specialist   control 20 + treatment 20
バッチ2  B1 light-only    / light specialist      control 20 + treatment 20
バッチ3  B3 mixed         / light specialist      control 20 + treatment 20
バッチ4  B4 mixed         / chemical specialist   control 20 + treatment 20
バッチ5  B5 mixed         / generalist            control 20 + treatment 20
```

変更していないもの: `response_gain=64` / `memory_tau=10`（Phase A選定値）、
`fixed_genes`、`body_size`、tick数10,000、seed 1-20、5条件×2行動則の構成。
`body_size` の小型化と個体数増加は現行世界ルールから生じた結果としてそのまま許容する。

B2を最初に置いたのは、事前登録の重要停止条件（§5.5）を先に確認するためである。

全バッチを同一commit `64f0b5a` / 同一Config / 同一数値実行環境
`linux-x86_64-glibc2.39-py3.12.3-np2.5.2` で実行する。
正式実行開始後は科学コード・Configを変更しない。
§3 で参照した途中実行データは参考扱いとし、正式結果には混ぜない。

### バッチ1（B2 chemical-only）— 完了 / §5.5 クリア

実行commit `64f0b5a`、40 run、所要5分、診断条件チェック702項目すべてOK。

```text
b2_chem_only_chemspec_treatment: 20/20 seed が 10,000 tick まで生存 (必要 18/20) → OK
```

| | control (gain=0) | treatment (gain=64) |
|---|---:|---:|
| 生存 | 18/20（seed 2, 6 が絶滅） | **20/20** |
| 最終pop 中央値 | 48 | **104** |
| vent滞在率 | 0.780 | **0.846** |
| chemical取得累積 | 208,043 | **468,113** |

**`docs/V1.6_Exp10_レビュー.md` B-4 の懸念は実測で否定された。**
「定位保持を失うと vent 依存の chemical-only 生態が壊れる」と書いたが、実際には
temporal sensing の方が vent 近傍に留まり、chemical取得2.25倍・個体数2.2倍・絶滅ゼロだった。

vent距離帯別（treatment）では滞在が d1_2 で最大（0.566）、chemical取得も d1_2 が最大。
vent直上（d0_1、0.082）より1〜2セル外側に留まるのは、直上ではstockを吸い尽くして
`dQ` が下がるためで、消費→離脱→回復というstock型資源の性質と整合する。

なお要約ツールは §8-3（high-Q改善）を「未達」と出すが、これは §6 の指標退化そのもので
b2では `hi_q` が control/treatment とも 1.0000 固定になり改善量が定義上0になるためである。
V1.6の失敗ではない。判定基準を実行後に変えないため**ツールには手を入れていない**。

## 7. 要判断項目

### 7.1 Phase B本番の回し方 — **決着済み（§6.5）**

科学条件を変えず 40 run × 5バッチへ分割して実行することで決着した。
経路はローカルに統一する（`workflow_dispatch` は workflow が default branch に
無いと起動できず、B2をローカルで正式実行した以上、同一環境の要件を守るには
残りもローカルが一貫するため）。

残る実務課題は**生データのDrive転送**である。ローカル実行では rclone 設定が
GitHub secret のため転送できない。`archives/` に tar.gz でまとめてあるので、
最終的に別途退避するか Actions で回収し直す必要がある。

### 7.2 個体数20倍・小型化の扱い

Phase B の `fixed_genes` は `light_absorption` / `chemical_absorption` の2つだけで、
`body_size` は自由に進化する。計画 §5.2 の「進化はOFF」という記述と実際はずれている
（Exp09も同じ設定だったが、固着していたため body_size がほぼ動かなかった）。

control / treatment 双方が同じ小型化を受けるので対照比較自体は成立するが、
10,000 tick では**行動則より体サイズ進化の方が支配的**になる。

- 案1: 仕様どおりの結果として記録する（AGENTS.md の小型化許容方針に沿う）
- 案2: Phase B で `body_size` も固定し、行動則だけを見る
  （事前登録後に `fixed_genes` を変えることになる）

### 7.3 high-Q領域滞在率の退化（§6）

- 案1: b2 では `vent_cell_frac` で §8-3 を判定すると明記する
- 案2: high-Q の定義を「Qが最大値の上位25%**かつ** Q>0」等へ改める
  （事前登録後の指標変更になる）
- 案3: b2 は §8-3 の判定対象から外し、§5.5（生存）のみで判断する

---

## 8. 現時点で確定していること

- V1.6 の実装は仕様どおりで、Phase 0 の15項目すべてを通っている
- Phase A は事前登録どおり Green で、`tau=10` / `gain=64` が機械的に選ばれた
- Matter保存・Energy台帳・seed決定論はV1.6でも成立している
- 一様刺激で偽biasが厳密に出ないことが実測で確認できた

## 9. 確定していないこと

- Phase B（生態を壊さないか）の全条件
- §5.5 chemical-only の生存判定（treatment 12/20 seed のみ）
- Phase C（長時間頑健性）
- V1.6 を default 化してよいか
