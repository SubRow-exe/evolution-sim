# Exp23 結果考察 — Phototrophy 直接競争実験

更新: 2026-09-16  
状態: **RESULT / COMPLETE**  
対象version: **V1.11**

関連:

- `docs/Exp23_実験計画.md`
- `docs/Exp22_結果考察.md`
- `docs/Exp22_Opus5レビュー.md`
- GitHub Actions run: `34951226448`
- 実装commit: `14efcc9f9a9c69b8233fd57cc3762a3b8f8d149b`

---

## 1. 目的

Exp23は、Phototrophyを最初から持つON系統と、持たないOFF系統を同一世界内で50:50から直接競争させ、Exp22で確認した生理的利益が実際の自然選択・系統頻度変化へ変換されるかを検証した。

A2_DYNAMIC_VENT、120 physical hours、8 seeds、photon flux 0 / 0.5 / 1.5 µmol photons m^-2 s^-1で実施した。

formal runは **24/24 run完了**、preflight G0-G10 / aggregate / completeness gateはいずれもPASSした。

---

## 2. 主結果

120 h時点のPhototrophy ON系統頻度:

| photon flux [µmol m^-2 s^-1] | 初期 | 120h中央値 | 範囲 | ON > 50% のseed |
|---:|---:|---:|---:|---:|
| 0.0 | 50% | **49.65%** | 44.44–52.25% | 3/8 |
| 0.5 | 50% | **55.65%** | 50.00–67.39% | **7/8** |
| 1.5 | 50% | **63.17%** | 50.00–77.14% | **7/8** |

aggregateでは、flux増加に対するON頻度中央値の応答は単調増加だった。

```text
0.0  -> 49.6%
0.5  -> 55.6%
1.5  -> 63.2%
```

したがって、Phototrophyへの選択圧は光量に依存して強くなる。

---

## 3. 本命 flux=0.5 の結果

事前登録したprimary conditionは `0.5 µmol m^-2 s^-1`。

結果:

- 8 seed中 **7 seed** でON頻度 > 50%
- 120h中央値 **55.65%**
- 初期50%からの中央値変化 **+5.65 percentage points**
- ON-OFF出生数差の中央値 **+16.5**
- ON-OFF死亡数差の中央値 **-6.5**

事前登録したstrong-support目安

```text
7/8以上のseedでON増加
final median f_photo >= 53%
```

を両方満たした。

Phototrophyの利益は、単なるstored Energy差ではなく、**生存と繁殖を通じて実際の系統頻度上昇へ変換された**と判断できる。

---

## 4. positive control flux=1.5

`1.5 µmol m^-2 s^-1`ではON頻度中央値は **63.17%**。

さらに、

- 出生数差 ON-OFF: 中央値 **+46**
- 死亡数差 ON-OFF: 中央値 **-24**

となり、0.5より明確に強い選択が確認された。

したがって、0.5での効果が偶然のアッセイ分岐ではなく、同じPhototrophy機構の光量依存応答上にあることをpositive controlが支持する。

---

## 5. zero-light control

flux=0ではON頻度中央値は **49.65%**で、120hの系統頻度としてはほぼ中立だった。

Exp22 A0/zero-light診断ではPhototrophy装置を持つこと自体に小さい維持コストが確認されているが、Exp23のA2・120h競争では、そのコストだけでON系統を一貫して減少させるほどの頻度差にはならなかった。

したがってExp23から言えるのは、

> 光なしで強い負の選択が確認された

ではなく、

> **光なしでは明確な正の選択はなく、0.5以上の光を与えると明確な正の選択へ移る**

である。

---

## 6. seed 23008について

seed 23008では全fluxで最終系統頻度が50:50のままだった。

このseedでは両系統の出生・死亡イベントが頻度差を作らない展開となったため、lineage frequency上の選択を検出できなかった。ただし高fluxではON側のliving matter増加は確認されており、Phototrophy経路そのものが停止していたわけではない。

この点はExp21のA0対照と同様、**頻度が動かなかったことと生理的効果が存在しないことを同一視しない**。

---

## 7. Exp23最終判断

**Exp23は成功と判定する。**

確認できたこと:

1. physical modeの同一集団内でPhototrophy ON/OFFが競争できる
2. flux=0.5でON系統が8 seed中7 seedで増加する
3. flux=1.5ではさらに強い頻度上昇が起きる
4. 光量増加に対しON頻度中央値が単調に増加する
5. 生理的な光Energy利益が、生存・繁殖差を経由して自然選択へ変換される

したがってV1.11では、

> **既に存在するPhototrophyというstanding variationに対し、十分な光が正の自然選択を生み、Phototrophy系統を集団内で増加させる**

ことを直接確認した。

---

## 8. まだ確認していないこと

Exp23は最初から50%の個体へPhototrophyを人為的に与えている。

したがって、まだ確認していないのは以下。

- Phototrophyを持たない集団からstructural innovationとして能力が新規出現すること
- 1個体程度のrare originから、その子孫系統が生き残り・拡大できること
- recurrent innovation/lossを含む完全な長期進化でPhototrophyが成立すること
- continuous gene evolutionとPhototrophy capability evolutionの共進化
- day/night cycle下での適応

次段Exp24では、まず **de novo structural innovationからrare lineageが成立するか** を検証する。

---

## 9. 一文要約

**Exp23は、Phototrophy OFF/ONを50:50で直接競争させ、A2_DYNAMIC_VENTにおいて光量0.5でON系統が中央値55.6%、1.5で63.2%まで増加することを確認し、Phototrophyの生理的利益が実際の光依存自然選択へ変換されることを示した。**
