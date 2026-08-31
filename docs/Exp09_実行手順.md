# Exp09 実行手順 — V1.5 異種一次Energy刺激比較則の診断

更新: 2026-08-31

> **この文書を Exp09 実行時の正本とする。**
>
> 条件・判定の正本は `docs/Exp09_実験計画.md`、モデルの正本は
> `docs/V1.5_異種刺激比較仕様.md`、採否判断は `docs/V1.5_Exp09_レビュー判断.md`。
> 本書は「どう回すか」だけを扱う。実行環境は **GitHub Actions (ubuntu-24.04)**。
> 本番は 5条件 × seed 1-5 = **25 run × 5,000 tick**。

関連:
- Issue #41
- `docs/V1.4_総括.md` (V1.4恒久default) / `docs/バージョニング方針.md`

---

## 1. V1.5 で変わったこと

行動側で、光とchemicalという**単位の違う一次Energy刺激**を無次元受容器応答へ
通してから比較するようになった。

```text
response(x, K) = x / (x + K)          0 <= response < 1 / 単調増加

light_score    = light_absorption    × response(light,          1.2)
chemical_score = chemical_absorption × response(chemical_stock, 12.3)
```

- 変わるのは **light vs chemical の異種比較だけ**。絞り込んだ候補を
  無機栄養・死骸・捕食と比べる段階はV1.4と同じ legacy score
  (`ability × raw値`) を使う
- したがって**単独source世界の行動はV1.4と完全に一致する** (停止条件で確認)
- 吸収則 (`_absorb_light` / `_absorb_chemical`) はV1.4のまま
- 同点は `stimulus_tie_eps = 1e-9`。どちらも別セルならEnergy源による方向付けを
  行わない。両score=0はV1.4と同じ挙動

`chemical_stimulus_half = 12.3` は**典型13セルvent (`chem_vent_flux=16`) の
生物不在平衡stock**を基準にした固定値である。生物が占有したventのstockへ
再校正はしない (レビュー判断 §2)。実行中のfield最大値やfluxから再計算もしない。

V1.4以前とは結果が一致しない (意図的な世界バージョン境界)。
V1.4の再現には `v1.4-final` (`226a926`) を使う。

## 2. 交差点stock — Phase Bの読み方の基準

ある光量・個体能力で `light_score = chemical_score` となるchemical stockを
**交差点stock**と呼ぶ。これより stock が高ければchemical、低ければlightが
一次Energy候補になる。

`tools/bench_exp09.py` が事前計算して表示する (V1.5 default):

| 表現型 (light/chem) | 明部 L=1.2 | 中間 0.78 | 暗部 0.36 |
|---|---:|---:|---:|
| light specialist (2.0/0.3) | 交差点なし | 交差点なし | 交差点なし |
| chemical specialist (0.3/2.0) | 1.00 | 0.77 | 0.44 |
| generalist (1.0/1.0) | 12.30 | 8.00 | 3.69 |

参考: Exp08 flux16 で実測した**占有vent**のstockは中央値 0.51 E/cell
(seed範囲 0.19〜1.37)。占有中のventは交差点を下回ることがあり、その状態で
lightを選ぶのは**式どおりの挙動**である。低いvent滞在率をそれだけで
実装異常としない (計画 §9-10)。

## 3. 条件Config

変えるのは「光/chemicalの有無」と「診断表現型」だけ。世界パラメータは
V1.4恒久default (`light_uptake_coef=2.0` / `chem_vent_flux=16.0` /
`chem_uptake=0.5`)、受容器スケールはV1.5 defaultのまま。

| 条件 | 世界 | 表現型 (light/chem) | 配置 |
|---|---|---|---|
| `a_light_only_lightspec` | vertical光 / chemical 0 | 2.0 / 0.3 | random |
| `b_chem_only_chemspec` | 光0 / chemical 16 | 0.3 / 2.0 | vent |
| `c_mixed_lightspec` | vertical光 + chemical 16 | 2.0 / 0.3 | random |
| `d_mixed_chemspec` | 同上 | 0.3 / 2.0 | random |
| `e_mixed_generalist` | 同上 | 1.0 / 1.0 | random |

両能力とも `fixed_genes` で全世代固定する (進化効果を混ぜない)。
光単独条件でも `n_vents=4` を維持し `chem_vent_flux=0.0` にする
(vent生成の乱数消費を他条件と揃えるため)。

```bash
uv run python tools/make_exp09_configs.py          # configs/exp09/ を生成
uv run python tools/make_exp09_configs.py --check  # 生成物と一致するか確認
```

`tests/test_exp09_configs.py` が「source構成と表現型以外は5 Configすべてで同一」
を機械的に守る。workflow の setup ジョブも起動前に `--check` を実行する。

## 4. 実行前チェック (計画 §10 の停止条件)

```bash
git pull --ff-only
git status --short            # 空であること
git rev-parse HEAD            # 記録する
uv run pytest tests -q
uv run python tools/make_exp09_configs.py --check
uv run python tools/bench_exp09.py                                  # Phase 0 / Phase A
uv run python tools/verify_vs_ref.py --ref 226a926 --single-source  # 単独source一致
```

`tools/bench_exp09.py` は進化runを使わず、

- `response` の算術 (0 / half / 単調性 / 0<=r<1)
- 各表現型・代表光量の**交差点stock**の事前計算
- 交差点の**両側**で選択が反転すること (各表現型でlight/chemical両ケース)
- exact tieでsource走査順の固定biasがないこと / 両score=0でV1.4相当へ戻ること
- score計算が未来の吸収量・Energy容量・移動後収益を使っていないこと
- 比較処理が乱数を消費しないこと / 観測追加が結果を変えないこと

を検査し、1件でも落ちれば非ゼロ終了する。workflow の setup でも実行する。

`verify_vs_ref --single-source` は light-only / chemical-only のConfigで
`v1.4-final` と指紋が完全一致することを確認する (レビュー判断 §3.2)。

## 5. 起動

GitHub → Actions → **Exp09** → Run workflow。

### Pilot (先に実施)

| 入力 | 値 |
|---|---|
| `cases` | default (5条件すべて) |
| `seeds` | `1` |
| `ticks` | `1000` |
| `render_spatial` | `true` |

5 run。実装健全性だけを確認する。Pilotの結果を見て本番条件を変更しない。

### 本番

| 入力 | 値 |
|---|---|
| `cases` | default (5条件すべて) |
| `seeds` | `1-5` |
| `ticks` | `5000` |
| `upload_events` | `false` |
| `render_spatial` | `true` |

25 run。`max-parallel: 20` で2波。所要は数十分程度。

## 6. 出力と停止条件

### collect ジョブ

| チェック | 停止条件か |
|---|---|
| `check_env.py` 数値実行環境の同一性 | **停止** |
| `health_check.py` run数・環境・SHA (早期終了は警告) | **停止** (早期終了以外) |
| `check_exp09.py` 排他・default・表現型固定・**score順位と実選択の一致** | **停止** |
| `summarize_exp09.py` 主判定と選択統計 | 情報 |

setup ジョブの Phase 0 / Phase A ベンチと単独source一致も停止条件。

## 7. 読み方 (計画 §9)

**最優先の判定**:

> その時点のchemical stockが事前計算した交差点より上ならchemical、
> 下ならlight という score順位と、実際の一次Energy候補選択が一致すること。

`summarize_exp09.py` が最初に「一致率」を出す。1.0000 でなければ実装不整合。

参考として:

- light specialistは標準条件ではchemical specialistよりlight選択率が高い
- chemical specialistは交差点を超えるstockではchemicalを選ぶ
- generalistは一方へ固定されず、局所stockと光量の組合せで切り替わる
- stock消費 → 離脱 → stock回復 → 再誘引の反復が出ても、交差点式と整合するなら
  異常ではない
- light-only / chemical-only control は `v1.4-final` と完全一致

**結論しないこと** (計画 §11): 光とchemicalの進化的優劣 / 専門化の方向 /
specialistとgeneralistの共存 / chemical bootstrap / 動物的進化 /
全刺激の完全比較則。

## 8. 実行後

1. Summary で env_check / health_check / 診断条件チェック / 要約を確認
2. 生データを退避 (外部ストレージ or `exp09-rawdata` 成果物)
3. `docs/実験結果保存方針.md` に従って `docs/Exp09_結果考察.md` と
   `experiments/<exp09_id>/NOTES.md` を作成し、集計プロットと代表GIF/PNGを
   `figures/` へ厳選保存する (文字サマリーだけで終了しない)
4. `docs/次の実験計画.md` と Issue #41 を更新
5. Green なら、通常祖先を混合世界へ置く長期進化実験を別途事前登録する

## 附録A. ローカル実行 (動作確認用)

```bash
for c in a_light_only_lightspec b_chem_only_chemspec d_mixed_chemspec; do
  uv run python tools/run_batch.py --seeds 1 --ticks 1000 --workers 1 \
    --config configs/exp09/exp09_${c}.json \
    --out runs/exp09/${c}
done
uv run python tools/check_exp09.py runs/exp09 --seeds 1
uv run python tools/summarize_exp09.py runs/exp09 --ticks 1000
```
