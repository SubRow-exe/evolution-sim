# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/V1.9_総括.md` — **直前versionのclose正本**
2. `docs/次の実験計画.md` — **現在作業の司令塔**
3. `docs/V1.10_CNP資源分解_実装仕様.md` — **V1.10実装正本**
4. `docs/Exp17_V1.10_CNP資源分解_実験計画.md` — **次formal experiment正本**
5. `docs/長期ロードマップ.md`
6. `docs/V1.9_現状ステータス.md`
7. `docs/Exp16_V1.9_結果考察.md`
8. `docs/V1.9_LUCA_proxy設計.md`
9. `docs/環境因子追加・校正方針.md`
10. `docs/バージョニング方針.md`
11. `docs/実験結果保存方針.md`
12. `docs/数値再現性・Actions実行環境方針.md`

旧V1.9 draft・旧Exp15計画より上記正本を優先する。

---

# 2. 現在地

```text
V1.8                         CLOSED
V1.9                         CLOSED
Exp15 Attempt 2 Phase A      SCIENTIFIC PASS
Exp15 Attempt 2 Phase B      NOT RUN / DEFERRED
Exp16                        COMPLETE / 55 runs analyzed
V1.10 C/N/P resource closure NEXT
Exp17                        PLAN READY
```

V1.9を再オープンして細部校正を続けない。
V1.10は独立versionとして扱う。

---

# 3. 現在の作業

## V1.10

environmental generic `nutrient/Matter`を:

```text
DIC / CO2-equivalent inorganic carbon
fixed nitrogen
phosphate phosphorus
```

へ分解する。

`Organism.matter`はdry biomassとして維持。
水およびS/Fe/Mg/K/Na/Ca/trace metalsは当面implicit/non-limiting。

fixed biomass stoichiometryでgrowth / corpse / waste / predationをC/N/P ledgerへ接続する。

## Exp17

```text
Phase 0  C/N/P conservation + limiter mechanical tests
Phase A  fixed iLUCA reference / 5 seeds x 10 physical days
Phase B  low-C / low-N / low-P identity tests
Phase C  depletion diagnostic only if needed; auto-runしない
```

V1.9 final populationを再現するためのC/N/P調整は禁止。

---

# 4. LUCA fidelity HARD RULE

**歴史上のLUCAを完璧に再現することはmainstreamの目的ではない。**

iLUCAはoriginの妥当性を上げるためLUCA-likeへ寄せるが、以下の場合だけ追加実装を優先する。

1. 欠落が現在結果を強く支配する
2. 次の進化圧へ応答するため必要
3. 現仕様が明らかに非生物学的
4. 物理scale・保存則・解釈性を大きく改善する

分子詳細の未実装を理由にmainstreamを延期しない。

---

# 5. 校正・実験 HARD RULE

環境を生存側へ曲げる前に:

> その環境が要求する応答を、生物側が現在または進化によって原理的に実現できるか

を確認する。

原則:

```text
mechanism test
-> fixed ancestor sanity
-> 必要ならevolution ON
-> minimal interaction
-> close
```

成立域がrobustならglobal optimum探索をしない。
実験結果を見てreference値を生存側へ自動最適化しない。

---

# 6. H2 environment HARD RULE

V1.9のH2はEnergyそのものではなくsubstrate。

```text
H2 -> uptake -> metabolism -> usable Energy + heat
```

V1.9 reference:

```text
H2 source = 10 mM
D = 5e-9 m2/s
exchange/loss tau = 900 s
4-source distributed layout
```

既知制約:

- sourceはDirichlet concentration boundaryで実質無限供給
- 現状はH2 depletion competitionよりpatch accessが主要圧
- dynamic source化はV1.11予定

---

# 7. Structural innovation HARD RULE

continuous mutationと能力起源を分離する。

```text
PHOTOTROPHY: innovation-gated
PREDATION:   V1.9ではlocked
```

現状のlight routeはphysical scale未対応なので、**V1.12以前にphototrophy formal experimentを開始しない。**

innovation probabilityを結果を見ながら調整しない。

---

# 8. 未来予測禁止 / homeostasis許可

```text
NG: 日没が近いからEnergyを貯める
NG: 将来収益を予測して行動する
OK: 現在Energyと現在支出からrunwayを計算
OK: 現在runway不足に応じて生理を調節
```

---

# 9. 絶対設計原則

- 適応度関数を直接置かない
- 特定生態型への固定bonus/penaltyを置かない
- 将来を予測するAI的行動を入れない
- 保存則を破らない
- 観測/Recorderをsimulationへフィードバックしない
- same-seed determinismを守る
- 能力起源をcontinuous mutationの裏口で起こさない
- 歴史的experimentを現在仕様へ書き換えない
- 過去worldの再現はversion ref/tagから行う
- 生存するようenvironment parameterを自動校正しない
- LUCA fidelityを目的化しない
- version境界を跨いだ変更を同一versionへ後付けしない

---

# 10. Formal experiment運用

- `effective_config.json` / `initial_genome.json` を成果物へ必ず保存
- preregistered gateでartifact不足があればsilent SKIPせずFAIL
- formal開始後にreference parameterを変更しない
- 変更が必要ならAttempt 2として履歴を残す
- Phase C等の条件付きrunを勝手に開始しない

---

# 11. 直近作業

```text
1. V1.9 branch/PR状態を確認しversion境界を確定
2. V1.10 C/N/P実装
3. unit / conservation / determinism tests
4. Exp17 Phase 0
5. Exp17 Phase A
6. Exp17 Phase B
7. 結果保存・考察
8. Phase Cは必要時のみ人間判断
```

長期順序は `docs/長期ロードマップ.md` を参照する。
