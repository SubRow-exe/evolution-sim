# Exp08 実行手順 — V1.4 吸収則の校正

更新: 2026-08-31

> **この文書を Exp08 実行時の正本とする。**
>
> 条件・判定の正本は `docs/Exp08_実験計画.md`、モデルの正本は
> `docs/V1.4_一次エネルギー吸収仕様.md`。本書は「どう回すか」だけを扱う。
> 実行環境は **GitHub Actions (ubuntu-24.04 / Linux)**。
> 本番は Phase A 60 run + Phase B 30 run = **90 run × 60,000 tick** を
> 1回の起動で投入し、結果を見て条件を変更せず完遂する。

関連:
- Issue #39
- `docs/Exp08_実験計画.md` / `docs/V1.4_一次エネルギー吸収仕様.md`
- `docs/バージョニング方針.md` (世界バージョン境界の扱い)

---

## 1. V1.4 で変わったこと

環境フィールド (光・化学・無機栄養) からの直接吸収が、
**有効表面積 × 個体能力 × 健全度** で決まる個体上限を持つようになった。

```text
A_eff  = matter^(2/3)
demand = 係数 × absorption遺伝子 × A_eff × health   (Energy空き容量でcap)
```

セルごとに全個体のdemandを先に求め、供給が足りなければ需要比例で配分する。
総取得は `min(供給, 総需要)`。総需要の合算に `math.fsum` を使うので、
個体リスト順を変えても配分はビット単位で同じ。

主な帰結:

- 低い `light_absorption` の単独個体がセル光を全取得できなくなった
  (V1.3以前の設計ミス)
- chemical の先着bias (個体リスト順の有利不利) が消えた
- 光/化学/無機栄養がすべて**移動後**のセルを参照する
  (V1.3以前は光だけ移動前セル)
- 未利用光が増え、`flow_light_cum / light_supply_cum` は大幅に下がる
  — **これは意図した挙動であり異常ではない**

V1.3以前とは結果が一致しない (意図的な世界バージョン境界)。
V1.3の再現には `v1.3-final` を使う。CIの結果不変性基準refは `5aca88e`。

## 2. 条件Config

振る世界パラメータは、Phase Aでは `light_uptake_coef` **だけ**、
Phase Bでは `chem_vent_flux` **だけ**。

| Phase | 条件 | Config | 内容 |
|---|---|---|---|
| A | L0 | `exp08_a_l0_coef{1p0,1p5,2p0,3p0,4p0}.json` | 祖先 / `light_absorption`=0.3固定 |
| A | L2 | `exp08_a_l2_coef2p0.json` | 完成光型 / `light_absorption`=2.0固定 (1水準) |
| B | — | `exp08_b_flux{08,16,24}_chem.json` | 光0 / `chemical_absorption`=2.0固定 / vent配置 |

Phase Aは `chem_vent_flux=0.0` で光単独にするが、**`n_vents=4` は維持する**。
`n_vents=0` にするとvent生成の乱数消費が変わり、Phase Bと系列が揃わなくなる。

L2を1水準に絞っているのは、matter≈0.8では `light_absorption=2.0` の
demand (`1.72×coef`) が `light_max=1.2` を常に超え、係数を振っても
供給律速で判別力が出ないため (計画 §4.3)。判別はL0側で行う。

Config は 9個。**手書きせず生成する。**

```bash
uv run python tools/make_exp08_configs.py          # configs/exp08/ を生成
uv run python tools/make_exp08_configs.py --check  # 生成物と一致するか確認
```

`tests/test_exp08_configs.py` が「振る対象と診断条件以外は同一」を機械的に
守る。workflow の setup ジョブも起動前に `--check` を実行する。

## 3. 実行前チェック (計画 §9 の停止条件)

```bash
git pull --ff-only
git status --short            # 空であること
git rev-parse HEAD            # 記録する
uv run pytest tests -q
uv run python tools/verify_vs_ref.py --ref 5aca88e   # V1.4内での結果不変
uv run python tools/make_exp08_configs.py --check
uv run python tools/bench_v14_uptake.py              # Phase 0 決定論ベンチ
```

Phase 0 ベンチ (`tools/bench_v14_uptake.py`) は進化runを使わず、

- `A_eff = matter^(2/3)` のスケーリング
- light / chemical の個体吸収ceiling (同一表に併記)
- 維持費・修復費・初期Energy・繁殖閾値との関係
- 1/5/20/100個体の密度競争 (供給十分/不足)
- 個体順を reverse / shuffle しても配分が変わらないこと
- 無機栄養の Matter余地 / 同化Energy による事前cap

を検査し、1件でも落ちれば非ゼロ終了する。workflow の setup でも実行する。
並べ替えには `Simulation.rng` を消費しない別RNGを使う。

**Phase 0 は算術と実装の確認であり、その数値を見て Phase A/B の条件を
変更しない** (計画 §3.5)。実装バグが見つかった場合のみ直して再実行する。

## 4. 起動

GitHub → Actions → **Exp08** → Run workflow。

### Pilot (先に実施)

| 入力 | 値 |
|---|---|
| `cases` | `a_l0_coef1p0,a_l0_coef4p0,a_l2_coef2p0,b_flux08_chem,b_flux24_chem` |
| `seeds` | `1` |
| `ticks` | `5000` |
| `render_spatial` | `true` |

5 run。**実装健全性だけ**を確認する。

- Phase A で chemical flow が0 / Phase B で light flow が0
- `light_uptake_coef` と固定遺伝子が意図どおり
- vent配置・実効source・初期stock (Phase B)
- 台帳・出力・crashなし

Pilotの生物学的結果を見て係数やfluxを変更しない。

### 本番

| 入力 | 値 |
|---|---|
| `cases` | `a_l0_coef1p0,a_l0_coef1p5,a_l0_coef2p0,a_l0_coef3p0,a_l0_coef4p0,a_l2_coef2p0,b_flux08_chem,b_flux16_chem,b_flux24_chem` (default) |
| `seeds` | `1-10` |
| `ticks` | `60000` |
| `upload_events` | `false` (容量。死因はstats.csvの deaths_* で追える) |
| `render_spatial` | `true` |

90 run (matrix上限256以内)。`max-parallel: 20` で5波。

**90 runを1回で投入する。** 途中結果を見て係数・flux・tick数・
固定遺伝子を変更しない。

#### 規模の目安

Actionsベンチ (ms/tick ≒ −2.14 + 0.0391×個体数) から:

| 定常個体数 | 60,000 tick の所要 |
|---:|---:|
| 100 | 約 2分 |
| 300 | 約 10分 |
| 650 | 約 23分 |

絶滅runは数秒〜数分で終わる。実時間は **1〜3時間** を見込む。
run jobの timeout は 350分、collect は 180分。

## 5. 出力と停止条件

### run ごと (成果物 `exp08-<case>-seed<N>`)

```text
config.json / meta.json / stats.csv / lineages.csv
snapshots/     environment/
spatial/light/ (Phase A) または spatial/chemical/ (Phase B)
```

絶滅は**測定結果**であり、run ジョブも health_check も止まらない。

### collect ジョブ

| チェック | 停止条件か |
|---|---|
| `check_env.py` 数値実行環境の同一性 | **停止** |
| `health_check.py` run数・環境・SHA (早期終了は警告) | **停止** (早期終了以外) |
| `check_exp08.py` 光/chemicalの排他・係数・遺伝子固定・vent配置・実効source | **停止** |
| `summarize_exp08.py` Phase A/B の校正表 | 情報 |
| `run_batch.py --aggregate` seed間集計 | 情報 |

## 6. 読み方 (計画 §8)

### Phase A

1. **L2 (positive control)** が成立するか。不成立なら光供給・係数・維持費・
   実装を再監査する
2. **L0 が係数に感受性を持つか**。全係数でほぼ同じなら `light_absorption`
   または demand 実装が効いていない疑い
3. 係数に応じて赤字〜黒字の人口動態差が出れば新光吸収則は機能している

`light_uptake_coef=1.0` の一時生存は初期Energy (50 E) と開始直後の繁殖で
説明できるため、**長期trendで読む**。break-even近傍の係数は世代時間が
長いので、生存/絶滅の二値ではなく `推移` 欄と中間tickの人口を見る。

光利用率がV1.3以前より大幅に下がるのは新仕様の意図した結果である。

### Phase B

- 8/16/24 で成立するか (surface則・公平配分の後も頑健か)
- flux によって population / stock / 利用率 / 個体吸収量が系統的に変わるか

`matter^(2/3)` は matter<1 では chemical 吸収を**増やす**方向なので、
Phase B が Exp07 と同等以上に成立するのは想定内。
**flux 8 の不安定さを default 引き上げの根拠にしない** (計画 §5.2)。
16/24 を候補にするのは「vent局所供給密度を光帯 (0.36〜1.2 E/tick/cell) と
同等以上にする」という事前の設計目標による。

### 結論しないこと (計画 §10)

光とchemicalの進化的優劣 / chemical祖先bootstrap / 多様性 / 動物的進化 /
異種刺激を同時に感じたときの行動選択。

## 7. 実行後

1. Summary で env_check / health_check / 診断条件チェック / 要約を確認
2. 生データを退避 (外部ストレージ or `exp08-rawdata` 成果物)
3. `experiments/exp08_<日時>/` に要約とマニフェストを保存
4. 計画 §7 の選定原則に従って `light_uptake_coef` と `chem_vent_flux` の
   恒久default候補を決める (「光を弱くしたいから」で選ばない)
5. `docs/次の実験計画.md` と Issue #39 を更新
6. 必要なら `chem_uptake` を独立1軸で追加診断する
7. 光+chemical同居の前に、未来予測を使わない異種刺激の無次元比較則を
   別途事前登録する

## 附録A. ローカル実行 (動作確認用)

```bash
for c in a_l0_coef2p0 a_l2_coef2p0 b_flux08_chem; do
  uv run python tools/run_batch.py --seeds 1 --ticks 5000 --workers 1 \
    --config configs/exp08/exp08_${c}.json \
    --out runs/exp08/${c}
done
uv run python tools/check_exp08.py runs/exp08 --seeds 1
uv run python tools/summarize_exp08.py runs/exp08 --ticks 5000
```
