# Exp10 実行手順 — V1.6 temporal biased random walk の診断・校正

更新: 2026-08-31

> **この文書を Exp10 実行時の正本とする。**
>
> 条件・判定の正本は `docs/Exp10_実験計画案.md`、モデルの正本は
> `docs/V1.6_行動則設計案.md`、実測に基づくレビューは
> `docs/V1.6_Exp10_レビュー.md`。本書は「どう回すか」だけを扱う。
>
> Phase A は **ローカル実行** (軽量arena)、Phase B / C は
> **GitHub Actions (ubuntu-24.04)**。

関連: Issue #41 / `docs/バージョニング方針.md`

---

## 1. V1.6 で変わったこと

一次Energy (light / chemical) の行動が、winner-take-all の
「周囲の最良セルへ向かう」方式から、**現在地で感じる刺激の時間変化で
random walkの曲がり幅だけを変える**方式になった。

```text
知覚      : 連続座標で light / chemical を双線形補間 (吸収はセル単位のまま)
無次元化  : R = x / (x + K)                    K は V1.5 と同じ 1.2 / 12.3
統合      : Q = (aL*R_light + aC*R_chem) / (aL + aC)     能力加重平均
時間比較  : dQ = Q_now - Q_memory              EMA (alpha = 1 - exp(-1/tau))
移動      : sigma_eff = wander_turn_sigma * 2/(1 + exp(gain * dQ))
            heading += Normal(0, sigma_eff)
```

**dQ から「どちらへ行くべきか」は求めない。** 向きは常にrandom walkのまま。

### なぜ知覚を補間するか

field はセル内一定 (piecewise constant) で、wander速度 0.83 wu/tick に対し
`cell_size` は 20 wu ある。**1セル横断に24.1 tick**かかるので、補間しないと
memory time 1〜30 tick では約96%のtickで `dQ` が厳密に0になり、
時間比較が原理的に働かない (`docs/V1.6_Exp10_レビュー.md` A-2)。

したがってV1.6は **(i) 知覚の連続化** と **(ii) 時間比較によるturn rate変調**
の2変更を不可分に含む。Phase 0 で個別に検査する。

### なぜ能力加重平均か

単純加算だと `dQ = Σ aᵢ ΔRᵢ` になり、能力が2倍の個体は走性も2倍強くなる。
能力が「食べられる量」と「走性の強さ」を兼ねてしまい、`response_gain` が
表現型と交絡する (レビュー B-1)。加重平均なら全能力を同率で倍にしても
`Q` は変わらない。

### 定位保持の廃止

「現在セルが最良だから停止する」を一次Energyについて廃止した。
既存の満腹時停止 (`satiety_energy_frac = 0.85`) は維持する。

これによりV1.5と違い個体が実際に移動する。V1.5では `sensory_range` が
`cell_size` を下回るため自セルが常に最良となり、Exp09では移動量が
5,000 tick全区間で0だった (レビュー A-1)。

### V1.5以前との関係

V1.6は移動原理そのものを変えるためV1.5とのbit一致は要求しない。
V1.5の再現には `v1.5-final` を使う。
CI結果不変性の基準refはV1.6最初の実装commit (`e15ee67`) へ移してある。

---

## 2. 実行前の停止条件 (Phase 0)

計画 §3 の15項目。1件でも落ちたら先へ進まない。

```bash
uv run pytest tests/test_v16_temporal.py -q     # 32件
uv run pytest tests/test_conservation.py tests/test_determinism.py -q
```

とくに次の3つが「V1.6が余計なことをしていない」ことの中心。

- 一様世界では `response_gain` 0 と 256 の結果が完全一致する
  (偽biasを作らない + 観測がRNG系列を変えていない)
- `response_gain=0` なら `memory_tau` によらず結果が完全一致する
- 同一セル内の別位置に置いた2個体の吸収量が厳密に一致する
  (知覚だけ補間で、吸収はセル単位のまま)

---

## 3. Phase A — ローカル実行 (軽量arena)

死亡・繁殖・吸収・生理をすべて止めた**移動専用診断環境**で行動則だけを見る。
production world へ診断専用の特殊環境を恒久追加しないため (レビュー C-1)。

```bash
uv run python tools/arena_exp10.py \
  --out runs/exp10_phaseA --ticks 2000 --n-org 100 --seeds 20 --workers 4
```

- 5環境 (K0-K4) × 3表現型 × 13組 (tau 3/10/30 × gain 4/16/64/256 + gain=0) × 20 seed
  = **3,900 run**、実測 約2.3 core-hour (4並列で約35分)
- run同士は完全に独立なので、並列実行しても逐次と1 bitも変わらない (確認済み)

判定と最終候補の選定:

```bash
uv run python tools/summarize_exp10.py runs/exp10_phaseA --write-selection
```

事前登録のGreen条件 (計画 §4.6) をそのまま当て、Green領域から
**最小 `response_gain` → 同gainなら最短 `memory_tau`** で1組だけ選ぶ (§4.7)。
「効く中で最も弱い変更」を採る。結果を見て閾値もパラメータ候補も足さない。

選定結果を Phase B の Config 生成元へ置く:

```bash
cp runs/exp10_phaseA/phaseA_selection.json configs/exp10/
uv run python tools/make_exp10_configs.py
git add configs/exp10 && git commit
```

**手で候補を選ばない。** `make_exp10_configs.py` は
`configs/exp10/phaseA_selection.json` からしか読まない。

---

## 4. Phase B — GitHub Actions (full simulation)

Phase Aで選ばれた**1候補だけ**を通常simulationへ持ち込む。

Actions → **Exp10** → Run workflow

```text
cases  : (default のまま10条件)
seeds  : 1-20
ticks  : 10000
```

5条件 × control/treatment × 20 seed = **200 run**。

| 条件 | 光 | chemical | 表現型 |
|---|---|---|---|
| b1_light_only_lightspec | vertical | source 0 | lightspec 2.0 / 0.3 |
| b2_chem_only_chemspec | 0 | flux 16 | chemspec 0.3 / 2.0 |
| b3_mixed_lightspec | vertical | flux 16 | lightspec |
| b4_mixed_chemspec | vertical | flux 16 | chemspec |
| b5_mixed_generalist | vertical | flux 16 | generalist 1.0 / 1.0 |

- control = `response_gain = 0` (pure random walk)
- treatment = Phase A選定値
- `memory_tau` は control / treatment で同一 (行動則の軸だけを振る)

### 重要停止条件 (§5.5)

> **b2_chem_only_chemspec_treatment で 20 seed中18 seed以上が
> 10,000 tick まで生存すること。**

V1.6は定位保持を失うため、vent滞在に依存する chemical-only 生態が
壊れないかが最大の懸念である (レビュー B-4)。これを満たさない場合、
Phase A が正しくても **V1.6 default化は停止**し、世界スケール・移動則の
不整合として再検討する。

### 判定

collect job が自動で回す。

```bash
uv run python tools/check_exp10.py runs/exp10 --seeds 1-20
uv run python tools/summarize_exp10_phaseB.py runs/exp10 --ticks 10000
```

---

## 5. Phase C — 残り時間での長時間頑健性確認

Phase A / B が Green のときだけ実施する (計画 §6)。

Actions → **Exp10** → Run workflow

```text
cases  : b1_light_only_lightspec_control,b1_light_only_lightspec_treatment,
         b2_chem_only_chemspec_control,b2_chem_only_chemspec_treatment,
         b5_mixed_generalist_control,b5_mixed_generalist_treatment
seeds  : 1-20
ticks  : 30000
```

3条件 × 2行動則 × 20 seed = **120 run**。

計算時間に余裕がある場合も、**新しいパラメータ条件を増やさず**
同じ最終候補について tick を最大50,000まで延ばす (計画 §6)。

---

## 6. 計算量の目安

Exp09実測 (1 run ≈ 2.2 core-min / 5,000 tick / pop ~300) からの見積もり。

| Phase | run数 | tick | 目安 |
|---|---:|---:|---|
| Phase A (ローカル) | 3,900 | 2,000 | 約2.3 core-hour / 4並列35分 |
| Phase B | 200 | 10,000 | 約20 core-hour / 20並列1〜2時間 |
| Phase C | 120 | 30,000 | 約35 core-hour / 20並列2〜3時間 |

計画 §7 の優先順位を守る。計算時間を埋めること自体は目的にしない。

1. Phase 0 を完全に通す
2. 軽量Phase Aを十分なseedで実行
3. 最終1候補へ絞る
4. Phase B 200 run を必須実行
5. 残り時間を Phase C の seed数・tick延長へ使う

**パラメータ候補を結果を見て追加することは禁止** (計画 §11)。

---

## 7. 結果保存

`docs/実験結果保存方針.md` に従う。文字サマリーだけで終了しない。

GitHubへ:
- `docs/Exp10_結果考察.md`
- `experiments/<exp10_id>/NOTES.md`
- `figures/` (計画 §12 の6種 + `README.md`)

全生データはGoogle Drive / Actions artifactへ。
