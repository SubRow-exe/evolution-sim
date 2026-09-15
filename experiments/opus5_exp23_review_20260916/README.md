# Opus5 Exp23 / Exp24 レビュー検証スクリプト

`docs/Exp23_Exp24_Opus5レビュー.md` の数値を再現するための診断スクリプト。
**正式実験ではない。simulation の仕様・Config・判定基準は一切変更していない。**

## `exp23_paired_statistics.py`

入力は Actions run `34951226448` の各 run job ログに出力された
`final_f_photo` 24 値 (スクリプト内に literal で保持)。simulation は走らせない。

出力:

1. `docs/Exp23_結果考察.md` §2 の中央値・範囲・カウントの再現
2. seed を対応ありブロックとした flux 間 paired 差と符号検定
3. seed ごとの flux 単調性
4. 事前登録 gate との照合

```bash
python exp23_paired_statistics.py
```

## `exp24_single_origin_power.py`

`docs/Exp24_実験計画.md` §13 の strong-support 基準
(「6/8 seed で `N_photo(+240h, 0.5) > N_photo(+240h, 0.0)`」) の検出力計算。

Exp23 の実測から per-capita 出生率・死亡率・選択係数を推定し、
線形 birth-death 過程 (Kendall 1948 の解析解) で

- founder 1 個体の establishment probability
- paired endpoint `P(>) / P(=) / P(<)`
- 6/8 基準の検出力
- endpoint を establishment probability にした場合の必要 origin 数
- b, d 推定に対する感度
- recurrent innovation を維持した場合の origin 供給量
- post-origin window 長と必要 origin 数

を出す。simulation は走らせない。

```bash
python exp24_single_origin_power.py
```

## 公開値のローカル再現

レビュー中に以下を実行し、CI の出力と一致することを確認した。

```bash
# 校正 (f0_mol_s = 4.890000722073717e-11 が CI と一致)
uv run python experiments/exp18_v1101_dynamic_vent/phase0.py phase0_local.json

# seed 23007 / flux 0.0 -> final_f_photo = 0.4444444444444444 (CI と一致、N=99)
uv run python experiments/exp23_phototrophy_competition/run_exp23.py \
  --seed 23007 --flux 0.0 --hours 120 --calibration-dir . --outdir repro_23007_f00

# seed 23008 / flux 0.0 と 0.5 -> どちらも final_f_photo = 0.5
#   births 150/150, deaths 0/0 の退化 run であることを確認
uv run python experiments/exp23_phototrophy_competition/run_exp23.py \
  --seed 23008 --flux 0.0 --hours 120 --calibration-dir . --outdir repro_23008_f00
uv run python experiments/exp23_phototrophy_competition/run_exp23.py \
  --seed 23008 --flux 0.5 --hours 120 --calibration-dir . --outdir repro_23008_f05
```
