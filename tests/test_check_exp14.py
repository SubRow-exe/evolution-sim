"""tools/check_exp14.py のテスト。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import check_exp14
from tools.exp14_common import TOTAL_RUNS
from tools.make_exp14_configs import build_phase_a


def _write_meta(run_dir: Path, seed: int, git_sha="sha-A", env_key="env-A",
                 incomplete=False) -> None:
    meta = {"seed": seed, "git_sha": git_sha, "numeric_environment": {"env_key": env_key}}
    if incomplete:
        meta["incomplete_resource"] = True
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _stub_run(run_dir: Path, name: str, seed=1, **meta_kwargs) -> Path:
    d = run_dir / name
    d.mkdir(parents=True, exist_ok=True)
    build_phase_a("A0", 2000).to_json(d / "config.json")
    _write_meta(d, seed, **meta_kwargs)
    (d / "stats.csv").write_text("tick,population\n0,100\n2000,50\n", encoding="utf-8")
    return d


def test_check_generated_configs_full_ok():
    errors = check_exp14.check_generated_configs("FULL")
    assert errors == []


def test_expected_run_keys_count():
    assert len(check_exp14.expected_run_keys()) == TOTAL_RUNS


def test_check_run_key_completeness_detects_missing_and_unexpected(tmp_path):
    dirs = [_stub_run(tmp_path, "exp14_A_A0_seed1")]
    errors = check_exp14.check_run_key_completeness(dirs)
    assert any("欠落" in e for e in errors)

    extra = _stub_run(tmp_path, "not_a_real_key")
    errors2 = check_exp14.check_run_key_completeness(dirs + [extra])
    assert any("想定外" in e for e in errors2)


def test_check_run_key_completeness_detects_duplicate(tmp_path):
    d1 = tmp_path / "sub1"
    d2 = tmp_path / "sub2"
    r1 = _stub_run(d1, "exp14_A_A0_seed1")
    r2 = _stub_run(d2, "exp14_A_A0_seed1")
    errors = check_exp14.check_run_key_completeness([r1, r2])
    assert any("重複" in e for e in errors)


def test_environment_integrity_detects_sha_mismatch(tmp_path):
    r1 = _stub_run(tmp_path, "r1", seed=1, git_sha="sha-A")
    r2 = _stub_run(tmp_path, "r2", seed=2, git_sha="sha-B")
    errors = check_exp14.check_run_environment_integrity([r1, r2])
    assert any("git_sha" in e for e in errors)


def test_compare_first_nk_identical_match(tmp_path):
    a = _stub_run(tmp_path, "a")
    b = _stub_run(tmp_path, "b")
    errors = check_exp14.compare_first_nk(a, b, max_tick=2000)
    assert errors == []


def test_main_skip_completeness_allows_partial_collect(tmp_path, capsys, monkeypatch):
    """preflightのE2E smokeは1件だけ配置するため、既定の完全性チェックでは
    115件欠落エラーになる。--skip-completeness で回避できることを確認する
    (Actions run 33759888896で発生した実障害の回帰テスト)。
    """
    _stub_run(tmp_path, "exp14_A_A0_seed1")
    monkeypatch.setattr(sys, "argv", ["check_exp14.py", str(tmp_path)])
    rc = check_exp14.main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "欠落" in err

    monkeypatch.setattr(sys, "argv", ["check_exp14.py", str(tmp_path), "--skip-completeness"])
    rc2 = check_exp14.main()
    assert rc2 == 0
