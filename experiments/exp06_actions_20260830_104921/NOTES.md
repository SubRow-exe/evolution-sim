# Exp06 — chemical利用経路の成立性診断

実行日: 2026-08-30
実行環境: GitHub Actions / ubuntu-24.04
Actions run: https://github.com/SubRow-exe/evolution-sim/actions/runs/33307351442
コード: `bdcb825` (main)
正本: `docs/Exp06_実験計画.md` / 手順: `docs/Exp06_実行手順.md` / Issue #34

## 1. 実行条件 (事前登録どおり・変更なし)

```text
全条件 light_pattern=uniform / light_max=0.0
A a_ancestor_random  現行祖先        / ランダム配置
B b_ancestor_vent    現行祖先        / vent上配置
C c_chem_vent        chem 2.0固定    / vent上配置   (positive control)
D d_chem_random      chem 2.0固定    / ランダム配置
seed 1-10 / 10,000 tick / 4条件 × 10 = 40 run
stats_interval=20 / snapshot_interval=1000
```

## 2. 診断条件の成立確認 — 全項目Green

| 項目 | 結果 |
|---|---|
| 40 run 完走 | success (絶滅による早期終了は測定結果) |
| 光0 | 全40 runで累積光供給=0・累積 light flow=0 |
| vent配置 | B/C の全個体が chem_mask セル上から開始 |
| chem固定 | C/D は初期・最終snapshotとも厳密に 2.0 |
| 対応配置 | 同一seedで B/C・A/D の初期配置が一致 |
| 環境・SHA | 40 run すべて単一 |

判定: `check_exp06.py` → OK / `health_check.py` → 停止条件に非該当

## 3. 結果 — **4条件すべて 0/10 生存 (全滅)**

| 条件 | 生存 | 絶滅tick (範囲) | ピーク人口 | chem_flow累積 | chem_abs最大 | vent滞在最大 |
|---|---|---|---|---|---|---|
| A 祖先/ランダム | 0/10 | 91〜154 | 179〜194 | 21〜108 | 0.300〜0.311 | 0.12〜1.00 |
| B 祖先/vent | 0/10 | 148〜152 | 186〜190 | 1,928〜2,112 | 0.299〜0.302 | 1.00 |
| C chem2.0/vent | 0/10 | 136〜210 | 199〜200 | 1,674〜1,940 | 2.000 | 1.00 |
| D chem2.0/ランダム | 0/10 | 103〜234 | 179〜194 | 45〜584 | 2.000 | 1.00 |

初期個体数100に対しピーク190〜200 — **どの条件でも一度は倍増してから崩壊**している。
初期エネルギー (50 E/個体) とvent初期ストックを子へ変換し尽くした時点で餓死に転じる。

祖先条件 (A/B) で `mean chemical_absorption` が 0.5 / 1.0 / 1.5 に到達したseedは **0/10**。
chemical利用能力が進化的に上昇し始める気配はなく、絶滅までの100〜150 tickでは
初期値0.3のまま推移した。

B では10 seedすべてが tick 148〜152 に集中して絶滅しており、
vent上に置いても結果はseedにほぼ依存しない。

C (positive control) は chemical を最も多く消費 (1,674〜1,940 E) し、
vent滞在率1.0で最大の人口 (199〜200) に達したが、それでも 136〜210 tick で全滅した。

生存と絶滅の混在は1条件も無いため、事前規定の「seed 11-20 追加」条件には該当しない。

## 4. 切り分け — §8 ケース1

> **C (chem-adapted / vent) も全滅した。**
> 現行の chemical 資源量・供給速度・生理コストの組合せでは、
> chemical依存生態そのものが標準初期個体群から成立しない。

計画 §2 の見積と整合する:

```text
光 (V1.1)            : 1,248 E/tick
chemical 理論上限     : 約 32.5 E/tick
                       (chem_capacity=50, chem_regen=0.05,
                        1 vent cell最大 0.625 E/tick × 約52セル)
```

供給規模で約38倍の非対称があり、B/C が消費した約1,900〜2,100 E は
vent の初期ストック (約52セル × 25 E ≒ 1,300 E) と回復分をほぼ使い切った量に相当する。
つまり**ストックは食べ尽くせるが、フローが集団を養えない**。

### この結果の帰結

計画 §10 のとおり、以下の解釈は**成立しない**:

> 「複数のエネルギー利用戦略が十分に進化可能な世界で、光利用型が競争に勝った」

V1.1〜Exp05で観測された光利用優勢は、競争の結果ではなく
**モデル設計上の到達可能性の非対称**を含む。V1.1総括の該当解釈は修正が必要。

Exp03〜05で観測された数値・sweep・形質変化そのものは引き続き有効であり、
同じ光利用経路内での比較 (Exp04のsweep促進因子解析など) も有効なまま。

## 5. 次に見直す候補 (1軸ずつ)

§8 ケース1が指す候補:

- `chem_capacity` / `chem_regen` — ventのフロー供給量
- vent の面積・数 (`n_vents` / `vent_radius_cells`)
- chemical uptake と維持費の収支
- `initial_population` と局所carrying capacity

**A/B が chemical_absorption を上げる前に絶滅している**ため、
初期 `chemical_absorption` や `sensory_range` の見直しは
「chemical生態が成立する資源量」を先に確保してからでないと評価できない。
ケース2/3の切り分け (進化上の谷 / 探索ボトルネック) は、
C が生存する資源設定の下で再度診断する必要がある。

これは世界ルール・初期パラメータの変更にあたるため、
`docs/バージョニング方針.md` に従い次の世界バージョン (V1.3) として扱う。

光総量0.75/0.50系列は、chemical経路の扱いが決まるまで引き続き保留。

## 6. 保存物

- 生データ: `gdrive:evolution-sim/exp06_actions_20260830_104921/`
  (4条件 × 各0.7 MB、tar.gz 合計約2.1 MB)
- チェックサム・マニフェスト・解析出力: Actions成果物 `exp06-summary` (90日保持)
  - `exp06_<条件>/MANIFEST.md` (run一覧・SHA256)
  - `summary.txt` / `env_check.txt` / `conditions.txt` / `health.txt`
- 本NOTESの数値は collect ジョブの出力に基づく

## 7. 注記

- 全条件が数百tickで絶滅したため、10,000 tick 実行の大半は空振りである。
  次に同種の診断を行う場合は tick数を下げてよいが、
  **今回の事前登録条件は変更していない**。
- `summarize_exp06.py` の「中間人口」列 (tick 5,000時点) は
  全runが既に絶滅しているため 0 になっている。
