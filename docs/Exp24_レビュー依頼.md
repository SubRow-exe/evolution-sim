# Exp24 第二レビュー依頼

対象: `docs/Exp24_実験計画.md`

状態: **Opus5初回レビュー反映済み / 第二レビュー待ち。承認前に実装・formal runを開始しないこと。**

初回レビュー:
- Issue #78
- 原文: `docs/Exp23_Exp24_Opus5レビュー.md` (review branch)

## 人間判断で採用した変更

旧single-origin案を破棄し、Exp24を**recurrent-origin establishment assay**へ変更した。

主な変更:

1. first origin後のinnovation lockを廃止
2. `phototrophy_innovation_prob=0.01/birth` をrun全期間で維持
3. 各独立OFF→ON eventへ `photo_founder_id` を付与し、子孫が継承
4. `phototrophy_loss_prob=0`
5. A2_DYNAMIC_VENT / flux 0, 0.5, 1.5
6. primary contrastを **1.5 vs 0.0** に変更
7. seedを **16 (24001–24016)** に増加
8. formal durationを **1920h** とし、前半960hに生じたoriginを全て+960hまで追跡
9. primary endpointを `survive_960` / seed-level establishment rateへ変更
10. origin個々を独立replicateとして直接検定せず、seed/runをprimary inferential unitとする
11. apparatus assembly、同一tick複数origin、degenerate demography、runtime checkpointをGateへ追加

## 第二レビューで特に確認してほしい点

### MUST REVIEW

1. **1920h設計の妥当性**
   - 前半960hをorigin accrual cohort、後半を含め各originの+960h follow-upとする設計でよいか
   - 960h以降のoriginをprimaryから除外する扱いが妥当か

2. **primary endpoint**
   - `N_founder(+960h)>0` をoperational establishmentとするのが適切か
   - N>=5等の拡大条件をprimaryへ加えるべきか

3. **統計単位**
   - originをそのまま独立replicate扱いせず、seedごとのestablishment rateをprimaryとする方針が適切か
   - cluster bootstrap方法をどう固定すべきか

4. **Strong Support proposal**
   - F2−F0が16 seed中12 seed以上で正
   - median差 > 0
   - seed-cluster bootstrap 95% CI下限 > 0
   の3条件が妥当か

5. **16 seed / origin数 / 検出力**
   - 改訂後のformal designで事前powerが十分か、正式実装前に再計算すること
   - origin間相関を考慮したpower estimateを可能な範囲で出すこと

6. **`photo_founder_id`実装**
   - OFF→ON newbornで新規付与
   - ON子孫が継承
   - 同一tick複数originを区別
   - recorder専用stateがsimulation挙動へ非干渉
   が成立する実装案を確認すること

7. **founder apparatus assembly**
   - innovation founderが局所fixed-Nから装置を組み立てる現行経路
   - assembly完了前はphoto credit 0
   - structural N ledger closure
   をpreflightで十分検証できるか

8. **runtime feasibility**
   - 48 × 1920h runのwall-clock見積もり
   - Actions timeoutを超える場合のcheckpoint/resume設計
   - checkpointがRNG/state/ledgerを完全に再開できるか

### SHOULD REVIEW

9. F1=0.5をsecondary dose-responseとして残す妥当性
10. degenerate demography runの扱い
11. per-origin / per-run CSV schema
12. Exp24成功時にV1.11をcloseできるか

## レビュー出力形式

- MUST FIX
- SHOULD FIX
- ACCEPTABLE
- 推奨する最終formal design
- 事前power / runtime概算

を分けてください。

**レビュー段階では科学条件・コードを独自に変更せず、変更提案として返してください。**
