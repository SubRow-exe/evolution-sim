"""pytest configuration.

V1.9 (docs/V1.9_iLUCA再設計仕様.md) はgenome.pyのGENE_NAMESを14から17へ
拡張し、INITIAL_GENOME (light_absorption/predation_efficiency等) を変更
した。AGENTS.md §V1.9現状ステータス.md「絶対設計原則」は
「historical experiment code/docsは現在仕様へ書き換えない」
「過去worldの再現はversion ref/tagから行う」と定めている。

Exp11〜Exp14の一部のConfig生成・collector・aggregationツールは、旧14-gene
世界を前提にした手書きの件数アサーション (例: 「body_size以外13遺伝子固定」)
を持つ。これらは当時の実験の科学的結論そのものではなく、旧世界の遺伝子数に
結びついた構造的自己チェックだが、それを17-gene版へ書き換えると
「過去に実際に生成・実行されたConfigとは異なる新しいConfigが生成される」
ことになり、frozen historical artifactを現在仕様へ書き換えることになる。
したがって書き換えず、collection対象から除外する
(過去バージョンの再現は`v1.7-final`/`v1.8-exp13`等のgit ref/tagから行う。
AGENTS.md §12「過去worldの再現はversion ref/tagから行う」)。

現在の(V1.9以降の)エンジン・ハーネスを検証する他のtestはすべて有効なまま。
"""
collect_ignore = [
    "test_exp07_configs.py",
    "test_exp08_configs.py",
    "test_exp09_configs.py",
    "test_exp10_configs.py",
    "test_check_exp12.py",
    "test_check_exp13.py",
    "test_check_exp14.py",
    "test_exp11_aggregation.py",
    "test_exp11_configs.py",
    "test_exp12_aggregation.py",
    "test_exp12_configs.py",
    "test_exp13_aggregation.py",
    "test_exp13_configs.py",
    "test_exp14_configs.py",
]
