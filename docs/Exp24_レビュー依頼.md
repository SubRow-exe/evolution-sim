# Exp24 レビュー判断・実装指示

対象: `docs/Exp24_実験計画.md`

状態: **初回Opus5レビュー反映済み / 人間判断で改訂案を採用 / READY FOR IMPLEMENTATION**

初回レビュー:
- Issue #78
- 原文: `docs/Exp23_Exp24_Opus5レビュー.md` (review branch)

## 人間判断

初回Opus5レビューで指摘されたMUST FIXを採用し、旧single-origin案を破棄してExp24を**recurrent-origin establishment assay**へ変更した。

追加の第二レビューは実施しない。以下の改訂済み条件を正式方針として採用し、Claudeは実装へ進んでよい。

## 採用済みformal design

1. first origin後のinnovation lockは行わない
2. `phototrophy_innovation_prob=0.01/birth` をrun全期間で維持
3. 各独立OFF→ON eventへ `photo_founder_id` を付与し、子孫が継承
4. `phototrophy_loss_prob=0`
5. A2_DYNAMIC_VENT / flux 0, 0.5, 1.5
6. primary contrastは **1.5 vs 0.0**
7. seedは **16 (24001–24016)**
8. formal durationは **1920h**。前半960hに生じたoriginをprimary cohortとし、各originを+960hまで追跡
9. primary endpointは `survive_960` / seed-level establishment rate
10. origin個々を独立replicateとして直接検定せず、seed/runをprimary inferential unitとする
11. apparatus assembly、同一tick複数origin、degenerate demography、runtime checkpointをGateへ含める

## Claudeへの実装指示

`docs/Exp24_実験計画.md` を正本として、Exp24の実装を開始してよい。

実装時に科学条件・seed・flux・成功判定を独自変更しないこと。

順序:

1. `photo_founder_id` と必要なrecording / aggregationを実装
2. unit test / regression test / observation non-interference testを追加
3. preflightを実行
4. lineage inheritance、same-tick multi-origin、apparatus assembly、ledger、determinism、runtime/checkpointをGateで確認
5. Gate PASS時のみformal 48 runを開始
6. Gate FAIL時は自動parameter tuningせず停止し、原因を報告
7. formal完了後にaggregateとExp24結果考察用データを保存

## 注意

- `0.01/birth` はorigin供給を観測可能にするためのexperimental accelerationであり、自然界のinnovation率を表さない。
- Exp24の目的は「Phototrophyが新規出現し、光量によってその系統の定着確率が変わるか」の検証である。
- 実行時間上Actions timeoutに抵触する場合は、科学条件を変えずcheckpoint/resumeなど技術的分割で対応する。

**追加レビュー待ちを理由に実装・実行を停止しないこと。preflight Gateを実行上の停止条件とする。**
