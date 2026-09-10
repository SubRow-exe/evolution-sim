# Exp20 結果・考察 — V1.11 Primitive Phototrophy Seeded Invasion

更新: 2026-09-10  
状態: **Attempt 1 完了 / 生態学的結論は撤回 / Attempt 2 再実験が必要**

正本実験計画: `docs/Exp20_V1.11_PrimitivePhototrophy_SeededInvasion_実験計画.md`  
V1.11仕様正本: `docs/V1.11_原始Phototrophy_実装仕様_rev2.md`  
Opus 5レビュー: Issue #71 / `docs/Exp20_Opus5レビュー.md`  
次の正本: `docs/Exp20_Attempt2_修正・再実験計画.md`

---

## 1. 用語

- **phototroph**: V1.11で追加したprimitive phototrophy能力を持つ個体。
- **ancestor**: phototrophy能力を持たない祖先型個体。
- **A0_STATIC**: 4 ventが常時ONの一定H2供給環境。
- **A1_TEMPORAL**: 4 ventを2組に分け、6 hごとにactive pairを交代する時間変動H2環境。総H2供給量はA0と同じ。
- **legacy light route**: V1.11以前の任意単位の `world.light` を `_absorb_light()` で直接 `org.energy` に加算する旧経路。
- **physical phototrophy route**: V1.11 rev2で導入した photon flux -> absorbed -> usable -> maintenance/activity credit の物理単位経路。

---

## 2. Attempt 1で確認できた事実

formal designどおり24 runは全完走し、aggregate artifactも生成された。

```text
Environment: A0_STATIC / A1_TEMPORAL
Initial photo frequency: 0 / 1 / 10 / 50%
Seeds: 20001 / 20002 / 20003
Duration: 120 h
Total: 24 runs
```

成立性として保持できる結果:

- 24/24 run完走
- C/N/P ledger closure
- V1.11 phototrophy chain内部のEnergy identity成立
- A1 ancestor-only controlは約43–46 hで全滅
- 実験pipeline・artifact生成系が動作

一方、以下の生態学的結論は撤回する。

- A0でphototrophが48 hで16倍になったことを「phototrophyの一般的fitness advantage」とした解釈
- `Delta_s48 > 0` を主根拠として「TEMPORAL環境でphototrophyの相対fitnessが高い」とした判定
- A0の強い利益を弱めるためにphototrophy benefit / costを調整するというExp21方針

---

## 3. 重大な原因1 — physical modeにlegacy light routeが混入

Opus 5レビューとコード照合により、`Simulation._absorb_fields()` がphysical modeでも旧 `_absorb_light()` を呼び続けていることを確認した。

この旧経路は任意単位の `world.light` と `light_uptake_coef` から得た値を、現在Joule建てとなっている `org.energy` に直接加算する。

そのため、phototrophではV1.11の物理光機構とは別に巨大なEnergy流入が起き、需要が `E_max - energy` でclampされる結果、毎stepに近い頻度でEnergy tankが満タンになる。

診断結果:

```text
V1.11 physical photo credit（30 step） : 5.1474e-16 J
legacy routeの余分なEnergy           : 1.3895e-11 J
legacy / V1.11                        : 約2.70e4倍
```

legacy routeのみ無効化してA0 50%条件を48 h再現すると:

```text
phototroph: 50 -> 50
ancestor:   50 -> 50
```

となり、Attempt 1の `50 -> 800`、すなわち16倍増殖は完全に消えた。

したがって、Attempt 1のA0 strong sweepはV1.11 primitive phototrophyの効果ではない。

---

## 4. 重大な原因2 — 48 h相対fitness指標がlineage extinctionに支配された

Attempt 1では0–48 hのphototroph/ancestor log-ratio変化 `s48` と、A1-A0差 `Delta_s48` を主指標としていた。

しかしA1ではancestor-onlyが43–46 hで全滅し、10% / 50% founder armでも48 h時点のancestor数が実質0となるrunがあった。

その結果、48 hのlog-ratioは生物学的な増殖速度差よりも、`log(0)` 回避用pseudocount 0.5に強く支配された。

従って:

- 0% armだけでなく、ancestorが0またはほぼ0となるfounder armでも48 h相対指標は主評価に使用しない
- `A48 = 0` をpseudocountで有限値化してprimary estimandへ押し込まない
- lineage extinctionは相対fitness指標ではなく、生存時間・絶滅時刻として別に評価する

とする。

Attempt 1の `Delta_s48 > 0` は正式な生態学的結論として採用しない。

---

## 5. テスト上の問題

`tests/test_v111_phototrophy.py` の主要テストはproductionの `Simulation.step()` を通さず、旧Energy入口を検出できない構造だった。

特に:

- T4はテスト自身がphoto creditを個体へ加算してからassertしている
- T5は「light alone does not fund growth」のbehaviorを検査せず、関数signatureのみを確認している
- dark testはV1.11 physical photon fluxを0にしても、別fieldであるlegacy `world.light` を止めない
- phototrophy OFF testでは、capability OFF時に休眠するlegacy経路を原理的に検出できない

よって今後は、機構内部counterだけでなくproduction stepを通した外部的な上界検査を追加する。

---

## 6. 修正方針

コード修正はClaude Code / Codexが担当する。修正要求は以下。

### R1. physical modeからlegacy light routeを除去

physical modeでは旧 `_absorb_light()` によるEnergy加算を使用しない。

重要なのは「phototrophy capabilityがOFFなら呼ばない」というgate追加ではなく、**physical modeのEnergy経路から旧任意単位light routeそのものを排除すること**。

またphysical modeで `light_max` / `light_uptake_coef` 等のlegacy parameterがEnergy収支へ影響しないことをtestで固定する。

### R2. production `Simulation.step()` を通すbehavioral testへ変更

最低限:

1. 同一条件のphototroph / ancestorを実stepで進める
2. 実測Energy差を得る
3. V1.11機構が物理的に説明できる最大Energy差を独立計算する
4. 実測差が上界を超えないことをassertする

概念的には:

```text
DeltaE_photo - DeltaE_ancestor
<= physical_photo_usable_upper_bound + maintenance_difference + tolerance
```

とする。

このassertはV1.11内部counterを真として再利用せず、「説明できない第2のEnergy入口」が存在しないことを検出するためのもの。

### R3. T5を実behavior検証へ置換

「lightだけでは持続的net biomass growthをfundしない」を、signatureではなく実simulation behaviorとして検査する。

### R4. 異常な完全一致を診断対象にする

今後の実験レビューchecklistへ以下を追加する。

```text
[ ] 複数seedで完全同一のtrajectory / endpointになっていないか
[ ] 増加率が2^nの整数倍など同期分裂を示していないか
[ ] 観測効果量が新機構の理論上限を超えていないか
```

確率的simulationでseed間分散が0の場合は「再現性が高い」と即解釈せず、決定論的なhidden routeやclampを先に疑う。

---

## 7. Exp20 Attempt 1の最終扱い

**Attempt 1は削除しないが、生態学的結論はINVALIDとする。**

保持目的:

- legacy light route混入を発見した再現可能な失敗例
- regression testを設計する根拠
- 解析指標のlineage extinction問題を示す事例
- pipeline / ledger成立確認

したがって「Exp20 formal runは成功、再実行不要」という旧結論は撤回する。

---

## 8. 次の実験 — Exp20 Attempt 2

コード修正とtest合格後、**同一の生物学的問いをAttempt 2として再実行する**。

基本条件はAttempt 1から変更しない。

```text
A0_STATIC / A1_TEMPORAL
photo founder = 0 / 1 / 10 / 50%
seed = 20001 / 20002 / 20003
photon flux = 0.015 umol/m2/s
radiant_to_usable_eff = 0.10
light_absorption = 0.01
Duration = 120 h
Total = 24 runs
```

これはparameter calibrationではなく、**バグ修正後に当初の問いを再検証する実験**である。

### Attempt 2の主評価

48 h単一点ではなく、ancestorの全滅より前のearly windowを使う。

```text
6 h / 12 h / 18 h / 24 h
```

各時点でP>0かつA>0の場合に:

```text
L(t) = ln(P_t / A_t)
```

を計算し、時間に対する回帰傾きをearly relative fitnessとする。

- pseudocountはprimary endpointに使用しない
- lineageがwindow途中で0になった場合、その後のlog-ratioを補完しない
- valid pointが不足するrunはrelative-fitness slopeをNAとし、extinction outcomeとして扱う
- A1-A0差は同一seed・founder頻度でpairedに比較する

### ecological rescueは別estimand

以下を独立評価する。

- ancestor lineage extinction time
- phototroph lineage extinction time
- total population extinction time
- survival at 120 h
- population trajectory / AUC
- lineage-specific births / deaths

「phototrophが相対的に有利」と「phototrophyが集団を絶滅から救う」を混同しない。

### A0 negative control

修正後A0では、Attempt 1のような決定論的16倍sweepが消失していることを確認する。

ただし `P48 == P0` を固定の合否基準にはしない。重要なのは:

- legacy route由来Energy = 0
- 観測されたphoto由来Energy差がphysical上界内
- seed間完全同期の不自然な2^n sweepがない

ことである。

---

## 9. Attempt 2後の次段階

Attempt 2でphysical phototrophyによるecological rescueが再現した場合、次段階で光量を校正する。

現時点ではphototrophy効率やN構造コストを先に変更しない。まず環境量であるphoton fluxを1軸で振り、A1 rescueが成立する最小光量を探す方向を第一候補とする。

候補:

```text
0.015 / 0.05 / 0.15 / 0.5 / 1.5 umol/m2/s
```

ただしこれはExp20 Attempt 2の結果確認後に正式preregistrationする。

Attempt 2でrescueが消える場合は、まずphysical mechanismの効果量とH2 interruption時のmaintenance deficitを比較し、必要光量を理論計算してから次のsweepを設計する。

---

## 10. 現時点の結論

> **Exp20 Attempt 1で観測されたA0の16倍増殖は、V1.11 phototrophyではなくlegacy light routeからの単位不整合Energy流入である。また48 h相対fitness指標はA1のancestor extinctionとpseudocountに支配されていた。したがってAttempt 1の生態学的結論と「phototrophyを弱める」方針を撤回する。physical modeからlegacy routeを除去し、production stepを通すEnergy上界testを追加した上で、同条件のExp20 Attempt 2を再実行する。Attempt 2では6–24 hのearly relative-fitness slopeとlineage survivalを別々に評価する。光量calibrationはAttempt 2の結果を確認してから行う。**
