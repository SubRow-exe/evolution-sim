# 生物進化シミュレーション (evolution_sim)

単純な世界のルール（物理・エネルギー・物質・遺伝・突然変異）だけを設定し、
自然選択によって予想していなかった生命形態・生態・行動が**創発**することを観察するシミュレーション。

- 方針: 仕様書 Ver.1.0 方針版 (`C:\Project\# 生物進化シミュレーション 仕様書 Ver.1.0 方針版.txt`)
- 実装仕様: [docs/仕様書_Ver1.1_MVP実装版.md](docs/仕様書_Ver1.1_MVP実装版.md)

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
