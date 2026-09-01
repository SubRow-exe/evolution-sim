# Exp10 Phase B figures

正式 Phase B（GitHub Actions / commit `287dc9b8` / 数値実行環境
`linux-x86_64-glibc2.39-py3.12.3-np2.5.2` / 5条件 × control/treatment × seed 1-20 ×
10,000 tick）の集計プロットと代表空間可視化。集計値は `summarize_exp10_phaseB.py` の
seed 中央値をそのまま用いている（`../make_figures.py`）。ラベルは英語（日本語フォントの
文字化け回避、計画 §12）。

## 集計プロット

- **fig1_survival_population.png** — 条件別の生存 seed 数（§5.5 gate 18/20 を破線で明示）と
  最終 population（control vs treatment）。全 20/20 生存（B2 control のみ 18/20）。
- **fig2_vent_residence.png** — vent セル滞在率（control vs treatment）。vent を持つ全条件で
  treatment > control。
- **fig3_highq_improvement.png** — §8-3。high-Q 滞在率の改善量（treatment−control, pp）。
  全条件 20/20 seed が改善（方向 OK）、+5pp を超えるのは B4 のみ。B2 は指標退化のため対象外。
- **fig4_energy_uptake.png** — treatment の光/chemical 累積取得量（条件別）。
- **fig5_band_residence.png** — vent 距離帯別滞在率（treatment）。chemspec は 1-2セル外側、
  lightspec は光勾配側（d4+）。

## 代表空間可視化

代表 seed の選定は説明可能・機械的に行う（`docs/実験結果保存方針.md` §3）:
主要条件の anchor として **固定 seed1** を選ぶ。

- **b2_chem_only_seed1.gif / b2_chem_only_seed1_final.png** — B2 chemical-only（control,
  seed1）。§5.5 の対象条件で、vent（噴出口）近傍に個体が集まる chemical 依存生態を示す。
  背景は chemical stock。10,000 tick を 2,000 tick 刻み 5 フレーム。
- **b1_light_only_seed1.gif / b1_light_only_seed1_final.png** — B1 light-only（control,
  seed1）。光勾配のみの世界で、明部側へ個体が広がる様子。背景は light。

代表 seed の条件・選定理由:
| ファイル | 条件 | seed | 選定理由 |
|---|---|---|---|
| b2_chem_only_seed1.* | B2 chem-only / chemspec / control | 1 | 主要条件（§5.5）の固定 anchor |
| b1_light_only_seed1.* | B1 light-only / lightspec / control | 1 | 対照的な光勾配生態の固定 anchor |

注: 全 run の spatial PNG/GIF は各 Actions run が `render_spatial.py` で生成し、
artifact `exp10-<case>-seed<N>` と Google Drive に保存済み（Git には入れない）。
