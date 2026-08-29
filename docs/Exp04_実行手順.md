# Exp04 本番実行手順

更新: 2026-08-29

> **この文書を Exp04 実行時の正本とする。**
>
> **正式な実行環境は GitHub Actions (ubuntu-24.04 / Linux) とする。**
> 本番は **baseline を含む5条件 × seed 1〜40 × 40,000 tick = 200 run** を
> 同一ランナー環境で、結果を途中で見て設計変更せず完遂する。
>
> Windows ローカル実行は**代替手段**として付録Aに残す。
> Issue #4 の過去コメントにある「1条件を先行して結果を見てから残り3条件を決める案」は
> 検討案であり、**現在は不採用**。
> Issueコメント・古いメモと本書が衝突する場合は、**本書とIssue #4本文の最新状態を優先する。**

関連:
- Issue #4
- `docs/次の実験計画.md`
- `docs/オンライン実行環境.md`
- `experiments/exp03_20seeds_40k/trigger_analysis/NOTES.md`
- `AGENTS.md`

---

## 1. 最終決定

### 実行環境: GitHub Actions (Linux)

結果は数値実行環境に依存する (`math.sin/cos/atan2/hypot` と `pow` の最終ビットが
OS側の数学ライブラリ実装に依存するため、同じseedでも Windows と Linux で結果が異なる)。

Exp04 は **Actions のランナー上で全条件を完結させる**。
run単位で並列実行でき、PCを占有せず、環境が `meta.json` で機械的に照合できる。

**この決定の帰結として、baseline も Actions 上で実行する。**
Windows で得た Exp03 の baseline をそのまま比較対象にはできないため、
遺伝子固定なしの baseline を5条件目として同じランナー環境で走らせる。

### 実験条件

| 条件 | 固定遺伝子 | 固定値 |
|---|---|---:|
| `baseline` | (固定なし) | — |
| `body_size` | `body_size` | 1.0 |
| `reproduction_investment` | `reproduction_investment` | 0.4 |
| `mutation_rate` | `mutation_rate` | 0.05 |
| `light_absorption` | `light_absorption` | 0.3 |

各条件:
- seed: 1〜40
- ticks: 40,000
- 総run数: **5条件 × 40 seed = 200 run**
- sweep主判定: `top_lineage_frac >= 0.5`
- 感度解析: 0.3 / 0.5 / 0.7
- **baseline: 本実験内の `baseline` 条件 (Actions / Linux)**

### seed数を20から40へ拡大した理由 (2026-08-29 決定)

**この変更は結果を一切見る前に決定した事前登録である。**
1〜20を実行して結果を見てから21〜40を追加したのではない。
200 runを1回の起動で投入し、40 seedをプールして解析する。

理由は**「不明」判定に落ちる範囲を狭めるため**。

§5の判定基準は「20 seedで差が曖昧なら**不明**」としている。
baselineの転移率を仮に65%とすると、固定条件で30%へ低下した場合の検出力は
n=20 で約50%、n=40 で約80%程度になる。
つまり n=20 では「中程度の効果」を検出できず不明判定になりやすい。

実行環境をActionsへ移し、PCを占有せず並列実行できるようになったため、
標本数を倍にするコストが実質的に無くなったことによる。

**途中で結果を見て打ち切らない。** 40 seed全てを完遂してから解析する
(optional stopping を避けるため)。

### Exp03 (Windows) の 13/20 の扱い

Exp03 は Windows 上で得た結果であり、**40,000 tick までに 13/20 seed が主判定sweep**
に到達している。この数値は**参考値として保存する**が、
**Exp04 の条件間比較には使わない。**

- Exp04 の2×2表・累積発生率の比較対象は、**Actions 上の `baseline` 条件のみ**
- 「Actions の baseline が 13/20 と一致するか」を Exp04 の判定材料にしない
  (数値実行環境が違うので、一致しなくても異常ではない)
- Exp03 と Exp04 baseline の差は形質依存性ではなく環境差を含むため、
  差そのものを科学的主張の根拠にしない

### 採用しない実行案

以下は過去に検討したが、事前3 seed × 10,000 tick確認で4固定条件とも集団が成立することを確認したため採用しない。

- `body_size` 1条件だけ先に本番実行し、その結果を見て残り3条件の設計を変える
- 4条件を10 seedへ縮小する
- 途中結果を見てseed数・tick数・閾値・固定対象を変更する
- **Windows の Exp03 baseline と Actions の固定条件を直接比較する** (数値実行環境が異なる)

理由: Exp04は条件間を同じ事前固定設計・同一環境で比較する方が解釈しやすく、
途中結果を見た後の設計変更を避けられる。

---

## 2. 実行前チェック（Claude Codeは必ず実施）

### A. コードと作業ツリー

1. `AGENTS.md`、本書、`docs/次の実験計画.md`、Issue #4 を読む。
2. 最新 `main` を取得する。
3. `git status --short` が空であることを確認する。未コミット変更がある状態で本番を開始しない。
4. `git rev-parse HEAD` を記録する。本番200 runの途中でコードを変更しない。
   (Actions はディスパッチ時のSHAでチェックアウトするため走行中のジョブには影響しないが、
   再実行時にズレるため触らない)

```bash
git pull --ff-only
git status --short
git rev-parse HEAD
```

### B. テスト

本番前にCIがGreenであることを確認する。

```bash
gh run list --workflow=ci.yml --limit 1
```

失敗している場合は本番を開始しない。
モデル挙動に関係するコードを本番直前に変更した場合は、`AGENTS.md` の
決定性・結果不変確認 (`tools/verify_vs_ref.py`) も満たすまで開始しない。

### C. 実行環境

- **GitHub Actions の ubuntu-24.04 ランナーを使用する。**
- 5条件すべてを同じ数値実行環境で完結させる。Windowsローカルと混在させない。
- OS / Python / NumPy / glibc / ランナーイメージ版 / git SHA は
  各runの `meta.json` に自動記録される (`evosim/runmeta.py`)。
- 環境とコードの同一性は完了後に `tools/health_check.py` が機械的に照合する。
  混在していれば非ゼロ終了し、ワークフローが赤くなる。

### D. 出力先

Actions では run ごとに成果物が分離されるため、ローカルのようなディレクトリ衝突は起きない。
`collect` ジョブが条件ごとに再構成する。

- 成果物名: `exp04-<条件>-seed<N>`
- 集約後: `runs/exp04_<条件>/`
- 生データのアーカイブ: `archives/<条件>.tar.gz` → Google Drive へ転送
- 要約・チェックサム: `experiments/exp04_actions_<timestamp>/`

転送先の設定は `docs/オンライン実行環境.md` を参照。
転送経路は `.github/workflows/drive_check.yml` で事前に疎通確認できる。

---

## 3. 本番実行

```bash
gh workflow run exp04.yml -f conditions=baseline,body_size,reproduction_investment,mutation_rate,light_absorption -f seeds=1-40 -f ticks=40000 -f upload_events=true
```

ワークフロー: `.github/workflows/exp04.yml`

- run単位でジョブを分割 (200ジョブ)。`max-parallel: 20`
- `fail-fast: false` — 1 runの失敗で他を巻き込まない
- 各runは `stats.csv` / `lineages.csv` / `events.csv` / `config.json` / `meta.json` を保存
  (`snapshots/` は容量が大きく Exp04 の判定に使わないため除外)
- `events.csv` はトリガー解析 (§5副解析) に必要。容量と引き換えに既定で保存する

見込み: 1 runあたり20〜45分、20並列で**実時間 約6時間**。
PCを起動し続ける必要はない (投入後はGitHub側で実行される)。
Public リポジトリのため Actions 分は無料。

### 実行中のルール

- 科学的結果を途中で評価して残条件の設計を変更しない。
- 技術的エラーが起きた場合は、原因修正前にどこまで実行済みかを記録する。
- コード変更が必要になった場合、同じ実験群として継続しない。修正・テスト後に
  新しいワークフロー実行としてやり直す。
- extinction / `max_population_halt` 等で40,000 tick未満に終了したrunは削除・除外せず、
  **早期終了という結果として記録**する。
- 個別ジョブが技術的理由 (ランナー障害等) で落ちた場合、**そのrunだけ再実行しない。**
  run数が揃わなければ §4 が停止条件として検出する。

---

## 4. 完了直後の健全性チェック

`collect` ジョブが自動で実行する。手元で再実行する場合:

```bash
uv run python tools/check_env.py runs/exp04_*
```

```bash
uv run python tools/health_check.py runs/exp04_* --ticks 40000 --expect-runs 40
```

`tools/health_check.py` は前提が崩れていれば**非ゼロ終了する**。

**停止する (結果を解釈してはいけない):**

1. 条件ごとの run 数が40に満たない (`--expect-runs 40`)
2. `meta.json` の欠損 (再現条件を特定できない)
3. 固定対象遺伝子の分散が全期間0でない (遺伝子固定が効いていない)
4. 数値実行環境が2種類以上 (条件間比較の前提が崩れる)
5. git SHA が不統一 (異なるコードのrunが混在している)

**停止しない (警告のみ):**

- 早期終了run — 除外せず「早期終了という結果」として一覧に出す。観測結果であり異常ではない
- git SHA の dirty — Actions では通常発生しない

停止条件に該当した場合、生データの退避 (アーカイブ・Drive転送・成果物保存) は
完了させたうえでワークフローを失敗させる。データを失わずに原因究明できる。
**原因を解消して実験群ごとやり直すこと。一部runだけ差し替えない。**

---

## 5. 解析ルール（結果確認前に固定済み）

### 主解析

各条件で:

```bash
uv run python tools/analyze_transitions.py runs/exp04_<条件>
```

見るもの:
- 40kまでの累積sweep発生率
- sweep tick分布
- 閾値0.3 / 0.5 / 0.7感度
- **同一実験内の `baseline` 条件との比較** (Exp03の13/20とは比較しない)

### 同一seed対応比較

各固定条件について**同一実験内の baseline** と seed 1〜40 を対応させ、必ず2×2表を作る。

| baseline (Actions) | fixed |
|---|---|
| sweep | sweep |
| sweep | no sweep |
| no sweep | sweep |
| no sweep | no sweep |

seedは条件間で対応している (同じseedは同じ初期条件) ため、この対応付けは有効である。
**Exp03 (Windows) のseedと対応させてはいけない。**

### 判定

同一実験内の baseline との比較で:

- 固定条件で1 seedでもsweep → その形質の進化は**厳密な必要条件ではない**
- 0/40 → **40k以内のsweepに強く必要な候補**。絶対的必要条件とは言わない
- 非ゼロだが明瞭に減少/遅延 → **促進因子候補**
- baselineと同程度/増加 → **主要な必要条件ではない**
- 40 seedで差が曖昧 → **不明**

### 副解析

- population / total_biomass / n_lineages / mean_age
- births / deaths / death causes
- light / chemical / nutrient / corpse / predation resource flows
- 固定対象以外の遺伝子平均・分散（代償進化）
- `light_absorption`固定時にchemical / corpse等の代替利用が増えるか

sweepが起きた条件では:

```bash
uv run python tools/analyze_trigger.py runs/exp04_<条件> --batch
```

Issue #18で見えた「高回転（多産多死）状態 → 出生/死亡均衡の崩壊 → sweep」が残るかを見る。
Issue #18 は Windows の Exp03 で得た所見なので、**Linux上で再現するかどうか自体が観測対象**である。

---

## 6. 終了

Exp04結果を `experiments/` にNOTESとともに保存し、Issue #4へ結論を記録する。
NOTESには**実行環境が Actions / Linux であること**と、
**Exp03 (Windows) の13/20を比較に使っていないこと**を明記する。

生データは容量が大きいため GitHub には置かず、Google Drive へ転送し、
リポジトリにはマニフェスト (チェックサム + 転送先) を残す。

Exp04完了をもってV1.1の必須解析を終了する。
未解決の「高回転状態の均衡がなぜ崩れるか」はBacklogへ残し、Ver.1.2 Stage 0（資源構造監査）へ進む。

---

## 付録A. Windows ローカルで実行する場合 (代替手段)

Actions が使えない場合の代替手段として残す。**正式な実行環境ではない。**

採用する場合も、**選んだ環境内で全条件を完結させること。混在させない。**

### 環境

- Exp03と同じWindows実行マシンを使用する。
- 4条件を同時に外側から並列実行しない。**条件は順番に実行し、各条件内だけ `--workers 14`** とする。

### 出力先

`run_batch.py` は指定した親ディレクトリの下へ時刻付きrunを追加する。
古いパイロットrunや途中runと混ざると集計を汚染するため、
**本番専用の新規ディレクトリを使い、既存ディレクトリへ追記しない。**

- `runs/exp04_20seeds_40k_fix_body_size`
- `runs/exp04_20seeds_40k_fix_reproduction_investment`
- `runs/exp04_20seeds_40k_fix_mutation_rate`
- `runs/exp04_20seeds_40k_fix_light_absorption`

開始前に同名ディレクトリが存在する場合は、内容を確認せず上書き・追記しない。
旧データなら別名へ退避するか、本番用に別の完全に新しい名前を使い、その名前を実験NOTESへ記録する。

### 実行

```bash
uv sync --frozen
```

```bash
uv run pytest tests
```

```bash
for G in body_size reproduction_investment mutation_rate light_absorption; do uv run python tools/run_batch.py --seeds 1-40 --ticks 40000 --workers 14 --fix-genes $G --out runs/exp04_40seeds_40k_fix_$G; done
```

### baseline の扱い

Exp03 と同じ Windows マシンであれば、Exp03 の baseline (13/20) を比較対象にできる。
ただし **Exp03 実行時から数値実行環境が変わっていないこと**を
`tools/check_env.py` で確認すること。Python や NumPy の更新でも `env_key` は変わる。

環境が変わっていた場合は、Actions と同じく **baseline をローカルで再実行する** (5条件)。

### 比較

| | GitHub Actions (正式) | Windows ローカル (代替) |
|---|---|---|
| 実行 run 数 | 100 (baseline込み) | 80 + 必要なら baseline 20 |
| Exp03 baseline との比較 | 不可 (環境が異なる) | 環境が不変なら可 |
| 実時間 | 約3時間 (PCを占有しない) | 3〜6時間 (PC占有) |
| 費用 | 無料 (Publicリポジトリ) | 電気代のみ |
| 環境の同一性保証 | ランナーイメージ版まで記録・照合 | 手元環境に依存 |
