# Exp04 本番実行手順

更新: 2026-08-29

> **この文書を Exp04 実行時の正本とする。**
> Issue #4 の過去コメントにある「1条件を先行して結果を見てから残り3条件を決める案」は検討案であり、**現在は不採用**。
> 本番は **4条件 × seed 1〜20 × 40,000 tick を、結果を途中で見て設計変更せず完遂する**。
> Issueコメント・古いメモと本書が衝突する場合は、**本書とIssue #4本文の最新状態を優先する。**

関連:
- Issue #4
- `docs/次の実験計画.md`
- `experiments/exp03_20seeds_40k/trigger_analysis/NOTES.md`
- `AGENTS.md`

---

## 1. 最終決定

### 実験条件

| 固定遺伝子 | 固定値 |
|---|---:|
| `body_size` | 1.0 |
| `reproduction_investment` | 0.4 |
| `mutation_rate` | 0.05 |
| `light_absorption` | 0.3 |

各条件:
- seed: 1〜20
- ticks: 40,000
- workers: 14
- sweep主判定: `top_lineage_frac >= 0.5`
- 感度解析: 0.3 / 0.5 / 0.7
- baseline: Exp03 20 seed（40kで13/20が主判定sweep）

### 採用しない実行案

以下は過去に検討したが、事前3 seed × 10,000 tick確認で4固定条件とも集団が成立することを確認したため採用しない。

- `body_size` 1条件だけ先に本番実行し、その結果を見て残り3条件の設計を変える
- 4条件を10 seedへ縮小する
- 途中結果を見てseed数・tick数・閾値・固定対象を変更する

理由: Exp04は4条件間を同じ事前固定設計で比較する方が解釈しやすく、途中結果を見た後の設計変更を避けられる。

---

## 2. 実行前チェック（Claude Codeは必ず実施）

### A. コードと作業ツリー

1. `AGENTS.md`、本書、`docs/次の実験計画.md`、Issue #4 を読む。
2. 最新 `main` を取得する。
3. `git status --short` が空であることを確認する。未コミット変更がある状態で本番を開始しない。
4. `git rev-parse HEAD` を記録する。本番4条件の途中でコードを変更しない。
5. 依存関係をlockfileどおりに揃える。

```bash
git pull --ff-only
git status --short
git rev-parse HEAD
uv sync --frozen
```

### B. テスト

本番前に全テストを通す。

```bash
uv run pytest tests
```

失敗した場合は本番を開始しない。

モデル挙動に関係するコードを本番直前に変更した場合は、`AGENTS.md` の決定性・結果不変確認も満たすまで開始しない。

### C. 実行環境

- Exp03と同じWindows実行マシンを使用する。
- 4条件すべてを同じ数値実行環境で完結させる。
- OS / Python / NumPy / git SHA 等は各runの `meta.json` に自動記録される。
- 4条件を同時に外側から並列実行しない。**条件は順番に実行し、各条件内だけ `--workers 14`** とする。

### D. 出力先

`run_batch.py` は指定した親ディレクトリの下へ時刻付きrunを追加する。
古いパイロットrunや途中runと混ざると集計を汚染するため、**本番専用の新規ディレクトリを使い、既存ディレクトリへ追記しない。**

本番の親ディレクトリ名は以下に固定する。

- `runs/exp04_20seeds_40k_fix_body_size`
- `runs/exp04_20seeds_40k_fix_reproduction_investment`
- `runs/exp04_20seeds_40k_fix_mutation_rate`
- `runs/exp04_20seeds_40k_fix_light_absorption`

開始前に同名ディレクトリが存在する場合は、内容を確認せず上書き・追記しない。旧データなら別名へ退避するか、本番用に別の完全に新しい名前を使い、その名前を実験NOTESへ記録する。

---

## 3. 本番実行

```bash
for G in body_size reproduction_investment mutation_rate light_absorption; do
  uv run python tools/run_batch.py \
    --seeds 1-20 \
    --ticks 40000 \
    --workers 14 \
    --fix-genes $G \
    --out runs/exp04_20seeds_40k_fix_$G
done
```

### 実行中のルール

- 科学的結果を途中で評価して残条件の設計を変更しない。
- 技術的エラーが起きた場合は、原因修正前にどこまで実行済みかを記録する。
- コード変更が必要になった場合、同じ実験群として継続しない。修正・テスト後に新しい出力先でやり直す。
- extinction / `max_population_halt` 等で40,000 tick未満に終了したrunは削除・除外せず、**早期終了という結果として記録**する。

---

## 4. 完了直後の健全性チェック

各条件について:

1. seed 1〜20の20 runが存在すること。
2. 各runの `meta.json` が存在すること。
3. 原則として最終tickが40,000であること。早期終了があれば理由を記録する。
4. 固定対象遺伝子が全期間固定されていること（平均値が固定値、分散0）を確認する。
5. 4条件の数値実行環境が同一であることを確認する。

```bash
uv run python tools/check_env.py \
  runs/exp04_20seeds_40k_fix_body_size \
  runs/exp04_20seeds_40k_fix_reproduction_investment \
  runs/exp04_20seeds_40k_fix_mutation_rate \
  runs/exp04_20seeds_40k_fix_light_absorption
```

環境混在が出た場合は、そのままExp03との科学的比較へ進まない。

---

## 5. 解析ルール（結果確認前に固定済み）

### 主解析

各条件で:

```bash
uv run python tools/analyze_transitions.py runs/exp04_20seeds_40k_fix_<gene>
```

見るもの:
- 40kまでの累積sweep発生率
- sweep tick分布
- 閾値0.3 / 0.5 / 0.7感度
- baseline 13/20との比較

### 同一seed対応比較

各固定条件についてExp03 baselineとseed 1〜20を対応させ、必ず2×2表を作る。

| baseline | fixed |
|---|---|
| sweep | sweep |
| sweep | no sweep |
| no sweep | sweep |
| no sweep | no sweep |

### 判定

- 固定条件で1 seedでもsweep → その形質の進化は**厳密な必要条件ではない**
- 0/20 → **40k以内のsweepに強く必要な候補**。絶対的必要条件とは言わない
- 非ゼロだが明瞭に減少/遅延 → **促進因子候補**
- baselineと同程度/増加 → **主要な必要条件ではない**
- 20 seedで差が曖昧 → **不明**

### 副解析

- population / total_biomass / n_lineages / mean_age
- births / deaths / death causes
- light / chemical / nutrient / corpse / predation resource flows
- 固定対象以外の遺伝子平均・分散（代償進化）
- `light_absorption`固定時にchemical / corpse等の代替利用が増えるか

sweepが起きた条件では:

```bash
uv run python tools/analyze_trigger.py runs/exp04_20seeds_40k_fix_<gene> --batch
```

Issue #18で見えた「高回転（多産多死）状態 → 出生/死亡均衡の崩壊 → sweep」が残るかを見る。

---

## 6. 終了

Exp04結果を `experiments/` にNOTESとともに保存し、Issue #4へ結論を記録する。

Exp04完了をもってV1.1の必須解析を終了する。
未解決の「高回転状態の均衡がなぜ崩れるか」はBacklogへ残し、Ver.1.2 Stage 0（資源構造監査）へ進む。
