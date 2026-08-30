# Exp07 実行手順 — V1.3 chemical source成立範囲

更新: 2026-08-30

> **この文書を Exp07 実行時の正本とする。**
>
> 条件・判定の正本は `docs/Exp07_実験計画.md`、モデルの正本は
> `docs/V1.3_化学資源モデル仕様.md`。本書は「どう回すか」だけを扱う。
> 実行環境は **GitHub Actions (ubuntu-24.04 / Linux)**。
> 本番は 8 flux × 3条件 × seed 1-10 = **240 run × 120,000 tick** を
> 1回の起動で投入し、結果を見て条件を変更せず完遂する。

関連:
- Issue #37
- `docs/Exp07_実験計画.md` / `docs/V1.3_化学資源モデル仕様.md`
- `docs/バージョニング方針.md` (世界バージョン境界の扱い)

---

## 1. V1.3 で変わったこと

chemical は「地質sourceから一定fluxで供給され、局所stockとして滞留し、
一次の環境損失で失われる」一次Energy sourceになった。

```text
L  = chem_loss_frac * C     環境損失
C1 = C - L
C2 = C1 + S                 地質source (生物にもstockにも依存しない)
```

**stockに上限 (capacity) は無い。** source全量が流入し、損失項だけで
有限化する。生物不在の平衡は `C* = S / chem_loss_frac`。

これにより、実際に世界へ入るchemicalは常に `n_vents × chem_vent_flux` で、
vent配置 (seed) に依存しない。上限クリップを持つと、端で欠けたventや
重複セルで1セルあたりsourceが上がって超過分が捨てられ、flux 64 では
seed依存で最大10.8%のsourceが失われる。成立境界の判定が歪むため廃止した。

V1.2以前とは結果が一致しない (意図的な世界バージョン境界)。
V1.2の再現には `v1.2-final` を使う。

## 2. 条件Config

振る世界パラメータは `chem_vent_flux` **だけ**。

| 条件 | 記号 | 初期ゲノム | 初期配置 |
|---|---|---|---|
| `c_chem_vent` | C | chemical_absorption=2.0 固定 | vent上 |
| `b_ancestor_vent` | B | 現行祖先 | vent上 |
| `d_chem_random` | D | chemical_absorption=2.0 固定 | ランダム |

A (Ancestor/Random) は進化bootstrapと空間accessの障害を同時に含み
診断情報量が低いため省略する (計画 §5)。

Config は 8 flux × 3条件 = 24個。**手書きせず生成する。**

```bash
uv run python tools/make_exp07_configs.py          # configs/exp07/ を生成
uv run python tools/make_exp07_configs.py --check  # 生成物と一致するか確認
```

`tests/test_exp07_configs.py` が「fluxと診断条件以外は24 Configすべてで同一」
を機械的に守る。workflow の setup ジョブも起動前に `--check` を実行する。

## 3. 実行前チェック

```bash
git pull --ff-only
git status --short            # 空であること
git rev-parse HEAD            # 記録する
uv run pytest tests -q
uv run python tools/verify_vs_ref.py --ref ea78125   # V1.3内での結果不変
uv run python tools/make_exp07_configs.py --check
```

## 4. 起動

GitHub → Actions → **Exp07** → Run workflow。

### Pilot (先に実施)

| 入力 | 値 |
|---|---|
| `fluxes` | `4,16,64` |
| `conditions` | `c_chem_vent,b_ancestor_vent,d_chem_random` |
| `seeds` | `1` |
| `ticks` | `5000` |
| `render_spatial` | `true` |

9 run。**実装健全性だけ**を確認する (計画 §7)。

- 総source が設定値と一致する
- stock更新式・台帳に不整合がない
- light flow が0
- Config / placement / fixed gene が意図どおり
- 出力・crashなし

Pilotの生物学的結果を見てflux範囲を変更しない。

### 本番

| 入力 | 値 |
|---|---|
| `fluxes` | `4,8,12,16,24,32,48,64` |
| `conditions` | `c_chem_vent,b_ancestor_vent,d_chem_random` |
| `seeds` | `1-10` |
| `ticks` | `120000` |
| `upload_events` | `false` (容量。死因はstats.csvの deaths_* で追える) |
| `render_spatial` | `true` |

240 run (matrix上限256以内)。`max-parallel: 20` で12波。

**240 runを1回で投入する。** 途中結果を見てflux範囲・条件・tick数・
`chemical_absorption=2.0` を変更しない。

#### 規模の目安

Actionsベンチ (ms/tick ≒ −2.14 + 0.0391×個体数) から:

| 定常個体数 | 120,000 tick の所要 |
|---:|---:|
| 100 | 約 4分 |
| 300 | 約 19分 |
| 650 | 約 47分 |

絶滅runは数秒〜数分で終わる。実時間は **2〜5時間** を見込む。
run jobの timeout は 350分 (GitHub-hostedの6時間上限内)。
成果物は snapshot 120枚/run で **1〜2 GB** 規模になるため、collect の
timeout を180分に取ってある。

## 5. 出力と停止条件

### run ごと (成果物 `exp07-flux<NN>-<条件>-seed<N>`)

```text
config.json / meta.json / stats.csv / lineages.csv
snapshots/     environment/     spatial/chemical/ (PNG + GIF)
```

絶滅・`max_population_halt` 到達はいずれも**測定結果**であり、
run ジョブも health_check も止まらない。

### collect ジョブ

| チェック | 停止条件か |
|---|---|
| `check_env.py` 数値実行環境の同一性 | **停止** |
| `health_check.py` run数・環境・SHA (早期終了は警告) | **停止** (早期終了以外) |
| `check_exp07.py` 光0・実効source・初期stock・配置・chem固定・対応配置 | **停止** |
| `summarize_exp07.py` 生存境界・chemical収支・B到達・D空間access | 情報 |
| `run_batch.py --aggregate` seed間集計 | 情報 |

`check_exp07.py` を停止条件にしているのは、診断条件が崩れていたら
結果をどう読んでも意味がないため。生データの退避を終えてから落とす。

## 6. 読み方 (計画 §9)

1. **段階1 — C**: chemical生態そのものが120k持続する flux 境界
2. **段階2 — B**: C成立域で祖先からのbootstrap
3. **段階3 — D**: C成立域でvent探索・空間access

**Bは生存/絶滅の二値で読まない。** 祖先ゲノム・matter 0.8・静止の収支は

```text
維持費 = 0.320 + 0.04 * chemical_absorption
吸収   = 0.40  * chemical_absorption
```

で、黒字化は `chemical_absorption ≈ 0.89` (実効1.0前後)。初期値0.3の
約3倍であり、**Bの絶滅はsource flux不足の証拠にならない**。
`summarize_exp07.py` が到達マイルストーン (0.5 / 0.9 / 1.2 / 1.5 / 2.0) と
初回tickを出すので、そちらで読む。

`max_population_halt` 到達は失敗ではなく供給過多側の科学結果。

最終個体数が20未満のrunは「絶滅していないだけ」の可能性があるため、
summarizerが注記を出す。生存としてカウントする前に確認する。

## 7. 実行後

1. Summary で env_check / health_check / 診断条件チェック / 要約を確認
2. 生データを退避 (外部ストレージ or `exp07-rawdata` 成果物)
3. `experiments/exp07_<日時>/` に要約とマニフェストを保存
4. 計画 §8 の評価項目を確認 (生態成立性 / chemical収支 / 進化bootstrap /
   空間access / 参考形質)
5. §10 に従って恒久 `chem_vent_flux` の候補を決める
   (「光と同程度」に合わせない)
6. `docs/次の実験計画.md` と Issue #37 を更新
7. C/B/D が成立する flux が見つかって初めて、V1.1互換 vertical 光 +
   V1.3 chemical source の同居実験へ進む

## 附録A. ローカル実行 (動作確認用)

```bash
for f in 04 16 64; do
  for c in c_chem_vent b_ancestor_vent d_chem_random; do
    uv run python tools/run_batch.py --seeds 1 --ticks 5000 --workers 1 \
      --config configs/exp07/exp07_flux${f}_${c}.json \
      --out runs/exp07/flux${f}_${c}
  done
done
uv run python tools/check_exp07.py runs/exp07 --seeds 1
uv run python tools/summarize_exp07.py runs/exp07 --ticks 5000
```

Actionsと数値実行環境が異なるため、ローカル結果とActions結果を混ぜて解析しない。
