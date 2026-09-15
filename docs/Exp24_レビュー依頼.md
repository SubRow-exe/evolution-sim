# Exp24 レビュー依頼

対象: `docs/Exp24_実験計画.md`

状態: **レビュー待ち。レビュー完了前に実装・formal runを開始しないこと。**

Claude / Opusには、特に以下を確認してほしい。

1. `phototrophy_innovation_prob` default `1e-4/birth`をそのまま使わず、origin待ち時間短縮のため `0.01/birth`へ一時的に上げる設計の妥当性
2. first origin後にinnovation probabilityを0へ戻し、single-origin lineageだけを追う方法の妥当性
3. loss probabilityを0に固定する案の妥当性
4. waiting window 240h + post-origin 240hの計算時間・検出力
5. 同一seedのflux 0 / 0.5 / 1.5でfirst origin tick / founder IDまで一致させられるか
6. first origin後のPhototrophy ON個体をそのfounderの子孫とみなすために追加trackingが必要か
7. 8 seed、strong-support 6/8基準の妥当性
8. rare mutantからのselectionを測るprimary endpointとして `N_photo(+240h)` / `f_photo(+240h)` が適切か
9. recurrent innovationを先に実施すべき理由があるか
10. 成功時に「de novo Phototrophy evolution」と表現できる範囲

レビューでは、単なる賛否だけでなく、実装前に修正すべきMUST FIXと、任意のSHOULD FIXを分けること。

関連:
- `docs/Exp23_結果考察.md`
- `docs/Exp22_結果考察.md`
- `docs/Exp22_Opus5レビュー.md`
- `evosim/genome.py`
- `evosim/simulation.py`
