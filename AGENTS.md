# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数のAIアシスタントと人間が共同開発する。**どのAIも、コードを変更する前に必ず本書と `docs/仕様書_Ver1.1_MVP実装版.md` を読むこと。**

**作業を始める前に `docs/次の実験計画.md` を読むこと。** 現在何が分かっていて、
次に何をすべきかがまとまっている。作業が終わったら同書の状態を更新してからPRを出す。

## プロジェクトの目的

単純な世界のルール（物理・エネルギー・物質・遺伝・突然変異）だけを設定し、自然選択によって**予想していなかった生命形態・生態・行動が創発する**ことを観察するシミュレーション。「賢い生物を作る」のではなく「生物が生まれ得る世界を作る」。

## 絶対に守る設計原則

変更をコミットする前に、以下をすべて自問すること。

1. **適応度を直接計算しない。** `fitness = ...` や `if speed > 70: survive()` 型の実装は禁止。生存と繁殖はエネルギー・物質・損傷の帰結としてのみ発生させる
2. **種クラスを作らない。** `species = "plant"` / "predator" は禁止。役割は栄養獲得遺伝子の組み合わせから創発する
3. **寿命値を作らない。** `if age > lifespan: die()` は禁止。老化は損傷蓄積と修復のバランスから創発する
4. **コストは物理・生理則から導く。** 人工的なペナルティ定数ではなく、スケーリング則（例: 代謝∝size^0.75、移動∝mv²）で表現する
5. **物質は厳密保存。** 物質の増減を伴う変更は必ず保存則テスト（`tests/test_conservation.py`）を通すこと。エネルギーの授受は `energy_in_cum` / `energy_out_cum` 台帳に漏れなく計上する
6. **決定性を壊さない。** 乱数は `Simulation.rng`（単一のnumpy Generator）のみ。`random`モジュール・set/dict順序依存・壁時計依存・並列化は禁止。`tests/test_determinism.py` が門番
7. **想定外の戦略を許容する。** 「この遺伝子はこう使われるはず」という想定で挙動を制限しない

## 結果を変えない変更と、変える変更を区別する

高速化・リファクタリングは **結果を1ビットも変えてはならない**。
結果が変われば `v1.1-baseline` との比較が壊れ、過去の実験がすべて無効になる。

```bash
uv run python tools/golden.py                      # 同一OS内の高速チェック
uv run python tools/verify_vs_ref.py --ref 65eed4a # OS非依存の等価性検証 (CIが実行)
```

意図的にモデルを変更する場合のみ `tools/golden.py --write` で指紋を更新し、
**理由をコミットメッセージに残すこと**。

**注意: 結果はOS依存である。** `math.sin/cos/atan2/hypot` と `pow` が各OSのlibm実装のため、
同じseedでもWindowsとLinuxで結果が異なる。実験は同一マシンで行い、
異なるOSの結果を直接比較しないこと。

## 開発フロー

- ブランチを切って作業し、PRで提出する。mainへの直接pushはしない
- 変更後は必ず `uv run pytest tests` を全通しする（CIでも自動実行される）
- パラメータ調整をした場合は、根拠（どのseedで何tick回してどうなったか）をPR説明に書く
- 意味のある実験結果は `experiments/` に保存する（下記）

## 実験結果の残し方

`runs/` は.gitignore対象（日常の実行データ）。残す価値のある実験は:

```
experiments/expNN_<名前>/
├─ config.json / meta.json   (seed含む → 誰でも完全再現可能)
├─ stats.csv                 集計統計
├─ events.csv                全出生死亡イベント (任意)
├─ plots/                    グラフPNG
└─ NOTES.md                  目的・観察結果・考察
```

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
uvがPATHにない環境では `python -m uv ...` で起動する。

```bash
python -m uv run pytest tests                                  # テスト
python -m uv run python main.py --seed 42                      # GUI
python -m uv run python main.py --headless --ticks 20000 --seed 42  # 高速実験
python -m uv run python tools/plot_run.py runs/<run_id>        # グラフ生成
```
