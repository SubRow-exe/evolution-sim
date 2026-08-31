# Exp10 Phase A figures

`docs/実験結果保存方針.md` §2 に従う。解釈の正本は `docs/Exp10_中間報告.md`、
実測NOTESは `../NOTES.md`。

生成元: `phaseA.csv`（3,900 run / 2,000 tick / 100個体 / 20 seed）。
Fig.2 と Fig.4 だけは軌跡と最終位置が要るので、代表条件を**同一seed・
同一パラメータで再実行**して取っている（arenaは決定的なので本体と同じ結果）。

図中のラベルは英語にしている。日本語フォントは環境依存でCIや他マシンだと
文字化けするため。意味の説明は本ファイルと中間報告に置く。

## 集計プロット

| ファイル | 何を示すか |
|---|---|
| `fig1_turn_response.png` | 行動則そのもの。`turn_factor = 2/(1+exp(gain·dQ))` の形と、gainごとの効き方。**dQ から向きは決めない**（曲がり幅だけを変える）ことを図示している。 |
| `fig2_trajectories.png` | K1 light-Y / lightspec の軌跡12本。左が control（gain=0）、右が選定値（gain=64）。背景は `Q` 場で明るいほど高Q。白点が出発位置。 |
| `fig3_hi_q_residence.png` | high-Q領域滞在率 vs `response_gain`（環境5種 × 表現型3種、tau=10固定）。帯はseed間のmin-max。破線0.25は面積比＝偶然水準。 |
| `fig4_spatial_K3_K4.png` | K3（直交）と K4（逆向き）での最終位置分布。上段control / 下段temporal。K4で lightspec と chemspec が反対側へ分かれるのが読める。 |
| `fig5_param_sweep.png` | パラメータスイープheatmap。`(memory_tau, gain)` ごとの high-Q滞在率の control 比改善量 [pp]。事前登録の閾値は +5 pp。 |

生成コマンド:

```bash
uv run python tools/plot_exp10.py phase-a <phaseA dir> \
  --out experiments/exp10_phaseA_20260831/figures --tau 10 --gain 64
```

## 代表条件の選び方

計画 §4.7 で選定された **`memory_tau=10` / `response_gain=64`** を
temporal 側の代表とした。結果を都合よく見せるための選択ではなく、
事前登録規則が機械的に選んだ組をそのまま使っている。

Fig.2 / Fig.4 の seed は **seed 1 固定**（保存方針 §3-1 のanchor）。

Fig.4 の条件は次の順で選んだ。

1. K3 generalist — 両刺激統合が最も直接見える組
2. K4 の3表現型 — specialist が逆方向へ分かれ、generalist が中間に留まることを見る

## 読むときの注意

- **K0（一様場）の high-Q滞在率は全条件で 1.0000 になり、意味を持たない。**
  `Q` が空間一定だと上位25%の閾値が定数と一致し全セルが high-Q になるため。
  K0 の判定は drift（Fig.3 ではなくNOTESの表）で行う。
- Fig.3 の破線 0.25 は「面積比＝偶然に高Q領域にいる確率」。
  これを上回った分だけが走性の効果である。
- Fig.2 / Fig.4 の背景色スケールは図ごとに独立。**図をまたいで明るさを比較しない。**
- gain=256 は gain=64 より明らかに強く効くが、事前登録規則 §4.7 は
  「効く中で最も弱い変更」を採るため 64 を選んでいる。
  図で 256 が目立つことは選定の誤りを意味しない。

## 生データ

Phase A は移動専用arenaで、個体単位の生データを持たない設計である。
`../phaseA.csv`（3,900行）が結果の全量で、外部ストレージへ退避すべき
生データは無い。再現は `tools/arena_exp10.py` を同一commitで実行すればよい。
