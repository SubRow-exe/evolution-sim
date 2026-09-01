"""check_exp10.py の回帰テスト。

Exp10 Phase B の正式実行 (Actions run 33476692068) で、chemical-only control の
一部 seed が絶滅 (個体数0で終了) したとき、絶滅した run の最終snapshotが
個体0＝空になり、`min(vals)` / `max(vals)` が空列で ValueError を投げて
collect job を落とした。絶滅は Exp10 では測定結果であり整合性違反ではないので、
空snapshotは検証対象なしとしてスキップしなければならない。
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.check_exp10 import snapshot_gene


def _write_snapshot(run: Path, tick: int, rows: list[dict], cols: list[str]):
    snaps = run / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    with open(snaps / f"snap_{tick:08d}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_snapshot_gene_returns_empty_list_for_extinct_run(tmp_path):
    """絶滅run: 最終snapshotがヘッダのみ (個体0) なら空リストを返す。"""
    run = tmp_path / "run_seed1"
    cols = ["id", "x", "y", "body_size", "light_absorption"]
    _write_snapshot(run, 100, [{"id": 0, "x": 1, "y": 2,
                                "body_size": 1.0, "light_absorption": 0.3}], cols)
    _write_snapshot(run, 200, [], cols)  # 絶滅: 個体0
    vals = snapshot_gene(run, "body_size")
    assert vals == [], "空の最終snapshotは空リストを返すべき"


def test_snapshot_gene_reads_last_snapshot_when_populated(tmp_path):
    run = tmp_path / "run_seed2"
    cols = ["id", "body_size"]
    _write_snapshot(run, 100, [{"id": 0, "body_size": 1.0}], cols)
    _write_snapshot(run, 200, [{"id": 0, "body_size": 1.0},
                               {"id": 1, "body_size": 1.0}], cols)
    assert snapshot_gene(run, "body_size") == [1.0, 1.0]


def test_no_snapshots_returns_none(tmp_path):
    run = tmp_path / "run_seed3"
    run.mkdir()
    assert snapshot_gene(run, "body_size") is None


def test_empty_snapshot_is_falsy_so_min_max_are_skipped(tmp_path):
    """バグの核心: 空リストは falsy で、`if vals:` によって min/max をスキップ。
    None・空・非空の3状態がガードで正しく分岐することを固定する。"""
    run = tmp_path / "run_seed4"
    cols = ["id", "body_size"]
    _write_snapshot(run, 10, [], cols)
    vals = snapshot_gene(run, "body_size")
    assert vals == [] and not vals  # falsy: `if vals:` が偽になる
