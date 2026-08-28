# GitHub Projects 運用方針

## 目的

GitHub Projectsを、このプロジェクト全体の「司令塔」として使う。

役割分担:

- **Project**: 何を今やるか、次に何をやるかの俯瞰
- **Issue**: 1つの実験・機能・調査テーマ
- **PR**: 実際のコード/ドキュメント変更
- **docs/**: 長文の設計思想・考察・ロードマップ
- **experiments/**: 実験結果

## 推奨Projectビュー

### Board

- Backlog
- Next
- In Progress
- Experiment Running
- Analysis
- Done

### Table

推奨フィールド:

- Status
- Version: V1 / V2 / V3+ / Long-term
- Type: Experiment / Feature / Visualization / Performance / Research
- Priority: High / Medium / Low
- Scale: Small / Medium / Large

## バージョン方針

- **V1系**: 原始生命・単細胞的な世界。環境・資源・遺伝機構の複雑化も、身体構造が原始的な間はV1として扱う
- **V2系**: 身体構造そのものが進化し、形態が物理性能を決める世界
- **V3以降**: 多細胞化、神経・学習、社会・文化等

## 現在のIssue構成

### 今すぐ進めるV1実験

- #3 Exp03: 転移の発生率と時期を20 Seedで測定
- #4 Exp04: アブレーションで転移の必要条件を特定
- #5 Exp05: 転移後150k tickの長期挙動
- #6 Exp06: 災害タイミングの影響

### V1観測・解析

- #7 支配系統の祖先追跡・進化ブレークスルー検出
- #8 GUI環境レイヤー分離とHTML実験レポート
- #9 Seed横断の生態型分類・命名・収斂進化検出
- #15 原始生命の見た目多様化

### V1大型Backlog

- #10 環境・資源・災害の複雑化
- #11 原始的DNA交換から有性生殖的機構を進化可能にする

### V2以降

- #12 身体構造進化: Genome→Development→Body→Physics
- #13 異星環境・代替溶媒・非地球型生命モデル

### 基盤

- #14 遠隔実行・複数Seed並列化・性能プロファイル

### 親Issue

- #2 Evolution Sim 開発・実験バックログ

## 運用ルール

1. 思いついた大型アイデアはまずBacklog Issueへ追加する
2. 実装前に、既存Issueで扱えるか確認する
3. 実験は原則1 Issue = 1問い
4. 世界ルールを変えない実験と、世界ルールを変える機能追加を分ける
5. 実験完了後は `experiments/` と `NOTES.md` を保存し、Issueへ結果を要約してCloseする
6. 実装PRには対応Issueを紐付ける
7. 詳細な科学的考察はdocsへ残し、Issueは進捗と結論を簡潔に保つ
8. 多様性を直接作り込まず、環境・ニッチ・資源・遺伝機構から創発させる

## 当面の順番

1. #3 Exp03
2. #4 Exp04
3. #5 Exp05
4. #7 祖先追跡（Exp03〜05の解析価値を高めるため）
5. #6 Exp06
6. #8 / #9 観測・分類機能
7. #10 / #11 V1世界の拡張
8. #12 V2身体構造進化

GitHub Projects本体では、このIssue群をBoard/Tableへ追加して管理する。