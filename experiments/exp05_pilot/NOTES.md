# Exp05 Pilot — 実装健全性確認

実行日: 2026-08-30
コード: `7b84154` (`claude/pilot-execution-plan-52spjd`)
正本: `docs/Exp05_実験計画.md` §5 / `docs/V1.2_V1.2.1_詳細実装仕様.md` §9

> **このpilotは実装健全性の確認だけを目的とする。**
> 生物学的な結果 (暗部の無人化・個体数差・形質差など) は記録するが、
> これを理由にExp05本番の条件を変更しない。
> 仕様を変えるならpilotを破棄して再事前登録する。

---

## 1. 実行条件

```text
Control  : configs/exp05_control.json    (light_pattern=vertical)
Treatment: configs/exp05_treatment.json  (light_pattern=high_contrast_vertical
                                          bright=0.20 / transition=0.50
                                          dark_floor=0.0 / total_scale=1.0)
seed     : 1, 2, 3
ticks    : 5,000
run数    : 2条件 × 3 seed = 6
stats_interval    = 20
snapshot_interval = 1000
```

実行コマンド:

```bash
uv run python tools/run_batch.py --seeds 1,2,3 --ticks 5000 --workers 3 \
  --config configs/exp05_control.json --out runs/exp05_pilot/control
uv run python tools/run_batch.py --seeds 1,2,3 --ticks 5000 --workers 3 \
  --config configs/exp05_treatment.json --out runs/exp05_pilot/treatment
for d in runs/exp05_pilot/*/2*seed*; do
  uv run python tools/render_spatial.py "$d" --background light --gif --fps 3
done
uv run python tools/check_pilot.py runs/exp05_pilot --ticks 5000
```

数値実行環境 (`checks/env_check.txt`):

```text
linux-x86_64-glibc2.39-py3.12.3-np2.5.2   6 run すべて同一
```

**本番Exp05はGitHub Actions (ubuntu-24.04) で実行するため、環境キーは変わる。**
pilotの数値をExp05の結果と直接比較しない。

---

## 2. 健全性チェック結果 — 全項目Green

| 確認項目 | 結果 | 根拠 |
|---|---|---|
| crash / 早期終了なし | OK | 6 run すべて 5,000 tick 到達・絶滅なし (`checks/health_check.txt`) |
| Control/Treatment 総光量一致 | OK | 双方 1,248.000000 E/tick。`light_supply_cum` も双方 6,240,000 |
| Treatment 帯構造 8/20/12 | OK | 北8行plateau・中20行単調減少・南12行完全暗部 |
| Treatment 実効ピーク | OK | 1.733333 = 1.2 × 13/9 |
| Control が V1.1 互換 | OK | `verify_vs_ref.py --ref origin/v1.1-final` 全4ケース指紋一致 |
| snapshot / environment NPZ | OK | 各run snapshot 5枚・env NPZ 5個・static.npz あり |
| 空間指標の出力 | OK | stats.csv の3帯人口合計 == population、lineages.csv に8指標 |
| PNG / GIF | OK | 各run PNG 5枚 + `light.gif` |
| 観測ON/OFF不変性 | OK | `tests/test_observation_invariance.py` 3ケースGreen |
| テスト全体 | OK | 42 passed / 4 skipped (`checks/pytest.txt`) |
| 実行環境・git SHAの単一性 | OK | 6 run すべて同一環境・同一SHA (dirtyなし) |

判定出力: `checks/check_pilot.txt`

補足: 同一seed・同一条件で2回 (Config commit前と後) 実行し、
最終個体数まで一致した (別プロセス・別バッチでも決定性が保たれることの確認)。

skipされた4テストは `tests/test_golden.py` (この環境キーの指紋が未記録)。
実装等価性は `verify_vs_ref.py` 側で担保している。

---

## 3. 出力された数値 (参考記録・判断材料にしない)

tick 5,000 時点:

| 条件 | seed | 最終pop | n_lineages | top_frac | north | middle | south | mean_local_light | 光利用率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 1 | 364 | 85 | 0.027 | 78 | 252 | 34 | 0.880 | 12.5% |
| control | 2 | 336 | 79 | 0.027 | 129 | 187 | 20 | 0.918 | 11.1% |
| control | 3 | 376 | 81 | 0.040 | 114 | 232 | 30 | 0.888 | 12.9% |
| treatment | 1 | 490 | 56 | 0.039 | 175 | 315 | 0 | 1.419 | 15.3% |
| treatment | 2 | 480 | 52 | 0.044 | 292 | 188 | 0 | 1.563 | 15.5% |
| treatment | 3 | 443 | 52 | 0.047 | 229 | 214 | 0 | 1.514 | 16.1% |

光利用率 = `flow_light_cum / light_supply_cum` (累積)。

Treatment では南帯 (完全暗部・12行) の個体数が tick 5,000 時点で 0 になった。
これは `docs/Exp05_実験計画.md` §7 が「意味のある結果」として事前に挙げている
パターンの一つであり、**実装異常ではない。条件変更の理由にもしない。**

5,000 tick は V1.1 で lineage sweep が起きるより前の段階であり
(`top_lineage_frac` は全runで 0.05 未満)、進化的な結論は一切出せない。

---

## 4. 保存物

```text
experiments/exp05_pilot/
├─ NOTES.md
├─ checks/            check_pilot / health_check / env_check / verify_vs_ref / pytest
├─ control/seed{1,2,3}/   config.json meta.json stats.csv lineages.csv spatial/
├─ control/aggregate/
├─ treatment/seed{1,2,3}/
└─ treatment/aggregate/
```

snapshots CSV・environment NPZ・events.csv・performance.csv は容量が大きく、
pilotの判定には不要なため保存していない
(configs/ と seed から同一環境で再生成できる)。

---

## 5. 次のステップ

pilot は全項目Greenのため、`docs/Exp05_実験計画.md` の本番条件を
**変更せずそのまま** Exp05 (Issue #24) を実行する。

```text
Control:   configs/exp05_control.json
Treatment: configs/exp05_treatment.json
seed 1-20 / 40,000 tick / 2条件 × 20 seed = 40 run
GitHub Actions (ubuntu-24.04) / 同一ランナー環境
```

本番前に必要な作業:
- Exp05用ワークフロー (`.github/workflows/exp05.yml`) の追加
  — exp04.yml と同じ構造で、条件は `--config` で切り替える
- 生データ (snapshots / environment NPZ) の保存先確保。
  40 run × 40,000 tick では snapshot が 40枚/run になり容量が増えるため、
  Actions成果物 + 外部ストレージ転送の経路を exp04.yml と同様に用意する
