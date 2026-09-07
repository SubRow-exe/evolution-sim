# AI協働開発ガイドライン (AGENTS.md)

本リポジトリは複数AIと人間で共同開発する。コード変更前に本書と現在の正本を必ず読むこと。

---

# 1. 現在の最優先参照順

1. `docs/V1.9_現状ステータス.md` — **現在地の正本**
2. `docs/次の実験計画.md` — **直近作業の司令塔**
3. `docs/長期ロードマップ.md` — **中長期phaseの正本**
4. `docs/Exp16_V1.9_結果考察.md`
5. `docs/V1.9_LUCA_proxy設計.md`
6. `docs/V1.9_iLUCA再設計仕様.md`
7. `docs/環境因子追加・校正方針.md`
8. `docs/バージョニング方針.md`
9. `docs/メインストリーム開発ストーリー.md`
10. `docs/実験結果保存方針.md`
11. `docs/数値再現性・Actions実行環境方針.md`

旧Exp15計画・V1.9旧draft・historical experimentより上記正本を優先する。

---

# 2. 現在地

```text
V1.8                         CLOSED
V1.9 implementation          IMPLEMENTED
Exp15 Attempt 2 Phase A      SCIENTIFIC PASS
Exp16                        COMPLETE / 55 runs analyzed
Exp15 Attempt 2 Phase B      NEXT
V1.9 Origin Lock             CURRENT PHASE
```

Exp15 Phase B後はOrigin Audit / mutation-innovation auditを必要範囲で行い、V1.9 close判断へ進む。

---

# 3. V1.9の目的

V1.9 = **今後の進化を始めるのに十分妥当なchemical-first LUCA-like iLUCA originの構築**。

主要構造:

```text
INITIAL phototrophy OFF
INITIAL predation OFF
Energy = 1-pool
storage_capacity / starvation_horizon / reproduction_horizon
runway homeostasis
H2 explicit substrate / CO2 implicit
physical H2 diffusion + exchange/loss
LUCA-like acetogen proxy
maintenance-first growth allocation
phototrophy = structural innovation gated
```

---

# 4. LUCA fidelity HARD RULE

**歴史上のLUCAを完璧に再現することはmainstreamの目的ではない。**

iLUCAはoriginの妥当性を上げるためLUCA-likeへ寄せるが、以下の場合だけ追加実装を優先する。

1. 欠落が現在結果を強く支配する
2. 次の進化圧へ応答するため必要
3. 現仕様が明らかに非生物学的
4. 物理scale・保存則・解釈性を大きく改善する

分子詳細の未実装を理由にmainstreamを無期限延期しない。

例:

```text
重要なら実装:
  movementがH2到達を不自然に支配
  temperatureが次のselection axisに必要
  carbon balanceがMatter解釈を支配

原則後回し:
  WLP全酵素反応
  ATP/ADP分子個別追跡
  LUCA膜脂質組成の完全再現
```

---

# 5. 校正・実験 HARD RULE

環境を生存側へ曲げる前に:

> その環境が要求する応答を、生物側が現在または進化によって原理的に実現できるか

を確認する。

原則:

```text
fixed ancestor sanity
+
evolution ON
```

を分離する。

成立域がrobustなら細かなglobal optimum探索を行わない。

通常は1 world-rule軸あたり:

```text
mechanism
 -> fixed sanity
 -> evolution ON
 -> minimal interaction
 -> close
```

の1〜3 experiment程度を目安とする。

---

# 6. H2 environment HARD RULE

V1.9のH2はEnergyそのものではなくsubstrate。

```text
H2
 -> uptake
 -> metabolism
 -> usable Energy + heat
```

physical field:

- source concentration
- diffusion
- exchange/loss
- biological uptake

Exp16から、iLUCA成立性はsource peakだけでなくH2-rich areaの面積・連結性・到達性へ強く依存することが確認された。

baseline referenceは当面:

```text
H2 source = 10 mM
D = 5e-9 m2/s
exchange/loss tau = 900 s
4-source square layout
```

Exp16結果を見て生存側へ最適化し直さない。

---

# 7. Structural innovation HARD RULE

continuous mutationと能力起源を分離する。

```text
PHOTOTROPHY: innovation-gated
PREDATION:   V1.9 locked
```

PHOTOTROPHY OFFならLIGHT_ABSは常に0として機能する。
PREDATION OFFならpredation geneが正値でも機能しない。

innovation probabilityはfitness・環境・観測値を参照しない。
run中に「出現させるため」確率を調整しない。

---

# 8. 未来予測禁止 / homeostasis許可

```text
NG: 日没が近いからEnergyを貯める
NG: 将来収益を予測して行動する
OK: 現在Energyと現在支出からrunwayを計算する
OK: 現在runway不足に応じて代謝を調節する
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
- 生存するようにenvironment parameterを自動校正しない
- LUCA fidelityを目的化しない

---

# 10. 直近作業

```text
1. Exp15 Phase B gate/artifact handling修正
2. Phase B実行・考察
3. Origin Audit（必要なlegacy/proxy parameterのみ粗い感度）
4. mutation / innovation scale audit
5. V1.9 close / main merge判断
6. 次world-rule phaseへ
```

formal experimentの新規追加・parameter sweep・新world-rule実装は人間の明示判断なしに開始しない。

長期順序は `docs/長期ロードマップ.md` を参照し、直前結果で更新する。
