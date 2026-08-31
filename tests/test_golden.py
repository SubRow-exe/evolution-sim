"""結果不変性の回帰テスト (記録済み数値実行環境内)。

高速化やリファクタリングで**同一数値実行環境の結果が1ビットでも変わったら失敗**する。
結果が変われば v1.1-baseline との比較が壊れ、過去の実験が無効になるため、
実装変更と挙動変更を機械的に分離する必要がある。

指紋は数値実行環境依存で、Windows/Linux間ではlibm差により一致しないことがある。
Goldenは便宜上 `os-machine` キーで保存し、未記録キーではスキップする。
実装変更の比較は tools/verify_vs_ref.py が同じマシン上で旧refと現在実装を直接実行する。

意図的にモデルを変更した場合のみ:
    uv run python tools/golden.py --write
を実行し、変更理由をコミットメッセージに残すこと。

世界バージョン境界では指紋は必ず変わる。V1.2以前の指紋は
`tests/golden_state_v1.2.json` に履歴として残してあり、現行バージョンの
指紋とは比較しない (V1.2の再現には `v1.2-final`、V1.3は `v1.3-final` を使う)。
V1.3では指紋を記録しないまま境界を越えたため、履歴ファイルはV1.2までしかない。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.golden import CASES, GOLDEN_PATH, platform_key, run_case

_STORE = json.loads(GOLDEN_PATH.read_text(encoding="utf-8")) if GOLDEN_PATH.exists() else {}
_KEY = platform_key()

pytestmark = pytest.mark.skipif(
    _KEY not in _STORE,
    reason=f"この環境キー [{_KEY}] の指紋は未記録 "
           "(指紋は数値実行環境依存)。実装変更の比較は tools/verify_vs_ref.py が行う",
)


@pytest.mark.parametrize("name,seed,ticks,overrides", CASES,
                         ids=[c[0] for c in CASES])
def test_result_unchanged(name, seed, ticks, overrides):
    golden = _STORE[_KEY]
    assert name in golden, f"{name} の指紋が未記録"
    assert run_case(seed, ticks, overrides) == golden[name], (
        f"{name}: 結果が変わっています。実装変更が挙動を変えました。"
        " 意図した変更なら tools/golden.py --write で更新してください"
    )
