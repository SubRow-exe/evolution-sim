# 生物進化シミュレーション (evolution_sim)

単純な世界のルール（物理・エネルギー・物質・遺伝・突然変異）だけを設定し、
自然選択によって予想していなかった生命形態・生態・行動が**創発**することを観察するシミュレーション。

**開発に参加する場合はまず [docs/次の実験計画.md](docs/次の実験計画.md) を読むこと**
(現在地・未解決の問い・次にやるべきことがまとまっている)。

- 方針: [docs/仕様書_Ver1.0_方針版.md](docs/仕様書_Ver1.0_方針版.md)
- 実装仕様: [docs/仕様書_Ver1.1_MVP実装版.md](docs/仕様書_Ver1.1_MVP実装版.md)
- 使い方: [docs/操作ガイド.md](docs/操作ガイド.md) — GUIの見方・キー操作・出力レポートの読み方
- 長期計画: [docs/開発ロードマップ_リアル化方針.md](docs/開発ロードマップ_リアル化方針.md)
- 協働規約: [AGENTS.md](AGENTS.md) — 守るべき設計原則

## これまでに観察された創発

| 現象 | 実験 |
|---|---|
| 適応度関数なしでの方向性選択 (光利用能力の上昇) | [exp01](experiments/exp01_baseline_20k/NOTES.md) |
| 単一系統による選択的一掃 (シェア 3.7% → 96.2%) | [exp02](experiments/exp02_baseline_5seeds/NOTES.md) |
| 突然変異率のヒッチハイク (無性生殖集団のmutator hitchhiking) | [exp02](experiments/exp02_baseline_5seeds/NOTES.md) |
| 断続的な個体数転移 (5 seed中2 seedでのみ発生) | [exp02](experiments/exp02_baseline_5seeds/NOTES.md) |

いずれも設計者が実装した挙動ではなく、世界のルールから生じた結果である。

## 設計原則

- 適応度を直接計算しない。生存と繁殖はエネルギー・物質・損傷の帰結
- 「植物」「捕食者」「分解者」というクラスは存在しない。栄養獲得遺伝子の組み合わせの結果として役割が分化する
- 寿命パラメータは存在しない。損傷と修復のバランスから老化が創発する
- 物質は世界全体で厳密に保存される（無機物→生体→死骸→無機物の閉じた循環）
- エネルギーは外部（光・熱水噴出口）から流入し、熱として散逸する
- 同一Seedで完全再現可能

## 実行

```bash
# GUI (リアルタイム表示)
uv run python main.py --seed 42

# ヘッドレス高速実行 (超長期実験用)
uv run python main.py --headless --ticks 100000 --seed 42

# 記録から事後グラフ生成
uv run python tools/plot_run.py runs/<run_id>
```

### GUIキー操作

```
SPACE = 一時停止     1/2/3 = 速度 x1/x10/x100
G = グラフをplots/へ保存
D = 災害 (90%ランダム死亡 → ボトルネック観察)
R = リセット (新seed)   ESC = 終了
```

個体の色は栄養戦略を表す: **赤=捕食、緑=光合成、青=死骸分解**。

## オンライン実行環境

開発は **GitHub Codespaces**、本番計算は **GitHub Actions**、生データは外部ストレージ。
セットアップと運用方針は [docs/オンライン実行環境.md](docs/オンライン実行環境.md)。

```bash
# 生データ転送経路の疎通確認 (数KB、約30秒)
gh workflow run drive_check.yml
# Exp04 本番 (100 run、約3時間)
gh workflow run exp04.yml -f seeds=1-20 -f ticks=40000
```

## 計算性能ベンチマーク

クラウド環境選定のため、ローカル / Codespaces / クラウドで同一条件の性能を比較できる。

```bash
uv run python tools/benchmark.py --quick                    # 疎通確認 (約40秒)
# 比較用の完全版
uv run python tools/benchmark.py --full --scaling 1,2,4,8 --label <環境名> --out benchmarks/<環境名>.json
uv run python tools/benchmark.py --compare benchmarks/*.json
```

詳細は [docs/ベンチマーク.md](docs/ベンチマーク.md)、
分析は [docs/計算特性と並列化方針.md](docs/計算特性と並列化方針.md)。

## テスト

```bash
uv run pytest tests
```

- `test_determinism` — 同一seed 2回実行の完全一致
- `test_conservation` — 物質の厳密保存・エネルギー台帳の整合（災害を跨いでも）
- `test_smoke` — 既定設定で個体群が成立すること（Exp 0）

## 出力データ

```
runs/<run_id>/
├─ config.json / meta.json   全設定・seed (完全再現の根拠)
├─ events.csv                全出生・死亡イベント (系統樹再構築可能)
├─ stats.csv                 個体数・死因・全14遺伝子の平均と分散ほか
├─ snapshots/                全個体スナップショット (2000 tickごと)
└─ plots/                    population / genes / budget / histograms
```
