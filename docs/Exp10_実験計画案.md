# Exp10 実験計画案 — V1.6 temporal biased random walk 診断・校正

更新: 2026-08-31
状態: **Claudeレビュー待ち / 未実装 / 事前登録案**

正本候補:
- `docs/V1.6_行動則設計案.md`
- `docs/Exp09_結果考察.md`
- `docs/V1.5_異種刺激比較仕様.md`

## 1. 目的

Exp10では、V1.6候補で導入する

> 複数刺激を無次元化して統合し、その時間変化によって直進・方向転換確率を偏らせる temporal biased random walk

が、実装式どおりに働くだけでなく、集団挙動として自然な走化性・走光性を創発するかを診断する。

Exp10は進化実験ではない。
遺伝形質は固定し、行動則のみを評価する。

## 2. 主仮説

以下が成立することを主仮説とする。

1. `ΔQ > 0` のとき方向維持が増える
2. `ΔQ < 0` のとき方向転換が増える
3. 刺激なしでは純粋な random walk に戻る
4. 一様刺激では偽の方向性が生じない
5. 空間勾配があると、直接最適方向を計算しなくても高評価領域への偏りが創発する
6. light + chemical が同時に存在しても winner-take-all にならず、両刺激が行動へ寄与する
7. 上記性質が特定の1パラメータ点だけでなく、ある程度広いパラメータ領域で成立する

## 3. 用語

- **Q（統合環境評価値）**
  各刺激の無次元受容器応答と個体能力から作る、その個体にとっての現在環境の評価値。

- **ΔQ**
  `Q_now - Q_past`。正なら環境改善、負なら環境悪化を意味する。

- **baseline turn rate**
  `ΔQ = 0` 付近での基本方向転換確率。

- **response gain**
  `ΔQ` が方向転換確率へ与える強さ。

- **memory time**
  現在値と比較する過去の時間幅。

- **ドリフト**
  多数個体の平均移動が特定方向へ偏ること。

## 4. 比較する移動方式

最低3方式を比較する。

### A. pure random walk

環境刺激を行動へ使わない対照。

### B. V1.5 winner-take-all

従来方式。

```text
刺激scoreを比較
→ 勝者sourceを1つ選択
→ そのsourceへ方向付け
```

### C. V1.6 temporal integration

新方式。

```text
複数刺激を統合してQを計算
→ 過去Qと比較してΔQを求める
→ turn rateのみを偏らせる
```

## 5. 固定表現型

Exp09と連続性を持たせるため、少なくとも以下を使う。

- light specialist
- chemical specialist
- generalist

能力値はExp09と同等の診断表現型を第一候補とし、全世代固定する。

進化・突然変異の影響は混ぜない。

## 6. 環境条件

最低7系統を用意する。

### E0: no stimulus

light = 0、chemical = 0。

目的:
- pure random walkへ戻るか
- V1.6実装が不要な方向バイアスを生まないか

### E1: uniform stimulus

空間的に一様な刺激。

目的:
- 刺激が存在するだけで特定方向へのドリフトが生じないか

### E2: light only gradient

lightのみ空間勾配を持つ。

目的:
- temporal sensingだけで高light領域への偏りが創発するか

### E3: chemical only gradient

chemicalのみ局所source・勾配を持つ。

目的:
- vent方向を直接指定せずに高chemical領域への偏りが創発するか

### E4: light + chemical same-direction

両刺激の改善方向を概ね一致させる。

目的:
- 複数刺激が協調して方向維持を強めるか

### E5: light + chemical conflict

lightとchemicalの好条件領域を別方向へ配置する。

目的:
- winner-take-allとの差
- generalistで両刺激が統合されるか

### E6: light + chemical orthogonal

lightとchemicalの空間変化方向を概ね直交させる。

目的:
- 単一source追従では説明できない軌跡・分布が生じるか

## 7. Phase 0 — 決定論・算術診断

本番前に小規模テストで以下を停止条件として確認する。

1. seed固定で完全再現する
2. `ΔQ > 0` で turn rate が下がる
3. `ΔQ < 0` で turn rate が上がる
4. `ΔQ = 0` で baseline に戻る
5. turn rate が常に0〜1
6. 刺激ゼロでも数値異常が出ない
7. light能力0ならlight項がQへ寄与しない
8. chemical能力0ならchemical項がQへ寄与しない
9. 両刺激が存在すると両項がQへ加算される
10. winner-take-all分岐が新方式では使われない
11. 吸収量計算がV1.5以前から変化していない
12. V1.6内で同一seed・同一Configがbit再現する

ここで失敗した場合、長時間runへ進まない。

## 8. Phase A — パラメータ広域スクリーニング

目的:
特定一点ではなく、自然な挙動が成立するパラメータ領域を探す。

第一候補の探索軸:

```text
memory time      = 1 / 3 / 10 / 30 tick
baseline turn    = low / middle / high
response gain    = weak / middle / strong
```

合計36組。

各組について少数seed、5,000 tick程度を走らせる。

最初は代表環境として E0 / E2 / E3 / E5 を優先する。

主観測:

- `ΔQ`符号別のturn率
- 平均run length
- 平均移動距離
- high-Q領域滞在率
- source近傍滞在率
- 集団重心のドリフト
- seed間ばらつき
- 絶滅率 / population推移

### Phase Aで落とす条件

以下のいずれかを満たす領域は候補から外す。

- E0で明確な方向ドリフトが出る
- E1で一様場にもかかわらず方向ドリフトが出る
- `ΔQ`とturn rateの関係が仕様と逆
- 極端に直進し続ける / 毎tick近く方向転換する
- 高Q領域への偏りがrandom walkとの差として検出できない
- seed依存が極端に大きく、再現性がない

## 9. Phase B — 多環境・多seed検証

Phase Aで残った複数候補を E0〜E6 全環境で検証する。

推奨:

- 20,000〜50,000 tick
- 10〜30 seed程度
- 3固定表現型
- pure random / V1.5 WTA / V1.6 temporal の3方式比較

GitHub Actionsのmatrix上限を考慮し、複数workflow runへ分割可能とする。

主判定:

1. E0/E1で偽バイアスがない
2. E2/E3で対応刺激の利用能力が高い表現型ほど高Q領域へ偏る
3. E4で両刺激の協調が見える
4. E5/E6でV1.5 WTAとは異なる統合挙動が出る
5. generalistが両刺激の寄与を実際に受ける
6. 効果がseedを跨いで再現する

## 10. Phase C — 頑健性確認

最終候補について環境強度を変える。

例:

```text
0.5× / 1.0× / 2.0×
```

対象:

- light強度
- chemical供給強度
- gradientの急峻さ

目的:
default環境だけに適合したパラメータではないことを確認する。

必要に応じてworld sizeやsource配置も追加で振る。

## 11. 主評価指標

### 11.1 行動則そのもの

- `P(turn | ΔQ < 0)`
- `P(turn | ΔQ ≈ 0)`
- `P(turn | ΔQ > 0)`

期待:

```text
P(turn | ΔQ < 0)
>
P(turn | ΔQ ≈ 0)
>
P(turn | ΔQ > 0)
```

### 11.2 集団挙動

- high-Q領域滞在率
- source近傍滞在率
- Qの個体平均 / 集団平均
- random walk対比での改善量
- WTA対比での挙動差
- 集団重心・分布の時間推移

### 11.3 複数刺激統合

E5/E6で、lightとchemicalの片方だけでは説明できないQ・滞在・移動パターンが得られることを確認する。

## 12. 可視化

Exp09以降の方針に合わせ、結果本文だけでなくGitHubから直接確認できる軽量PNG/GIFを保存する。

最低限:

1. `ΔQ` vs turn rate
2. 各方式の軌跡比較
3. high-Q領域滞在率の比較
4. E5/E6での空間分布
5. パラメータスイープheatmap
6. 代表seedのGIF

大容量生データは従来どおりGoogle Driveへ退避し、GitHubには要約・図・マニフェストを残す。

## 13. 計算時間の使い方

Exp09実績では25 run × 5,000 tickが数分で完了した。
したがってExp10では単一runを極端に長くするより、条件数・seed数・環境数へ計算資源を配分する。

10時間程度の利用可能時間がある場合、以下を優先する。

1. Phase Aを広く走らせる
2. 残った候補のみPhase Bへ進める
3. 余剰時間をPhase Cの頑健性確認へ使う

ただしGitHub-hosted runnerの並列数・matrix上限・課金/利用制限に従い、workflowを安全に分割する。

## 14. Green判定

Exp10をGreenとする最低条件:

1. Phase 0の決定論・算術診断が全件通る
2. E0/E1で偽の方向性がない
3. `ΔQ`とturn rateの関係が全候補・全seedで仕様と一致する
4. E2/E3でrandom walkより高Q領域滞在率が改善する
5. E5/E6で複数刺激統合の効果が確認できる
6. 効果が特定の1パラメータ点だけに依存しない
7. V1.4/V1.5の吸収物理が変更されていない
8. V1.6内部のseed決定論が成立する

## 15. Exp10が答えないこと

Exp10では以下を結論しない。

- temporal sensingが進化的に選ばれるか
- light specialist / chemical specialist / generalistのどれが長期的に有利か
- chemical bootstrap問題が解決したか
- spatial sensing / directional sensingが進化するか
- 感覚器コストや専門化トレードオフが十分か

これらは行動則Green後の別実験で扱う。

## 16. Exp10後

Exp10がGreenなら、次段で進化をONにした長期実験へ進む。

候補:

- V1.6環境下でlight/chemical利用形質がどのように分化するか
- chemical bootstrapが改善するか
- specialist/generalistの分布がどう変わるか

その前に、有限膜面積・代謝装置コストなどを入れるかは別途レビューする。
