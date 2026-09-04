# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/V1.9_現状ステータス.md` — **現在地・権限の正本**
2. `docs/V1.9_iLUCA再設計仕様.md` — **V1.9 world-rule FINAL仕様**
3. `docs/V1.9_実装チェックリスト.md` — **実装順・完了条件**
4. `docs/次の実験計画.md` — 現在の司令塔
5. `docs/V1.8_総括.md` — V1.8 close / 方針転換
6. `docs/環境因子追加・校正方針.md` — 恒久設計原則
7. `docs/バージョニング方針.md`
8. `docs/メインストリーム開発ストーリー.md`
9. `docs/実験結果保存方針.md`
10. `docs/数値再現性・Actions実行環境方針.md`

過去のExp15計画・V1.9旧draft・historical experimentより、上記FINAL仕様を優先する。

---

# 2. 現在地

```text
V1.7                         CLOSED
V1.8 scientific phase        CLOSED
original Exp15               SUPERSEDED / DO NOT DISPATCH
V1.9 design                  FINAL
V1.9 implementation          AUTHORIZED / CURRENT TASK
next formal experiment       NOT DESIGNED
```

現在AIが行ってよいこと:

- V1.9 FINAL仕様のコード実装
- unit/integration test追加・更新
- conservation / determinism検証
- 短いmechanical sanity
- 実装監査・ドキュメント更新

現在AIが勝手に行ってはいけないこと:

- 旧Exp15 dispatch
- formal experiment設計/dispatch
- parameter sweep
- 生存させるためのenvironment tuning
- V1.8 parameter tuningへの回帰

---

# 3. V1.9の目的

V1.9 = **より妥当なchemical-first iLUCA baselineの再構築**。

環境側を生存に合わせて曲げるのではなく、生物自身が自然な環境圧へ生理・進化で応答できる構造を作る。

主要FINAL変更:

```text
INITIAL light_absorption = 0
INITIAL predation_efficiency = 0
Energy = 1-pool
storage_capacity gene + storage upkeep
starvation signal = runway / starvation_horizon
reproduction gate = runway >= reproduction_horizon
H2 explicit / CO2 implicit
H2 diffusion halo
uniform random initial spawn
phototrophy = structural innovation gated
predation = V1.9 locked
```

V1.8 day/nightは残す。初期iLUCAにはlight routeが無いため直接影響せず、phototrophy出現後に意味のある周期圧となることを狙う。

---

# 4. 旧V1.9 draftからの廃止事項

以下を実装しない。

```text
Operational Energy + Reserve 2-pool
E_target controller
reserve_store_eff
reserve_mobilize_eff
starvation_sensitivity gene
reserve_capacity gene
reproduction_threshold fraction gene
source-biased initial spawn
```

代わりにFINAL仕様の:

```text
storage_capacity
starvation_horizon
reproduction_horizon
runway signal
```

を使う。

---

# 5. V1.9 homeostasis HARD RULE

未来情報を使わない。

```text
NG: 日没が近いから活動を止める
NG: 将来のEnergy収益を予測して貯蔵する
OK: 現在Energyと現在のfull-activity支出からrunwayを計算する
OK: runway不足に応じて現在代謝を調節する
```

FINAL仕様:

- BMR可変部/repairは強く抑制
- H2/light/nutrient uptakeは弱く抑制
- bmr_coreは抑制しない
- structural upkeepは抑制しない
- movementはV1.9 starvation responseでは抑制しない

---

# 6. V1.9 storage / reproduction

storage:

```text
E_max = energy_capacity_base * storage_capacity * matter
storage_upkeep ∝ storage_capacity * matter
```

容量を無料形質にしない。

reproduction:

```text
runway >= reproduction_horizon
AND
existing Matter gate
```

capacity fractionを繁殖条件へ直接使わない。

---

# 7. H2 environment HARD RULE

V1.9ではH2をEnergyそのものではなくsubstrateとして扱う。

```text
H2 substrate
 -> uptake
 -> chemical free energy
 -> conversion efficiency
 -> usable Energy + heat
```

vent:

- equal total flux
- world edgeからr以上内側
- source disk非重複
- fixed
- V1.9ではvent間flux差なし

H2:

- environmental loss
- reflecting diffusion
- explicit consumption
- halo/gradient形成

baseline initial spawnはworld uniform random。vent座標を個体へ教えない。

---

# 8. Structural innovation HARD RULE

continuous mutationと能力起源を分離する。

```text
PHOTOTROPHY: innovation-gated
PREDATION:   V1.9 locked
```

PHOTOTROPHY OFFならLIGHT_ABSは常に0として機能する。
PREDATION OFFならPREDATION geneが加算変異で正値になっても捕食機能を持たせない。

innovation probabilityはfitness・環境・観測値を参照しない。
phototrophyを出す目的でrun中に確率を調整しない。

---

# 9. 進化可能性とsanityの区別

今後の科学確認では原則:

```text
fixed ancestor sanity
+
evolution-ON sanity/experiment
```

を分離する。

固定祖先が死んでも、進化ONで適応可能なら環境FAILとは限らない。

ただし現在はexperiment設計段階ではない。

---

# 10. 絶対設計原則

- 適応度関数を直接置かない
- 特定生態型への固定bonus/penaltyを置かない
- 将来を予測するAI的行動を入れない
- 保存則を破らない
- 観測/Recorderをsimulationへフィードバックしない
- same-seed determinismを守る
- 能力起源を通常continuous mutationの裏口で起こさない
- 歴史的experimentを現在仕様へ書き換えない
- 過去worldの再現はversion ref/tagから行う
- 生存するようにenvironment parameterを自動校正しない

---

# 11. 実装手順

```text
1. 現main SHA / baseline tests記録
2. V1.9 FINAL仕様実装
3. V1.9 tests追加・既存tests更新
4. Energy/Matter/H2 conservation
5. determinism
6. mechanical sanity
7. implementation report
8. STOPして人間レビュー
```

細目は `docs/V1.9_実装チェックリスト.md`。

world rule / gene meaning / conservation / capability semanticsを変更しないと実装不能な場合は勝手に仕様変更せず、人間へ報告する。

formal experimentは人間の明示判断なしに開始しない。
