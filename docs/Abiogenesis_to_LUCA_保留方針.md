# Abiogenesis -> LUCA 保留方針

更新: 2026-09-04
状態: **DEFERRED / NOT ABANDONED**

## 1. 目的

本プロジェクトの長期目標の一つとして、完成済み生物を初期配置するだけでなく、より原始的な化学系から生命様システムが成立し、最終的にLUCA-likeな生物へ到達する過程を試す。

この目標は撤回しない。

## 2. なぜV1.9から分離するか

現在のEvoSimは `Organism` を既に次の能力を持つ単位として扱う。

- 境界/膜
- Energy state
- Matter state
- 代謝能力
- 複製/繁殖
- 遺伝子と突然変異

この枠組みのparameterをゼロ近傍へ落とすだけでは、abiogenesisを再現したことにはならない。生命成立前の段階では「個体」「遺伝子」「繁殖」という前提自体がまだ成立していないためである。

したがってabiogenesisを扱う際は、現行Organism以前に別layerが必要になる。

## 3. 最低限必要と考える前生物layer

候補:

```text
simple chemical species / feedstock
reaction network
energy gradients
surface/mineral catalysis
amphiphile or compartment formation
polymerization
catalytic molecules
imperfect template replication
heritable compartment composition
competition between protocells
transition from chemistry-level inheritance to genome-like inheritance
```

すべてを最初から実装する必要はない。最小モデルから段階的に検証する。

## 4. 再開時の基本方針

1. 現行V1.9 iLUCAを「到達目標の参照モデル」として保存する。
2. chemistry-only modelを現行Organismと独立に作る。
3. spontaneous compartment / self-maintaining reaction network / inheritance の各段階を別々にmechanical sanityする。
4. 「LUCAが出たこと」に合わせてルールを後付け調整しない。
5. 成立条件と不成立条件を両方保存する。
6. 最終的にprotocell stateをEvoSim Organismへ写像できるか検討する。

## 5. version

Abiogenesis layerは新しいstate variableとworld ruleを大量に追加するため、V1.9のparameter experimentには含めない。

再開時のversion番号はV1.9のclose後に決める。現時点では番号を予約しない。

## 6. 現在の優先順位

```text
V1.9 iLUCA physical baselineを整理
  -> environment robustness
  -> 必要ならiLUCA sensitivity
  -> V1.9 close
  -> abiogenesis trackを独立に再設計
```

V1.9で得られる「どのEnergy/Matter fluxならLUCA-like個体が成立するか」というデータは、将来abiogenesis modelがどの状態まで到達すれば生物圏へ移行できるかを決める境界条件として再利用する。
