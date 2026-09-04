# Exp16 V1.9 環境ロバストネス実験計画

更新: 2026-09-04
状態: **PREREGISTERED / DISPATCH AUTHORIZED**

## 1. 目的

Exp15 Attempt 2で成立したfixed iLUCAを変更せず、H2環境の強さ・輸送・空間配置に対する生存、成長、世代交代のロバストネスを調べる。

これは「生存する環境値を探して採用する」ためのadaptive tuningではない。条件は実行前に固定し、絶滅条件を含めて全結果を保存する。

## 2. 固定する生物側

Exp15 Attempt 2 (`ee9f181612b24c39d5bd092f8cd0310dfcde2cc7`) のLUCA-like proxyを固定する。

```text
arm = A
all 17 continuous genes fixed
initial_jitter_sigma = 0
phototrophy innovation = 0
predation innovation = locked/OFF
maintenance-first growth allocation fixed
H2 uptake kinetics fixed
ATP / maintenance / growth yield fixed
initial_population = 100
initial_matter = 0.50
```

## 3. 基準環境

```text
H2 source concentration = 10 mM
H2 diffusion coefficient = 5.0e-9 m2/s
H2 exchange timescale = 900 s
source layout = square (10,10),(10,30),(30,10),(30,30)
4 source cells
20 mm x 20 mm world
0.5 mm grid cell
0.5 mm effective depth
```

## 4. 条件

他の値はすべて基準のまま、原則として1軸ずつ変更する。

| condition | H2 source | tau | D [m2/s] | layout |
|---|---:|---:|---:|---|
| `h2_1mM` | 1 mM | 900 s | 5e-9 | square |
| `h2_3mM` | 3 mM | 900 s | 5e-9 | square |
| `h2_6mM` | 6 mM | 900 s | 5e-9 | square |
| `baseline_10mM` | 10 mM | 900 s | 5e-9 | square |
| `h2_15mM` | 15 mM | 900 s | 5e-9 | square |
| `exchange_fast_300s` | 10 mM | 300 s | 5e-9 | square |
| `exchange_slow_3600s` | 10 mM | 3600 s | 5e-9 | square |
| `diffusion_low_2p5e9` | 10 mM | 900 s | 2.5e-9 | square |
| `diffusion_high_1e8` | 10 mM | 900 s | 1e-8 | square |
| `layout_cross` | 10 mM | 900 s | 5e-9 | cross |
| `layout_cluster` | 10 mM | 900 s | 5e-9 | cluster |

Layouts:

```text
square  = (10,10),(10,30),(30,10),(30,30)
cross   = (20,10),(10,20),(30,20),(20,30)
cluster = (17,17),(17,23),(23,17),(23,23)
```

source数は4で固定し、geometryだけを比較する。

## 5. 実行数

```text
11 conditions
x 5 seeds (16001-16005)
x 10 physical days
= 55 runs
```

matrixはfail-fastしない。ある条件が絶滅しても他条件を止めない。

## 6. 主要観測量

- final population
- max population
- extinction / max_population_halt / duration_complete
- max generation
- generation interval
- population AUC
- final mean runway
- starvation active fraction
- biological H2 uptake
- H2 source influx
- biological uptake / source influx
- Energy ledger residual
- Matter ledger residual

## 7. 解析原則

1. baseline_10mMを中心に各1軸条件と比較する。
2. populationだけでなくgenerationとH2 utilizationを同時に見る。
3. max_population_haltは「成功」ではなくcensored high-growth outcomeとして記録する。
4. extinctionは削除しない。
5. ledger failureは生物学的結果として解釈せずimplementation failureとして分離する。
6. Exp16結果を見て同じExp16のconditionを追加・変更しない。追加試験が必要なら別attempt/experimentとして事前登録する。

## 8. version

同じV1.9 equations / state semanticsのConfig比較であり、world-rule変更ではないため**V1.9のまま**。
