# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数のAIアシスタントと人間が共同開発する。**どのAIも、コードを変更する前に必ず本書と `docs/仕様書_Ver1.1_MVP実装版.md` を読むこと。**

## 現在の作業方針の参照順

現在の実装・実験判断では、長期ロードマップより以下を優先する。

1. `docs/次の実験計画.md` — 今から何をするか
2. **Exp04実行時は `docs/Exp04_実行手順.md` — 実行条件・事前チェック・解析ルールの正本**
3. `docs/V1.1終了とVer1.2移行方針.md` — V1.1をどこで締め、次へ進むか
4. 必要に応じて個別Issue / 実験NOTES
5. `docs/開発ロードマップ_リアル化方針.md` — 長期ビジョン

作業が終わったら `docs/次の実験計画.md` と該当Issueの状態を更新する。

### 現在の短期順序

```text
Exp04 (#4) — 4条件×20 seed×40,000 tick。本番は一括設計で完遂
→ V1.1 baseline解析終了・未解決点をBacklog化
→ Ver.1.2 Stage 0: 資源構造監査 (#19)
→ Ver.1.2 最小環境更新（現第一候補: 空間的エネルギーニッチ）
```

Issue #18 の転移トリガー一次解析は**完了済み**。Exp05 / Exp06 / 14遺伝子全面感度解析 (#16) / #7祖先追跡は現在Deferredであり、V1.1終了の必須条件ではない。

**Exp04について、Issue #4の過去コメントにある「body_size 1条件を先行し、結果を見て残り3条件を決める案」は旧検討案で不採用。** Claude Codeは `docs/Exp04_実行手順.md` とIssue #4本文の最新方針を優先し、途中結果を見てseed数・tick数・閾値・固定対象を変更しないこと。

## プロジェクトの目的

単純な世界のルール（物理・エネルギー・物質・遺伝・突然変異）だけを設定し、自然選択によって**予想していなかった生命形態・生態・行動が創発する**ことを観察するシミュレーション。「賢い生物を作る」のではなく「生物が生まれ得る世界を作る」。

## 絶対に守る設計原則

変更をコミットする前に、以下をすべて自問すること。

1. **適応度を直接計算しない。** `fitness = ...` や `if speed > 70: survive()` 型の実装は禁止。生存と繁殖はエネルギー・物質・損傷の帰結としてのみ発生させる
2. **種クラスを作らない。** `species = "plant"` / "predator" は禁止。役割は栄養獲得遺伝子の組み合わせから創発する
3. **寿命値を作らない。** `if age > lifespan: die()` は禁止。老化は損傷蓄積と修復のバランスから創発する
4. **コストは物理・生理則から導く。** 人工的なペナルティ定数ではなく、スケーリング則（例: 代謝∝size^0.75、移動∝mv²）で表現する
5. **物質は厳密保存。** 物質の増減を伴う変更は必ず保存則テスト（`tests/test_conservation.py`）を通すこと。エネルギーの授受は `energy_in_cum` / `energy_out_cum` 台帳に漏れなく計上する
6. **決定性を壊さない。** 乱数は `Simulation.rng`（単一のnumpy Generator）のみ。`random`モジュール・set/dict順序依存・壁時計依存・並列化は禁止。`tests/test_determinism.py` が門番。ただし完全なビット再現は同一数値実行環境内で要求する
7. **想定外の戦略を許容する。** 「この遺伝子はこう使われるはず」という想定で挙動を制限しない
8. **環境負荷は具体的な環境量へ分解する。** 多様性を作るための抽象ペナルティではなく、温度・光・資源など意味のある環境条件から作用を導く
9. **環境拡張は原則1軸ずつ。** 複数ルールを同時に追加して因果を読めなくしない

## 結果を変えない変更と、変える変更を区別する

高速化・リファクタリングは **同一数値実行環境で結果を1ビットも変えてはならない**。
結果が変われば `v1.1-baseline` との比較が壊れ、過去の実験が無効になる。

```bash
uv run python tools/golden.py                      # 記録済みの同一数値実行環境での高速チェック
uv run python tools/verify_vs_ref.py --ref 18137b5 # 同一マシン上で旧refと現在実装を直接比較 (CIが実行)
```

`tools/verify_vs_ref.py` は「WindowsとLinuxで同じ結果を出す」ツールではない。
各実行環境の中で旧実装と新実装を同じ条件で走らせ、実装変更そのものが結果を変えていないかを検証する。

意図的にモデルを変更する場合のみ `tools/golden.py --write` で指紋を更新し、
**理由をコミットメッセージに残すこと**。

**注意: 結果は数値実行環境に依存する。** `math.sin/cos/atan2/hypot` と `pow` の最終ビットが
OS側の数学ライブラリ等に依存するため、同じseedでもWindowsとLinuxでは結果が異なる。
比較実験は同一マシン・同一数値実行環境で行い、異なる環境の結果を同一seedだからという理由で直接比較しないこと。

## 開発フロー

- ブランチを切って作業し、PRで提出する。mainへの直接pushはしない
- 変更後は必ず `uv run pytest tests` を全通しし、結果不変変更では `verify_vs_ref.py` も通す（CIでも自動実行される）
- パラメータ調整をした場合は、根拠（どのseedで何tick回してどうなったか）をPR説明に書く
- 意味のある実験結果は `experiments/` に保存する（下記）

## 実験結果の残し方

`runs/` は.gitignore対象（日常の実行データ）。残す価値のある実験は:

```
experiments/expNN_<名前>/
├─ config.json / meta.json   seed・設定を保存
├─ stats.csv                 集計統計
├─ events.csv                全出生死亡イベント (任意)
├─ plots/                    グラフPNG
└─ NOTES.md                  目的・観察結果・考察
```

**再現にはseedだけでは不十分。** Config、コード版、依存関係、数値実行環境を揃えること。
`meta.json` にはOS / architecture / Python / NumPy / git SHA等を保存する。

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。
uvがPATHにない環境では `python -m uv ...` で起動する。

```bash
python -m uv run pytest tests                                       # テスト
python -m uv run python main.py --seed 42                           # GUI
python -m uv run python main.py --headless --ticks 20000 --seed 42  # 高速実験
python -m uv run python tools/plot_run.py runs/<run_id>              # グラフ生成
```
