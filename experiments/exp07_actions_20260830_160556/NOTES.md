# Exp07 — V1.3 chemical source単独の成立性診断

実行日: 2026-08-30
実行環境: GitHub Actions / ubuntu-24.04
Actions run: 33314539501 (本番 / success)
Pilot run: 33314023050 (9 run × 5,000 tick / success)
コード: `c94de9d`
正本: `docs/Exp07_実験計画.md` / `docs/V1.3_化学資源モデル仕様.md`

## 実行条件

```text
light = 0
chem_vent_flux = 4, 8, 12, 16, 24, 32, 48, 64 E/tick/vent
n_vents = 4
chem_loss_frac = 0.10
chem_uptake = 0.5

C: chemical_absorption=2.0固定 / vent配置
B: 通常祖先 / vent配置
D: chemical_absorption=2.0固定 / random配置

8 flux × 3条件 × 10 seed = 240 run
120,000 tick
```

## 健全性

- 240 runを同一数値環境・同一コードSHAで実行
- `check_exp07.py`: 2,432項目すべてOK
- 全runでlight供給0
- 実効chemical source = 公称 `n_vents * chem_vent_flux`
- 初期stockは `chem_source_flux / chem_loss_frac` の平衡値
- B/Cのvent配置、C/Dのchemical_absorption=2.0固定を確認
- `health_check.py`: 問題なし
- `max_population_halt`到達0件

## 生存結果

| chem_vent_flux | 世界総source | C chem2/vent | B ancestor/vent | D chem2/random |
|---:|---:|---:|---:|---:|
| 4 | 16 | 1/10* | 0/10 | 0/10 |
| 8 | 32 | 10/10 | 0/10 | 10/10* |
| 12 | 48 | 10/10 | 0/10 | 10/10 |
| 16 | 64 | 10/10 | 0/10 | 10/10 |
| 24 | 96 | 10/10 | 0/10 | 10/10 |
| 32 | 128 | 10/10 | 0/10 | 10/10 |
| 48 | 192 | 10/10 | 0/10 | 10/10 |
| 64 | 256 | 10/10 | 0/10 | 10/10 |

`*`: flux4 Cの唯一の生存runは最終5個体。flux8 Dにも最終20個体未満の境界的runあり。

## C — chemical生態成立性

- flux4は実質不成立
- flux8以上では10/10が120,000 tickまで持続
- 成立境界は世界総source 16〜32 E/tickの間
- 成立域では人口はsource量に概ね追従
- source利用率は高く、供給されたchemicalが実際に生態を支えている

したがってV1.3の「一定地質source + 局所stock + 環境損失」モデルは、完成chemical利用型の持続生態を成立させられる。
Exp06でpositive controlまで全滅した主因は、旧stock依存regen式のモデル不整合だったと強く支持される。

## B — 通常祖先からの進化bootstrap

- 全8 flux × 10 seed = 80/80絶滅
- 絶滅tickは概ね146〜153でfluxにほぼ非依存
- `chemical_absorption >= 0.5` 到達0/80
- 最大値も初期0.3付近からほぼ動かない
- 高fluxほどstockが余るだけで、祖先の吸収速度は増えない

結論:

> chemical環境そのものは成立可能だが、通常祖先はchemicalを十分利用できる形質へ進化する前にEnergy収支が破綻する。

これはsource量の問題ではなく、祖先からchemical利用型への進化bootstrap障壁である。

## D — vent探索・空間access

- flux8以上で10/10が120,000 tickまで到達
- 多くのrunで最終個体の大半がvent cellへ定着
- 完成chemical型にとってrandom配置から少なくとも一部ventへの到達は可能
- ただし最終系統数はCより大きく減り、seed間分散も大きい
- 少数founderがventへ到達して成立するbottleneckが強い
- 4 ventすべてを均等に占有するとは限らず、vent間探索は弱い可能性がある

## Exp07後の重要な再監査

Exp07によりchemical環境側の成立性は確認できたが、比較対象である光側を再監査した結果、以下の設計課題を検出した。

1. 光には個体ごとの吸収上限がなく、`light_absorption`が主にセル光量の分配比率としてしか作用していない。
2. 単独個体なら低い`light_absorption`でもセル光をほぼ全量取得できる。
3. chemicalには`chem_uptake × chemical_absorption × matter × health`の個体吸収上限があり、光との生物側ルールが非対称。
4. chemicalはstock不足時に個体リスト順で先着有利になる。
5. light/chemical/nutrientの直接吸収が概ねmatter（体積）比例で、表面積制約がない。
6. 光は移動前セル、chemical/nutrientは移動後セルを参照する実装差がある。
7. 光の供給値とchemical stockをraw値で行動比較しており、異なる単位を直接比較している。

これらをV1.4で生物側の一次Energy/資源吸収メカニズムとして再設計する。

## 過去結果の扱い

保持:
- V1.1〜Exp05で高光利用化・小型化・sweep等が実際に観測された事実
- Exp04の光利用経路内での比較

撤回/保留:

> 複数の一次Energy戦略が対等に成立可能な世界で、光利用型が競争に勝った。

chemical環境側と光吸収側の双方に構造的非対称が見つかったため、この解釈は支持しない。

## 次

V1.4で一次Energy吸収則を再設計し、Exp08で光単独・chemical単独を校正する。
