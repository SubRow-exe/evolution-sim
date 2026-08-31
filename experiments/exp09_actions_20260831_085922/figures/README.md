# Exp09 figures

`docs/実験結果保存方針.md` §2-3 に従う。解釈の正本は `docs/Exp09_結果考察.md`。

生成元: 本番run `33375257275` と同一commit `c73b039`・同一数値実行環境
`linux-x86_64-glibc2.39-py3.12.3-np2.5.2` でのローカル再実行（25 runすべての
最終tick・最終populationが本番集計と完全一致）。

図中のラベルは英語にしている。日本語フォントは環境依存でCIや他マシンだと
文字化けするため。意味の説明は本ファイルと結果考察に置く。

## 集計プロット

| ファイル | 何を示すか |
|---|---|
| `fig1_agreement.png` | 主判定。条件ごとの「無次元scoreの順位と実際のsource選択が一致した割合」。全条件1.0000。棒の上に選択回数も出している。 |
| `fig2_score_curves.png` | 理論図。chemical stockに対する `chemical_score` 曲線と、明部/中間/暗部の `light_score` 水平線、その交差点stock。lightspecには交差点が存在しないことが読める。 |
| `fig3_stock_vs_pick.png` | 実測図。統計区間ごとの (感知chemical stock平均, chemical選択率) 散布と、chemspec / generalist の交差点stock（縦線）。横軸はsymlog。 |
| `fig4_timeseries.png` | population / 感知chemical stock / chemical選択率 / ventセル滞在率の時間推移。条件ごとに5 seedを重ね描き。 |
| `fig5_response.png` | 選択時の無次元応答 `x/(x+K)` の平均。light側はほぼ一定、chemical側は感知stockに追随する。 |
| `fig6_flows.png` | 実際にどこからEnergyを得たか。左: tick 5,000時点の累積取得量中央値（symlog）。右: 累積取得に占めるchemicalの比率の推移。 |

生成コマンド:

```bash
uv run python tools/plot_exp09.py <runs/exp09> \
  --out experiments/exp09_actions_20260831_085922/figures
```

### 横軸「感知chemical stock」の意味

`sel_chem_stock_mean` は、選択の瞬間に**感知範囲内で見えた最良のセルの**
chemical stockの平均である。個体が乗っているセルのstockではない。
ventが感知範囲に入っていない個体では0になるため、vent以外がstock 0の
混合世界ではこの平均は0側へ強く引かれる。図を読むときはこれを踏まえる。

## 代表GIF

全runをGitへ入れない。選定は結果を都合よく見せないため、以下の順で機械的に決めた
（保存方針 §3）。

1. **主要条件のanchorとして固定seed1**（5条件すべて）
2. 説明例として、条件d内で最も差が出たseedを1本追加

背景fieldは「その条件で判定の焦点になっている側」を選んだ。
光のみの条件は光、chemicalが絡む条件はchemicalにしている。
スナップショット間隔は1,000 tickなので1 GIFは5フレーム（tick 1,000〜5,000）。

| ファイル | 条件 | seed | 背景 | 選定理由 / 読みどころ |
|---|---|---:|---|---|
| `spatial_a_light_only_lightspec_seed1_light.gif` | a_light_only_lightspec | 1 | light | anchor。chemical source無しのcontrol。vertical光勾配の明部側に分布が寄る。 |
| `spatial_b_chem_only_chemspec_seed1_chemical.gif` | b_chem_only_chemspec | 1 | chemical | anchor。光0のcontrol。個体がvent上に張り付き（vent滞在率1.000）、占有されたventのstockが吸収で押し下げられて背景がほぼ暗くなる。 |
| `spatial_c_mixed_lightspec_seed1_light.gif` | c_mixed_lightspec | 1 | light | anchor。交差点が存在しない表現型。chemical選択率0.0000で光帯に分布する。 |
| `spatial_d_mixed_chemspec_seed1_chemical.gif` | d_mixed_chemspec | 1 | chemical | anchor。chemspecでも感知stockが交差点0.44〜1.00に届かず、vent滞在率0.011・chemical選択率0.0164に留まる。 |
| `spatial_e_mixed_generalist_seed1_chemical.gif` | e_mixed_generalist | 1 | chemical | anchor。generalistの交差点3.69〜12.30に対し感知stockが2桁低く、chemicalへ寄らない。 |
| `spatial_d_mixed_chemspec_seed4_chemical.gif` | d_mixed_chemspec | 4 | chemical | 説明例。d条件5 seed中で感知stock（0.3200）とchemical選択率（0.2129）がともに最大のseed。seed1（0.0205 / 0.0164）と並べると、stockが高いほどchemicalを選ぶという交差点式の向きが空間的にも見える。**外れ値ではなく、seed間で単調に並ぶ端**である。 |

生成コマンド:

```bash
uv run python tools/render_spatial.py <run> --background light|chemical --gif --fps 2
```

## 表示上の注意

- 背景の色スケールは1 GIF内の全フレームで共通（`vmax` = そのrunの全フレーム最大）。
  **GIF間で明るさを比較しない。** 条件ごとにstockの絶対水準が違う。
- 個体の色は `lineage_id` から決定的に決めた系統色で、形質や戦略を表さない。
- 個体の大きさは `matter` に比例する。

## 生データ

全run・全snapshot・全画像はGitへ入れていない。

- Google Drive: `gdrive:evolution-sim/exp09_actions_20260831_085922/`（圧縮13 MB）
- GitHub Actions artifact: `exp09-summary`（id 9751690417）
