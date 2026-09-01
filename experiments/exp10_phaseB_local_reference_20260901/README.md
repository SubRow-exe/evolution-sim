# Exp10 Phase B — ローカル実行の参考記録（**正式結果ではない**）

日付: 2026-09-01
実行環境: ローカル（Claude Code remote container / Linux）
実行commit: `64f0b5a`
数値実行環境キー: `linux-x86_64-glibc2.39-py3.12.3-np2.5.2`

## この記録の位置づけ

**ここのデータは Exp10 Phase B の正式200 runには含めない。**

正式なPhase Bは、B2を含む全5バッチを **GitHub Actions で統一して実行**する
（人間判断・2026-09-01）。本ディレクトリは

- V1.6実装の再現確認
- Actions結果との突き合わせ材料

としてのみ残す。最終解析にはActionsの結果だけを使う。

## 内容

| ファイル | 中身 |
|---|---|
| `local_reference_runs.csv` | 44 run の per-run 要約（B2 40 run + B1 control 途中4 run） |
| `batch1_b2.log` | バッチ1（B2）の実行ログ全文。停止条件チェックと判定を含む |
| `batch2_b1_interrupted.log` | バッチ2（B1）のログ。人間判断により途中で停止した |

生データ（各runの `stats.csv` / snapshots）はGitへ入れていない。

## B2 の結果（参考値）

40 run（control 20 + treatment 20）、10,000 tick、所要5分。
診断条件チェック 702項目すべてOK。

```text
b2_chem_only_chemspec_treatment: 20/20 seed が 10,000 tick まで生存 (必要 18/20)
```

| | control (gain=0) | treatment (gain=64) |
|---|---:|---:|
| 生存 | 18/20（seed 2, 6 が絶滅） | 20/20 |
| 最終pop 中央値 | 48 | 104 |
| vent滞在率 | 0.780 | 0.846 |
| chemical取得累積 | 208,043 | 468,113 |

`docs/V1.6_Exp10_レビュー.md` B-4 の「定位保持を失うと vent依存の chemical-only
生態が壊れる」という懸念とは逆に、temporal sensing の方が vent 近傍に留まった。

**ただしこれは参考値である。** 正式な §5.5 判定は Actions の結果で行う。

## B1（途中で停止）

control の 4 seed のみ（10,000 tick完走。seed 1-4）。
個体数が約6,500まで増えることを確認した時点で、実行経路の方針変更により停止した。

| tick | population | mean_body_size | 光利用率 |
|---:|---:|---:|---:|
| 20 | 196 | 0.996 | – |
| 4,020 | 1,670 | 0.681 | – |
| 8,080 | 6,511 | 0.226 | 65.5% |

Matterは全期間 3280.00 で厳密に保存されており、V1.6のmobilityが光利用率を
11.7%（V1.5）から65.5%へ引き上げた結果である。詳細は `docs/Exp10_中間報告.md` §3。
