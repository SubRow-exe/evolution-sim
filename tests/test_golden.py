"""結果不変性の回帰テスト (プラットフォーム内)。

高速化やリファクタリングで**結果が1ビットでも変わったら失敗**する。
結果が変われば v1.1-baseline との比較が壊れ、過去の実験が無効になるため、
実装変更と挙動変更を機械的に分離する必要がある。

指紋はOS依存 (math.sin/cos/atan2/hypot と pow が各OSのlibm実装のため
最終ビットが一致しない)。未記録のOSではスキップする。
OSを跨いだ保証は tools/verify_vs_ref.py が担当し、CIはそちらを実行する。

意図的にモデルを変更した場合のみ:
    uv run python tools/golden.py --write
を実行し、変更理由をコミットメッセージに残すこと。
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
    reason=f"このプラットフォーム [{_KEY}] の指紋は未記録 "
           "(指紋はlibmの差でOS依存)。OS横断の検証は tools/verify_vs_ref.py が行う",
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
