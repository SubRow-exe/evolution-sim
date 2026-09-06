# Exp16 V1.9 環境ロバストネス 結果・考察

更新: 2026-09-07
状態: **COMPLETE / 55 RUNS ANALYZED**

対象commit: `4d5a9cdd8c7948f037f8890ab977917421dc0524`
GitHub Actions run: `33873209494` (`Exp16 V1.9 Environment Robustness`)

---

## 1. 目的

Exp15 Attempt 2で成立したLUCA-like iLUCAを一切変更せず、H2環境の強さ・輸送・空間配置だけを変えたときに、10 physical daysの生存・成長・世代交代がどこまで維持されるかを調べる。

これはbaselineを生存側へ調整するためのadaptive tuningではない。11条件 x 5 seedを事前固定し、絶滅条件も含めて全55 runを保存した。

---

## 2. 実験結果

| condition | 生存 | final N median | max generation median | generation interval median | 解釈 |
|---|---:|---:|---:|---:|---|
| `h2_1mM` | 0/5 | 0 | 0 | — | 全滅 |
| `h2_3mM` | 0/5 | 0 | 0 | — | 全滅 |
| `h2_6mM` | 5/5 | 386 | 2 | 122.4 h | 生存可能だが強い制約 |
| `baseline_10mM` | 5/5 | 2981 | 5 | 55.9 h | 安定した成立 |
| `h2_15mM` | 5/5 | 4876 | 6 | 35.4 h | 高成長 |
| `exchange_fast_300s` | 0/5 | 0 | 0 | — | 全滅 |
| `exchange_slow_3600s` | 5/5 | 5000 | 6 | 32.0 h | 全seed上限到達、censored |
| `diffusion_low_2p5e9` | 0/5 | 0 | 1 | 78.4 h | 一時繁殖後に全滅 |
| `diffusion_high_1e8` | 5/5 | 4937 | 6 | 40.9 h | 高成長 |
| `layout_cross` | 5/5 | 43 | 5 | 50.7 h | 10日生存するが個体群は縮小 |
| `layout_cluster` | 0/5 | 0 | 5 | 30.8 h | 局所繁殖後に全滅 |

保存則は全条件で破綻しておらず、Exp16 workflow自体もsuccessで完了した。

---

## 3. 最大の結論

### 3.1 H2量だけでなく「H2-rich領域の空間的な広さ」が支配的

Exp16ではH2 source濃度だけでなく、diffusion、exchange-loss、source geometryの変更でも生存/絶滅が反転した。

物理modeのH2 fieldでは、source cellは指定濃度へclampされる一方、非source領域では概念的に

```text
diffusion + exchange/loss
```

でH2 haloが形成される。

代表的な拡散到達スケールは

```text
L ~ sqrt(D * tau)
```

で整理できる。

| 条件 | D [m2/s] | tau [s] | sqrt(D*tau) |
|---|---:|---:|---:|
| exchange_fast | 5e-9 | 300 | 1.22 mm |
| diffusion_low | 2.5e-9 | 900 | 1.50 mm |
| baseline | 5e-9 | 900 | 2.12 mm |
| diffusion_high | 1e-8 | 900 | 3.00 mm |
| exchange_slow | 5e-9 | 3600 | 4.24 mm |

この順序は結果と非常によく一致する。

```text
haloが狭い
  exchange_fast / diffusion_low -> extinction

baseline
  -> stable growth

haloが広い
  diffusion_high / exchange_slow -> very high growth
```

したがって、現在のiLUCA成立性を決める中心因子は単なるsource peak濃度ではなく、**個体が利用可能なH2領域の面積・連結性・遭遇確率**である。

### 3.2 `h2_exchange_tau_s` の意味

名称だけ見ると `exchange_fast` が「供給が速い」ように読めるが、現実装では各substepで

```text
loss = C * dt / tau
```

によるH2 removalが入り、その後source cellのみ指定濃度へ戻される。

従って:

```text
small tau = H2が速く除去される = haloが狭い
large tau = H2が長く残る       = haloが広い
```

である。

これはExp16の逆転挙動を説明でき、現時点では実装バグを示す結果ではない。ただし名称が曖昧なので、今後の文書では **H2 exchange/loss timescale** または **washout timescale** と明記する。

---

## 4. H2濃度依存性

baseline輸送条件では明瞭な段階差が出た。

```text
1 mM  -> extinction
3 mM  -> extinction
6 mM  -> persistence, slow growth
10 mM -> robust growth
15 mM -> high growth
```

少なくとも現在のiLUCAでは、3–6 mMの間に10日スケールの成立境界がある。

ただしこれは「LUCAのH2生存閾値が3–6 mM」という意味ではない。現在のworld geometry、diffusion/loss、移動、生理を含む**モデル全体のeffective threshold**である。

10 mM baselineは、全滅でも上限張り付きでもなく、5世代・約3000個体まで成長する中間的な条件になっている。V1.9 reference environmentとして当面維持する合理性がある。

---

## 5. source geometry

source数・source濃度を同じにして配置だけを変えても結果が大きく変わった。

### square

4 sourceを四象限へ分散するため、world全体のnearest-source距離が比較的小さい。baselineでは5/5生存、final N約3000。

### cross

sourceがworld中央寄りになり、corner側に大きなH2-poor領域が残る。5/5で10日生存したがfinal N median=43で、初期100より減少している。

従ってこれは「安定平衡」と断定せず、**10日間のpersistence**と扱う。さらに長期なら絶滅する可能性がある。

### cluster

sourceが中央に集中するため局所H2は豊富でもworld大部分がH2-poorになる。

全seedで最終的に絶滅したが、max generation median=5であり、単純に最初から成長不能だったわけではない。代表seedでは繁殖を繰り返した後、個体群減少が続いて約8日で絶滅した。

これは

> 良いpatch内では繁殖できるが、patchが狭く分散損失を補えない

という空間生態的な挙動として整合的である。

---

## 6. seed再現性

条件内のseed差は小さい。

例:

```text
baseline final N = 2929–3019
h2_6mM final N   = 362–398
layout_cross     = 38–57
```

生存/絶滅判定も各条件で5/5一致した。

従って今回の主要効果はRNG依存の偶然ではなく、environment conditionの効果としてかなり強い。

---

## 7. 重要な未解決点

### 7.1 生物によるH2 depletionがほぼ無い

biological H2 uptake / source influxはbaselineでmedian約

```text
5.6e-6
```

であり、最も高い条件でも1e-5オーダーである。

つまり現在のworldでは、数千個体いてもH2 fieldを生物がほとんど削っていない。

現状の選択圧は主として

```text
資源を奪い合う競争
```

ではなく

```text
H2-rich領域へ到達し、そこに滞在できるか
```

である。

これはExp16の目的上は問題ではないが、将来「資源競争・carrying capacity・生態型共存」を扱う際には重要な未解決点になる。

### 7.2 rich環境では別の律速が見え始める

`h2_15mM`、`diffusion_high`、`exchange_slow`ではfinal runwayがbaselineより大幅に増え、数時間分のEnergy reserveを持つ。

H2 Energyが十分になると、Matter precursor uptake / growth / reproduction等の別軸が律速になっている可能性がある。

従って今後H2をさらに増やすだけの実験価値は低い。

### 7.3 10日runは平衡確認ではない

- `exchange_slow`は5000個体のsimulation halt上限に全seed到達しており、真のcarrying capacityは未測定。
- `baseline`、`h2_15mM`、`diffusion_high`も10日時点で成長中の可能性がある。
- `layout_cross`は生存しているが減少傾向の可能性がある。

従ってExp16は**finite-time robustness map**であり、定常生態系の測定ではない。

---

## 8. V1.9への判断

Exp16から、現在のLUCA-like iLUCAが

1. どんなH2環境でも都合よく生存するわけではない
2. 物理的なH2分布に応じて生存/繁殖が大きく変わる
3. transportとgeometryによる自然な環境圧を受ける
4. seedを変えても同じ定性的結果を示す

ことが確認できた。

したがってV1.9のphysical environment + LUCA-like physiologyは、少なくとも**次の進化実験を行うための土台として成立している**と判断する。

baselineは当面:

```text
H2 source = 10 mM
D = 5e-9 m2/s
H2 exchange/loss tau = 900 s
4-source square layout
```

を維持する。

Exp16結果を理由にbaselineを最適化し直さない。

---

## 9. 次の実験への示唆

最優先はExp15 Attempt 2 Phase Bである。

Phase A実データでは5/5 seedがmax_generation=5へ到達しているため、本来の事前登録gateは科学的にはPASSしている。workflow artifact pathの集計不具合によりPhase Bが誤ってSKIPされたため、gate処理を修正したうえで、同じbaseline・同じ設計でPhase Bを実行する。

Phase Bでは:

```text
storage_capacity
starvation_horizon
reproduction_horizon
```

のみ進化可能にし、固定iLUCAに対して適応価値があるかを見る。

Exp16の結果から、環境をさらに調整してからPhase Bへ行く必要はない。

その後必要なら、環境を固定したiLUCA intrinsic parameter sensitivity、またはH2 depletion/competitionを扱う別実験を設計する。

---

## 10. Version

Exp16はV1.9内のConfig比較であり、新しいworld ruleを追加していない。

従って**VersionはV1.9のまま**。
