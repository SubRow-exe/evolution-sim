# Exp05 本番実行手順

更新: 2026-08-30

> **この文書を Exp05 本番実行時の正本とする。**
>
> 条件・評価項目の正本は `docs/Exp05_実験計画.md`。本書は「どう回すか」だけを扱う。
> 実行環境は **GitHub Actions (ubuntu-24.04 / Linux)**。
> 2条件 × seed 1-20 × 40,000 tick = **40 run** を同一ランナー環境で、
> 結果を途中で見て設計変更せず完遂する。

関連:
- Issue #24
- `docs/Exp05_実験計画.md`
- `docs/V1.2_V1.2.1_詳細実装仕様.md`
- `docs/オンライン実行環境.md`
- `experiments/exp05_pilot/NOTES.md` (pilot結果)

---

## 1. 条件の与え方

Exp04 は `--fix-genes` で条件を切り替えたが、**Exp05は光場を変える**ため
条件をコマンドラインではなくConfigで与える。

| 条件名 | Config | 光場 |
|---|---|---|
| `control` | `configs/exp05_control.json` | `vertical` (V1.1互換) |
| `treatment` | `configs/exp05_treatment.json` | `high_contrast_vertical` 20/50/30, total_scale=1.0 |

ワークフローの `conditions` に渡せるのは `configs/exp05_<条件名>.json` が
存在する名前だけ。存在しなければ setup ジョブが即座に失敗する。

両Configとも `stats_interval=20` / `snapshot_interval=1000`。
それ以外のパラメータは既定値のままで、光場以外は完全に同一。

---

## 2. 実行前チェック

1. `AGENTS.md`、`docs/Exp05_実験計画.md`、本書、Issue #24 を読む
2. 最新 `main` を取得する
3. `git status --short` が空であること (未コミット変更のまま本番を始めない)
4. `git rev-parse HEAD` を記録する。40 runの途中でコードを変更しない
5. CI Green を確認する
6. pilot が全項目Greenであることを確認する (`experiments/exp05_pilot/NOTES.md`)

```bash
git pull --ff-only
git status --short
git rev-parse HEAD
uv run pytest tests -q
uv run python tools/verify_vs_ref.py --ref origin/v1.1-final
```

---

## 3. 起動

GitHub → Actions → **Exp05** → Run workflow。

| 入力 | 本番値 |
|---|---|
| `conditions` | `control,treatment` |
| `seeds` | `1-20` |
| `ticks` | `40000` |
| `upload_events` | `false` (容量大。主解析に不要) |
| `render_spatial` | `true` (PNG/GIFは実験計画の標準成果物) |

40 run が run単位で並列実行される (`max-parallel: 20`)。
`concurrency: exp05` により二重起動しない。

**40 runを1回の起動で投入する。** 途中結果を見てseed数・tick数・閾値・光場を変更しない
(optional stopping を避けるため)。

---

## 4. 出力

### run ごと (Actions成果物 `exp05-<条件>-seed<N>`, 90日保持)

```text
config.json / meta.json / stats.csv / lineages.csv
snapshots/     snap_XXXXXXXX.csv        (40枚 / run)
environment/   static.npz + env_XXXXXXXX.npz (40個 / run)
spatial/light/ frame_*.png + light.gif
events.csv     (upload_events=true のときのみ)
```

Exp04 と違い **snapshots と environment を保存する**。
実験計画 §6 が全40 runでraw snapshot + environment dataの保存を要求しているため。

容量の目安: 1 run あたり十数MB、40 runで数百MB規模。
(Exp03 の 40,000 tick 時点の個体数は 1,200〜4,200)

### collect ジョブ

- `tools/check_env.py` — 数値実行環境の同一性 (**停止条件**)
- `tools/health_check.py` — run数・早期終了・環境・git SHA (**停止条件**)
- `tools/check_pilot.py` — 光場と出力構造 (情報表示のみ・停止しない)
- `tools/analyze_transitions.py` — 条件ごとのsweep累積発生率 (主判定 `top_lineage_frac >= 0.5`)
- `tools/run_batch.py --aggregate` — seed間集計
- `tools/make_manifest.py` — 生データのSHA256とサイズ
- rclone — 生データを外部ストレージへ転送 (`RCLONE_CONFIG_BASE64` / `RCLONE_REMOTE_BASE` 未設定ならskip)

`check_pilot.py` を停止条件にしないのは、早期終了runがあると
「tick数・snapshot数が期待どおりでない」項目がNGになるため。
早期終了は異常ではなく**結果**なので、判定は `health_check.py` に任せる。

健全性チェックが停止条件に該当した場合、生データの退避を終えてから
collect ジョブを失敗させる。**その結果を解釈してはいけない。**

---

## 5. 実行後

1. Actions の Summary で env_check / health_check / sweep解析を確認する
2. 生データを退避する (外部ストレージ or `exp05-rawdata` 成果物)
3. `experiments/exp05_<日時>/` にマニフェストと解析結果を保存する
4. `docs/Exp05_実験計画.md` §6 の主解析を行う
   - 進化: body_size / light_absorption / chemical_absorption / mutation_rate / reproduction_investment
   - lineage: sweep率 / sweep tick / n_lineages / 同一seed 2×2対応
   - 資源: 各flow / total_biomass / 光利用率
   - 空間: 3帯人口・occupied_cells・centroid・移動量・local light・vent滞在
   - 目視: light背景PNG/GIF
5. `docs/次の実験計画.md` と Issue #24 を更新する
6. 次の光環境変更 (候補A: 偏在を強く / 候補B: total_scaleだけ変更) を**一度に1軸だけ**選ぶ

**pilot はローカルLinuxで実行したため数値実行環境キーが本番と異なる。
pilot の数値と本番結果を直接比較しない。**

---

## 附録A. ローカル実行 (代替手段)

正式な実行環境はActions。ローカルは動作確認用。

```bash
uv run python tools/run_batch.py --seeds 1-20 --ticks 40000 --workers <N> \
  --config configs/exp05_control.json --out runs/exp05_control
uv run python tools/run_batch.py --seeds 1-20 --ticks 40000 --workers <N> \
  --config configs/exp05_treatment.json --out runs/exp05_treatment
```

異なる数値実行環境の結果をActionsの結果と混ぜて解析しない
(`meta.json` の `env_key` で機械的に検出できる)。
