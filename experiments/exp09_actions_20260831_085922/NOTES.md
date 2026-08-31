# Exp09 実測NOTES — V1.5 異種一次Energy刺激比較則の診断

実行日: 2026-08-31
GitHub Actions: `33375257275` / Exp09 本番
commit: `c73b03973024860a08bb` (PR #42 merge)
規模: 25 run（5条件 × seed1-5）、5,000 tick
workflow: success

Pilot: run `33374470880`（5条件 × seed1 × 1,000 tick）でGreenを確認してから本番。

詳細な解釈の正本は `docs/Exp09_結果考察.md`。

## 用語

- 無次元受容器応答 `response(x,K) = x/(x+K)`:
  単位の違う刺激（光量とchemical stock）を0〜1の共通尺度へ変換した値。
- `light_stimulus_half` (光刺激の半飽和光量): 応答が0.5になる光量。V1.5 default 1.2。
- `chemical_stimulus_half` (chemical刺激の半飽和stock): 応答が0.5になるstock。V1.5 default 12.3。
- 交差点stock: `light_score` と `chemical_score` が等しくなるchemical stock。
  これを上回ればchemical、下回ればlightが一次Energy候補として優勢になる。
- 感知chem stock (`sel_chem_stock_mean`): 選択時に感知範囲内で見えた**最良の**
  chemical stockの平均。個体が乗っているセルのstockではない。
  ventが感知範囲に無い個体では0になる。
- specialist（専門型）/ generalist（両用型）: 診断用に能力を固定した個体。

## 健全性

`tools/health_check.py` / `tools/check_env.py` / `tools/check_exp09.py` の出力より。

- 25 runすべて同一数値実行環境 `linux-x86_64-glibc2.39-py3.12.3-np2.5.2`
- 25 runすべて同一commit `c73b03973024860a08bb`
- 条件ごとのrun数 5 / 早期終了run なし（全runが5,000 tick完走）
- 固定遺伝子 `light_absorption` / `chemical_absorption` は全期間で分散0
- 診断条件チェック **415項目すべてOK**
- source排他成立（light-onlyでchemical flow=0、chemical-onlyで光供給=0）

Phase 0（算術・行動選択の決定論テスト）は `tools/bench_exp09.py` 31項目Green、
単独source Configの `v1.4-final` (`226a926`) 完全一致は
`tools/verify_vs_ref.py --single-source` 4ケースすべて一致で確認済み。

## 主判定 — score順位と実際のsource選択の一致

| 条件 | 一致 | 選択回数 | 一致率 |
|---|---:|---:|---:|
| a_light_only_lightspec | 5,732,947 | 5,732,947 | **1.0000** |
| b_chem_only_chemspec | 2,492,523 | 2,492,523 | **1.0000** |
| c_mixed_lightspec | 5,875,994 | 5,875,994 | **1.0000** |
| d_mixed_chemspec | 4,016,610 | 4,016,610 | **1.0000** |
| e_mixed_generalist | 6,352,148 | 6,352,148 | **1.0000** |

計 24,470,222回の一次Energy候補選択すべてで、無次元scoreの順位と実際の選択が一致した。

tie（`stimulus_tie_eps=1e-9` 内の同点）は全条件で0件。

この指標 (`sel_agree == sel_light + sel_chemical`) が示すのは
「全選択がV1.5比較則の分岐を通り、単独source fallbackにもtie放棄にも落ちなかった」
ことである。無次元scoreと交差点式の代数的等価性および交差点両側での選択反転は
Phase 0 (`tools/bench_exp09.py`) で個別に検証している。
解釈は `docs/Exp09_結果考察.md` §5.1 を参照。

## 事前計算した交差点stock [E/cell]

| 表現型 | 明部 L=1.2 | 中間 L=0.78 | 暗部 L=0.36 |
|---|---:|---:|---:|
| lightspec (light 2.0 / chem 0.3) | 交差点なし | 交差点なし | 交差点なし |
| chemspec (light 0.3 / chem 2.0) | 1.00 | 0.77 | 0.44 |
| generalist (light 1.0 / chem 1.0) | 12.30 | 8.00 | 3.69 |

lightspecは `light_absorption/chemical_absorption × response(L,1.2)` が1以上のため、
stockをいくら上げてもchemicalがlightを追い越さない。これは式の帰結であり異常ではない。

## 条件別サマリ（seed中央値）

| 条件 | 最終pop | chem選択率 | 感知chem stock | vent滞在 | light flow | chem flow |
|---|---:|---:|---:|---:|---:|---:|
| a_light_only_lightspec | 298 | 0.0000 | 0.0000 | 0.000 | 731,297 | 0 |
| b_chem_only_chemspec | 101 | 1.0000 | 1.3981 | 1.000 | 0 | 300,727 |
| c_mixed_lightspec | 303 | 0.0000 | 0.2915 | 0.042 | 728,318 | 7,066 |
| d_mixed_chemspec | 187 | 0.0831 | 0.1041 | 0.096 | 478,743 | 24,112 |
| e_mixed_generalist | 302 | 0.0001 | 0.0796 | 0.061 | 707,772 | 27,946 |

seedごとのchem選択率:

- c_mixed_lightspec: 0.0000（5 seedすべて）
- d_mixed_chemspec: 0.0164 / 0.0532 / 0.0831 / 0.2129 / 0.1623
- e_mixed_generalist: 0.0001 / 0.0000 / 0.0000 / 0.0023 / 0.0010

## 一次Energy候補が他刺激（栄養/死骸/捕食）に負けた回数

| 条件 | light由来 | chemical由来 | 選択回数 |
|---|---:|---:|---:|
| a_light_only_lightspec | 4,335 | 0 | 5,732,947 |
| b_chem_only_chemspec | 0 | 0 | 2,492,523 |
| c_mixed_lightspec | 4,363 | 0 | 5,875,994 |
| d_mixed_chemspec | 172,738 | 0 | 4,016,610 |
| e_mixed_generalist | 183,763 | 0 | 6,352,148 |

## 図

`figures/` を参照。生成コマンド:

```text
uv run python tools/plot_exp09.py <runs> --out experiments/exp09_actions_20260831_085922/figures
uv run python tools/render_spatial.py <run> --background light|chemical --gif --fps 3
```

## 生データ

- Google Drive: `gdrive:evolution-sim/exp09_actions_20260831_085922/`（圧縮13 MB）
- GitHub Actions artifact: `exp09-summary`（id 9751690417）

Gitへは図・NOTES・結果考察のみを入れる（`docs/実験結果保存方針.md` §1）。

## 再現性メモ

figures生成に使ったrunは、本番と同一commit `c73b039`・同一数値実行環境キー
`linux-x86_64-glibc2.39-py3.12.3-np2.5.2` でローカル再実行したもの。
25 runすべての最終tick・最終populationが本番集計と完全一致することを確認した
（例: a seed1-5 = 310/300/298/251/250、d seed1-5 = 187/195/219/186/184）。
