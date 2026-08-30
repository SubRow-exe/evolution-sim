# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数のAIアシスタントと人間が共同開発する。コードを変更する前に、本書と現在の司令塔ドキュメントを必ず読むこと。

## 現在の作業方針の参照順

1. `docs/次の実験計画.md` — 今から何をするか
2. **`docs/V1.2_V1.2.1_詳細実装仕様.md` — V1.2/V1.2.1実装の正本**
3. `docs/V1.2_実装順序.md` — V1.2 → V1.2.1 → Exp05の順序
4. **`docs/Exp05_実験計画.md` — Exp05条件・評価項目の正本**
5. `docs/バージョニング方針.md`
6. 個別Issue: #19 / #23 / #24
7. `docs/V1.1_総括.md`
8. `docs/開発ロードマップ_リアル化方針.md`

古いExp03/Exp04コメント・旧V1.2候補より上記正本を優先する。
作業完了後は `docs/次の実験計画.md` と該当Issueを更新する。

## 現在の短期順序

```text
V1.1 クローズ / v1.1-final 保存済み
→ #19 V1.2: high_contrast_vertical
→ #23 V1.2.1: environment snapshot + 空間/行動指標 + PNG/GIF
→ 観測ON/OFF結果不変テスト + CI Green
→ pilot: seed 1,2,3 × 2条件 × 5,000 tick
→ #24 Exp05: seed 1-20 × 2条件 × 40,000 tick
→ 数値 + 空間指標 + GIFレビュー
→ 次の光環境変更を決定
```

### V1.2で変更するもの

最初の世界ルール変更は**光場1軸のみ**。

V1.1終盤のsweep群では光利用率が約90%に達していたため、Exp05では総光量を減らさない。世界全体のエネルギー不足と空間偏在を分離する。

Treatment `high_contrast_vertical` の既定仕様:

```text
北20%: 最大光量plateau
中50%: 最大光量 → 0 の線形遷移
南30%: 完全暗部
```

Config:

```text
light_hc_bright_frac = 0.20
light_hc_transition_frac = 0.50
light_hc_dark_floor = 0.0
light_hc_total_scale = 1.0
```

40×40では:

```text
北 8行: 明部
中20行: 遷移
南12行: 完全暗部
```

Control `vertical` とTreatmentの総光供給量は**双方1,248 E/tick**にする。
Treatmentはshape生成後にControl総光量へ正規化し、実効ピークは約1.733333 E/cell/tick。

`light_hc_total_scale` はshapeと総量を分離して将来比較するためのパラメータ。Exp05では必ず1.0固定。
光場生成では乱数を消費せず、同一seedで`chem_mask`等の確率生成物を変えない。

### V1.2で変更しないもの

- INITIAL_GENOME
- 無性生殖
- 成熟年齢なし / 繁殖クールダウンなし
- 化学資源量・vent仕様
- 無機栄養構造
- 生理コスト式
- 突然変異仕様

### V1.2.1

世界ルールを変えない観測機能。

Exp05では:
- `snapshot_interval=1000`
- 個体snapshot CSV
- `environment/static.npz`: light / chem_mask
- `environment/env_XXXXXXXX.npz`: chemical / nutrients
- lineage占有セル数 / 重心 / 分布幅 / 平均移動距離 / mean local light / vent滞在割合
- `tools/render_spatial.py` でPNG/GIF

地理帯はTreatment設計に合わせてControl/Treatment共通で:

```text
North:  y/H < 0.20
Middle: 0.20 <= y/H < 0.70
South:  y/H >= 0.70
```

**観測ON/OFFで乱数系列・科学状態を完全一致させる。**

### Exp05

`docs/Exp05_実験計画.md` を正本とする。

- Control: `light_pattern=vertical`
- V1.2: `light_pattern=high_contrast_vertical`（20/50/30, total_scale=1.0）
- seed 1–20
- 40,000 tick
- 2条件 × 20 seed = 40 run
- stats_interval=20
- snapshot_interval=1000
- 同一seed対応比較
- 主sweep判定 `top_lineage_frac >= 0.5`

Pilotは `seed 1,2,3 × 2条件 × 5,000 tick` と固定。
クラッシュ・総光量・zone境界・ピーク光量・出力・観測不変性の確認だけに使う。
生物学的な結果を見て都合よくExp05条件を変更しない。

### Exp05後

V1.2以降しばらくは光環境を小刻みに振る。

次は一度に1軸だけ変更する。
1. `light_hc_total_scale=1.0`を維持してさらに空間偏在を強くする
2. 20/50/30 shapeを固定し、`light_hc_total_scale`だけ増減する

shapeと総量は同時に変更しない。

## バージョニング

- `V1.1 → V1.2 → V1.3`: 世界ルールを変え、進化結果を変え得る変更
- `V1.2 → V1.2.1 → V1.2.2`: 世界ルールを変えない機能・観測・解析・実行基盤追加

詳細: `docs/バージョニング方針.md`。

## プロジェクトの目的

単純な世界のルール（物理・エネルギー・物質・遺伝・突然変異）だけを設定し、自然選択によって**予想していなかった生命形態・生態・行動が創発する**ことを観察するシミュレーション。「賢い生物を作る」のではなく「生物が生まれ得る世界を作る」。

## 絶対に守る設計原則

1. **適応度を直接計算しない。** `fitness = ...` や `if speed > 70: survive()` 型の実装は禁止。生存と繁殖はエネルギー・物質・損傷の帰結としてのみ発生させる
2. **種クラスを作らない。** `species = "plant"` / `"predator"` は禁止。役割は栄養獲得遺伝子の組み合わせから創発する
3. **寿命値を作らない。** `if age > lifespan: die()` は禁止。老化は損傷蓄積と修復のバランスから創発する
4. **コストは物理・生理則から導く。** 人工的なペナルティ定数ではなく、意味のあるスケーリングや収支で表現する
5. **物質は厳密保存。** 物質の増減を伴う変更は保存則テストを通し、エネルギー授受は台帳へ漏れなく計上する
6. **決定性を壊さない。** 乱数は `Simulation.rng` のみ。壁時計・別乱数源・順序依存を入れない。同一数値実行環境内で再現性を要求する
7. **想定外の戦略を許容する。** 想定した生態型を出すために挙動を直接制限しない
8. **環境負荷は具体的な環境量へ分解する。** 抽象ペナルティではなく光・温度・資源等から作用を導く
9. **環境拡張は原則1軸ずつ。** 複数ルールを同時追加して因果を読めなくしない

## 結果を変えない変更と、変える変更を区別する

V1.2光場は意図的な世界ルール変更。
V1.2.1可視化・観測は結果不変変更。

高速化・リファクタリング・観測機能追加は、同一数値実行環境で科学結果を変えてはならない。

```bash
uv run python tools/golden.py
uv run python tools/verify_vs_ref.py --ref 18137b5
```

`tools/verify_vs_ref.py` は異OS間の一致を保証するものではない。同一数値実行環境内で旧実装と新実装を比較する。

意図的に世界モデルを変更する場合は、バージョン境界として理由を記録し、必要なgolden指紋更新を明示する。

## 開発フロー

- 原則ブランチを切り、PRで提出する
- 変更後は `uv run pytest tests` を全通しする
- 結果不変変更では結果不変性確認も通す
- パラメータ調整の根拠をPR説明に残す
- 意味のある実験結果は `experiments/` に保存する

## 実験結果の残し方

`runs/` は日常実行用。残す価値のある実験は:

```text
experiments/expNN_<名前>/
├─ config.json / meta.json
├─ stats.csv
├─ events.csv
├─ snapshots/
├─ environment/
├─ spatial/
├─ plots/
└─ NOTES.md
```

再現にはseedだけでなくConfig、コード版、依存関係、数値実行環境が必要。`meta.json` にOS / architecture / Python / NumPy / git SHA等を保存する。

## 技術スタック

Python 3.12 / uv / numpy / pygame-ce / matplotlib / pytest。

```bash
python -m uv run pytest tests
python -m uv run python main.py --seed 42
python -m uv run python main.py --headless --ticks 20000 --seed 42
python -m uv run python tools/plot_run.py runs/<run_id>
```
