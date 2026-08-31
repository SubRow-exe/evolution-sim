# Exp08 実測NOTES — V1.4 一次Energy吸収則の校正

実行日: 2026-08-31
GitHub Actions: `33349767307` / Exp08 run #2
commit: `b7d533c0ae7eb3d2158bb5156821eeeddc3b2402`
規模: 90 run（9条件 × 10 seed）、最大60,000 tick
workflow: success

詳細な解釈の正本は `docs/Exp08_結果考察.md`。

## 健全性

- 90 runすべて同一Linux / Python / NumPy環境
- 90 runすべて同一commit
- 条件ごとのrun数10
- 固定遺伝子は全期間で分散0
- 診断条件 1059項目すべてOK
- 早期終了10 runはすべて光吸収速度係数1.0での絶滅結果

## Phase A 光単独

`light_uptake_coef` = 光吸収速度係数。個体の`light_absorption`能力を実吸収上限へ変換する世界側の係数。

L0 (`light_absorption=0.3`固定):

| 光吸収速度係数 | 生存 | 最終個体数中央値 | 光利用率中央値 |
|---:|---:|---:|---:|
| 1.0 | 0/10 | 0 | 2.24% |
| 1.5 | 10/10 | 115 | 4.01% |
| 2.0 | 10/10 | 1,169 | 25.07% |
| 3.0 | 10/10 | 1,540 | 30.18% |
| 4.0 | 10/10 | 2,228 | 36.70% |

L2 completed light (`light_absorption=2.0`, 光吸収速度係数2.0): **10/10生存**、最終個体数中央値5,189。

## Phase B chemical単独

`chem_vent_flux` = 1つのchemical噴出口が1 tickに供給するEnergy量。

| 1 vent供給量 | 生存 | 最終個体数中央値 | source利用率中央値 | 平均stock中央値 |
|---:|---:|---:|---:|---:|
| 8 | 10/10 | 50 | 79.2% | 76.4 |
| 16 | 10/10 | 118 | 96.1% | 26.4 |
| 24 | 10/10 | 203 | 97.7% | 27.4 |

## 判定

- 光吸収上限は生態結果へ明確に作用した
- V1.4後も完成光型・完成chemical型は単独成立可能
- chemical生態はsurface則・公平配分後も頑健
- V1.4吸収メカニズムはExp08の範囲で妥当性確認を通過
- 恒久default値はまだ未決定

生データはGoogle Drive / GitHub Actions artifactに保存。
