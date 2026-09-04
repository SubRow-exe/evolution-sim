# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に現在の正本を必ず読むこと。

---

# 1. 最優先参照順

1. `docs/V1.9_現状ステータス.md` — **現在地・権限**
2. `docs/V1.9_検証実装仕様_物理スケール版.md` — **CURRENT IMPLEMENTATION SPEC**
3. `docs/Exp15_V1.9_実験計画案.md` — **implementation-ready Exp15 / Phase 0 gate**
4. `docs/V1.9_iLUCA再設計仕様.md` — V1.9機構設計
5. PR #67 `docs/V1.9_実装報告.md` — mechanism checkpoint
6. `docs/V1.9_物理スケール再校正方針.md` — 方針転換の背景
7. Issue #68 — Opus 5レビュー履歴
8. `docs/次の実験計画.md`
9. `docs/V1.8_総括.md`
10. `docs/環境因子追加・校正方針.md`

旧arbitrary numeric referenceより`V1.9_検証実装仕様_物理スケール版.md`を優先する。

---

# 2. 現在地

```text
V1.8                       CLOSED
V1.9 mechanism design      CLOSED
PR #67 mechanism patch     DONE / CHECKPOINT
V1.9 physical patch        IMPLEMENTATION AUTHORIZED / CURRENT TASK
Exp15 Phase 0              NEXT
Exp15 formal Phase A/B     BLOCKED UNTIL PHASE 0 PASS
```

---

# 3. V1.9検証baselineの重要判断

```text
1 agent = 1 cell
reference dry mass = 0.28 pgDW
1 matter unit = 0.28 pgDW
physical time unit = second
biology dt = 10 s
world = 20 mm x 20 mm
40x40 / dx=0.5 mm / depth=0.5 mm
H2 source = 4 point cells, resolved concentration 1 mM
D_H2 = 5e-9 m2/s
H2 exchange tau = 900 s
diffusion = CFL-safe automatic subcycling
H2 uptake = physical Michaelis-Menten
Energy = J / power = W
H2 usable Energy = 3750 J/mol
baseline maintenance from 0.116 mmol ATP/(gDW h)
Matter growth cost from Y_ATP=10 gDW/mol ATP
binary fission = 50:50 Matter
Exp15 damage axes = OFF
```

`cells_per_agent` / super-agentは導入しない。
H2 depletion competitionはExp15成功条件にしない。

Exp15の主要圧はH2-rich / H2-poor spatial Energy heterogeneity。

---

# 4. 維持するV1.9機構

```text
17 genes
1-pool Energy
storage_capacity
runway / starvation_horizon
reproduction_horizon
H2 explicit / CO2 implicit
uniform random spawn
PHOTOTROPHY structural innovation gate
PREDATION locked
conservation / determinism / Recorder
```

未来情報を使わない。

```text
NG: 日没予測
NG: 将来Energy収益予測
OK: current Energy / current P_full -> runway
```

---

# 5. 現在AIが実施してよいこと

PR #67 branchを土台に:

```text
physical scaling patch implementation
unit/integration tests
Energy/Matter/H2 conservation
same-seed determinism
H2 diffusion subcycling
physical Recorder
Phase 0 harness implementation
Phase 0 P0-A/B/C/D execution
implementation/preflight report
```

ここまでは人間の追加承認なしで進めてよい。

---

# 6. HARD STOP

Phase 0 PASS前にformal Exp15 Phase A/Bをdispatchしてはいけない。

また以下は禁止:

- PASSさせるためのparameter sweep
- Phase 0 FAIL時の自動tuning
- cells_per_agentの勝手な導入
- phototrophy formal run
- temperature / oxygen / pH等の新軸追加
- historical experimentの書き換え

Phase 0 FAIL時は結果と原因候補を報告してSTOP。

---

# 7. Phase 0 gate

正本: `docs/Exp15_V1.9_実験計画案.md`

```text
P0-A no-organism H2 field
P0-B radial fixed single-cell Energy balance
P0-C random movement exposure
P0-D dt=2.5/5/10 s convergence
```

最重要:

> world内に net power positive region と negative region の両方が存在すること。

全域positive / 全域negativeならformal Exp15へ進まない。

---

# 8. 絶対設計原則

- 適応度関数を直接置かない
- 特定生態型への固定bonus/penaltyを置かない
- 将来予測を埋め込まない
- 保存則を破らない
- Recorderをsimulationへフィードバックしない
- same-seed determinism
- capability originをcontinuous mutationで迂回しない
- historical experimentを書き換えない
- 生存するようarbitrary値を自動校正しない
- physical unit化できる量はSI/physical semanticsを優先する

---

# 9. 実行順

```text
1. PR #67 branchへphysical patch
2. tests / conservation / determinism
3. Phase 0 harness
4. P0-A/B/C/D run
5. report
6. STOPして人間レビュー
7. PASSならExp15 Phase A dispatch
```
