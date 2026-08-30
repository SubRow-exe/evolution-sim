# Exp06 実行手順 — chemical利用経路の成立性診断

更新: 2026-08-30

> **この文書を Exp06 実行時の正本とする。**
>
> 条件・判定ロジックの正本は `docs/Exp06_実験計画.md`。本書は「どう回すか」だけを扱う。
> 実行環境は **GitHub Actions (ubuntu-24.04 / Linux)**。
> 4条件 × seed 1-10 × 10,000 tick = **40 run** を1回の起動で投入し、
> 結果を見て条件を変更せず完遂する。

関連:
- Issue #34
- `docs/Exp06_実験計画.md`
- `docs/Exp05_結果考察.md`
- `AGENTS.md`

---

## 1. 診断ハーネスの構成

Exp06は「パラメータが存在すること」と「進化的に到達可能なこと」を分ける診断であり、
**default世界を一切変更しない**。診断条件はConfigからのみ注入する。

| Config項目 | 既定 | Exp06での使い方 |
|---|---|---|
| `light_pattern` / `light_max` | `vertical` / 1.2 | `uniform` / **0.0** (全条件) |
| `diagnostic_placement` | `random` | `vent` で初期個体を噴出口セル上へ配置 |
| `diagnostic_gene_overrides` | `{}` | `{"chemical_absorption": 2.0}` |
| `fixed_genes` | `[]` | 上書きした遺伝子は必ずここにも入れる |

実装上の保証 (`tests/test_exp06_diagnostics.py` で検証):

- 既定値のままなら通常実行と**1ビットも変わらない** (乱数系列も一致)
- ゲノム上書きは乱数を消費しない → 同一seedなら B/C・A/D の初期配置が一致する
- vent配置は `chem_mask=True` のセルのみを使い、セル内位置は `Simulation.rng` から決定的に生成
- 上書きした遺伝子を `fixed_genes` に入れ忘れると `ValueError` で弾く
  (positive control が世代とともに崩れるのを防ぐ)
- 上書きは全世代で固定されるため、C/D の chemical_absorption は最後まで厳密に 2.0

`chemical_absorption=2.0` は**診断用のpositive control**であり、次期初期値候補ではない。

## 2. 条件とConfig

| 条件名 (Config) | 記号 | 初期ゲノム | 初期配置 |
|---|---|---|---|
| `configs/exp06_a_ancestor_random.json` | A | 現行祖先 | ランダム |
| `configs/exp06_b_ancestor_vent.json` | B | 現行祖先 | vent上 |
| `configs/exp06_c_chem_vent.json` | C | chem 2.0固定 | vent上 |
| `configs/exp06_d_chem_random.json` | D | chem 2.0固定 | ランダム |

全条件で `light_max=0.0` / `stats_interval=20` / `snapshot_interval=1000`。
世界サイズ・chemical資源・nutrient・生理・繁殖・突然変異は現行V1.2のまま。

## 3. 実行前チェック

```bash
git pull --ff-only
git status --short          # 空であること
git rev-parse HEAD          # 記録する
uv run pytest tests -q
uv run python tools/verify_vs_ref.py --ref <直前のmain>   # 通常実行の結果不変
```

## 4. 起動

GitHub → Actions → **Exp06** → Run workflow。

| 入力 | 本番値 |
|---|---|
| `conditions` | `a_ancestor_random,b_ancestor_vent,c_chem_vent,d_chem_random` |
| `seeds` | `1-10` |
| `ticks` | `10000` |
| `upload_events` | `true` (死因の内訳を追える) |
| `render_spatial` | `true` (背景は chemical。光0なのでlight背景は使わない) |

setupジョブが起動前に各Configの `light_max=0` と上書き遺伝子の固定を検証する。

**40 runを1回で投入する。** 途中結果を見てseed数・tick数・`chemical_absorption=2.0`・
条件を変更しない。

### 追加投入 (事前規定)

いずれかの条件で生存と絶滅が混在し、10 seedで診断が曖昧な場合のみ、
**その条件だけ** `seeds=11-20` で追加実行する。判断基準は
`docs/Exp06_実験計画.md` §6 の3項目に限定する。

## 5. 出力と判定

### run ごと (成果物 `exp06-<条件>-seed<N>`)

```text
config.json / meta.json / stats.csv / lineages.csv / events.csv
snapshots/     environment/     spatial/chemical/ (PNG + GIF)
```

絶滅した場合はその時点までの記録が残る。**絶滅は失敗ではなく測定結果**であり、
run ジョブも health_check も絶滅では止まらない。

### collect ジョブ

| チェック | 停止条件か |
|---|---|
| `check_env.py` 数値実行環境の同一性 | **停止** |
| `health_check.py` run数・環境・SHA (早期終了は警告のみ) | **停止** (早期終了以外) |
| `check_exp06.py` 光0・配置・chem固定2.0・対応配置 | **停止** |
| `summarize_exp06.py` 生存/絶滅・人口推移・chemical利用の要約 | 情報 |
| `run_batch.py --aggregate` seed間集計 | 情報 |

`check_exp06.py` を停止条件にしているのは、診断条件が崩れていたら
結果をどう読んでも意味がないため。生データの退避を終えてからジョブを落とす。

`summarize_exp06.py` は §8 の切り分け表を機械的に当てはめた**候補**を出力するが、
結論と次に見直す1軸は人が決める。

## 6. 実行後

1. Summary で env_check / health_check / 診断条件チェック / 要約を確認する
2. 生データを退避する (外部ストレージ or `exp06-rawdata` 成果物)
3. `experiments/exp06_<日時>/` に要約とマニフェストを保存する
4. `docs/Exp06_実験計画.md` §7 の評価項目を確認する
   - 生存・繁殖: extinction有無/tick、population時系列、births/deaths
   - chemical利用: flow_chemical、chemical stock、vent_cell_frac、
     祖先条件で `chemical_absorption >= 0.5 / 1.0 / 1.5` に到達した系統の有無
   - 空間: vent占有、centroid、occupied cells、chemical背景GIF
   - light flow = 0 の確認
5. §8 の切り分けから、次に見直す**1軸だけ**を決める
6. `docs/次の実験計画.md` と Issue #34 を更新する
7. 光総量0.75/0.50系列はここで初めて再検討する

## 附録A. ローカル実行 (動作確認用)

```bash
for c in a_ancestor_random b_ancestor_vent c_chem_vent d_chem_random; do
  uv run python tools/run_batch.py --seeds 1-10 --ticks 10000 --workers <N> \
    --config configs/exp06_${c}.json --out runs/exp06/${c}
done
uv run python tools/check_exp06.py runs/exp06 --seeds 1-10
uv run python tools/summarize_exp06.py runs/exp06
```

Actionsと数値実行環境が異なるため、ローカル結果とActions結果を混ぜて解析しない。
