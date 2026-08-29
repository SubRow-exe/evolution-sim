"""結果不変性の回帰テスト。

高速化やリファクタリングで**結果が1ビットでも変わったら失敗**する。
結果が変われば v1.1-baseline との比較が壊れ、過去の実験が無効になるため、
実装変更と挙動変更を機械的に分離する必要がある。

意図的にモデルを変更した場合のみ:
    uv run python tools/golden.py --write
を実行し、変更理由をコミットメッセージに残すこと。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.golden import CASES, GOLDEN_PATH, run_case


@pytest.mark.parametrize("name,seed,ticks,overrides", CASES,
                         ids=[c[0] for c in CASES])
def test_result_unchanged(name, seed, ticks, overrides):
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert name in golden, f"{name} の指紋が未記録"
    assert run_case(seed, ticks, overrides) == golden[name], (
        f"{name}: 結果が変わっています。実装変更が挙動を変えました。"
        " 意図した変更なら tools/golden.py --write で更新してください"
    )
