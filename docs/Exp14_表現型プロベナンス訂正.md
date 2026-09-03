# Exp14 表現型プロベナンス訂正

更新: 2026-09-04
状態: **Exp14結果解釈への正式訂正 / raw結果は保持 / Exp14再実行はしない**

関連:
- `docs/Exp14_実験計画確定.md` — 事前登録履歴。書き換えない
- `tools/make_exp14_configs.py` — 実際のConfig生成器
- `.github/workflows/exp14.yml` — formal実行経路
- `docs/V1.8_現状総括_Exp14結果.md`
- `docs/Exp15_実験計画確定.md`

---

# 1. 発見事項

Exp14事前登録ではPhase A/Bの固定表現型をExp13 A1と同じlight specialistとしていた。

意図した表現型:

```text
light_absorption = 2.0
chemical_absorption = 0.3
その他 = INITIAL_GENOME
```

しかし、実装された`tools/make_exp14_configs.py`の`build_phase_a` / `build_phase_b` / `build_phase_c`には`diagnostic_gene_overrides`が設定されていない。

一方、`fixed_genes`はPhase A/Bで全14遺伝子、Phase Cでも対象形質以外を固定している。

したがって実際の初期個体は`INITIAL_GENOME`を使用し、light側は:

```text
light_absorption = 0.3
chemical_absorption = 0.3
```

で開始した。

`.github/workflows/exp14.yml`のformal 116 runはすべてこれら`build_phase_*()`を直接呼ぶため、**116/116 runにこの表現型差が適用される。**

---

# 2. 何が原因か

Exp13ではlight specialistを:

```python
LIGHT_SPECIALIST = {"light_absorption": 2.0, "chemical_absorption": 0.3}
```

として、Configへ:

```python
diagnostic_gene_overrides=dict(LIGHT_SPECIALIST)
```

を明示していた。

Exp14では計画書上の「Exp13 A1 light specialist」を文章として継承したが、Config generatorへその上書きを移植しなかった。

generator/checker/testが「feature flag・run数・fixed_genes」中心に検査し、**Simulation初期化後の実個体表現型を独立oracleで確認していなかった**ことが再発防止上の本質的問題である。

---

# 3. Exp14結果で維持できる事実

raw artifact自体は有効なSimulation結果であり破棄しない。

以下は実測事実として維持する:

```text
- 116/116 runが最終絶滅
- 死亡原因はstarvation
- Generation 2は0
- 各armのpopulation / Energy / extinction tick等の実測軌跡
```

また、**実際に使われたINITIAL_GENOME表現型の範囲内**では、同一Phase内の相対比較は探索的証拠として利用できる。

例:
- cycleを消すと寿命が延びた
- storage capacity増加で一晩越しが改善した
- tick1繁殖抑制が延命方向だった

ただし、これらは「light specialistで定量確認済み」とは扱わない。

---

# 4. Exp14結果から撤回・弱める解釈

次はExp14だけでは主張しない:

1. Exp13 A1 light specialistとExp14 A0の定量的な直接比較
2. V1.7 light specialist世界に対する定量回帰
3. light specialistでのday/night・density response寄与量
4. Exp14 gridを根拠にV1.8恒久parameterを選定すること
5. 「light_max=8でも救済しない」をlight specialist一般へ外挿すること

Exp14は**INITIAL_GENOME光吸収0.3条件でのdiagnostic**として再位置づける。

---

# 5. Exp15での是正

Exp14をそのまま再実行しない。

Exp15では、本来必要だった2機構切り分けを正しいlight specialistで行う。

HARD GATE:

```text
fixed_genes = canonical GENE_NAMES 14個
diagnostic_gene_overrides:
  light_absorption = 2.0
  chemical_absorption = 0.3
```

Config JSONの値確認だけでは不十分。

必ずtestで`Simulation(cfg, seed)`を実際に初期化し、初期100個体すべてについて:

```text
light_absorption == 2.0
chemical_absorption == 0.3
```

を確認する。

このtestが通らない限りExp15 formalを開始しない。

---

# 6. 履歴の扱い

- `docs/Exp14_実験計画確定.md`は事前登録履歴として書き換えない
- Exp14 raw artifactを削除しない
- 本訂正文書を現在解釈より優先する
- `docs/V1.8_現状総括_Exp14結果.md`には訂正参照を追加する
- `AGENTS.md`と`docs/次の実験計画.md`から本書を最優先参照へ含める

今後、計画上の表現型と実行表現型の一致は**Config→Simulation初期個体までE2Eで検証する**。
