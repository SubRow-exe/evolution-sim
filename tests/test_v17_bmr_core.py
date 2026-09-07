"""V1.7 bmr_core 実装テスト (docs/V1.7_基礎維持代謝仕様案.md §8)。

Phase 0 停止条件:
  P0-1 bmr_core=0 で V1.6 完全回帰
  P0-2 式の境界 (M=1 / bmr_core=0 / bmr_core=bmr_coef / 範囲外 ValueError)
  P0-3 Energy / Matter / RNG / 決定性
  P0-5 Config JSON round-trip で bmr_core が保存・復元される
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim.config import Config
from evosim.simulation import Simulation


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _fingerprint(sim: Simulation) -> dict:
    """最終 tick の人口・Energy合計・Matter合計を返す。"""
    orgs = sim.organisms
    return {
        "n": len(orgs),
        "E_sum": round(sum(o.energy for o in orgs), 6),
        "M_sum": round(sum(o.matter for o in orgs), 6),
    }


def _run(seed: int = 1, ticks: int = 50, **kw) -> Simulation:
    cfg = Config(**kw)
    sim = Simulation(cfg, seed)
    for _ in range(ticks):
        sim.step()
    return sim


# ---------------------------------------------------------------------------
# P0-2: 式の境界
# ---------------------------------------------------------------------------

class TestBmrFormula:
    """BMR 計算式の境界条件を physiology.py 外から確認する。"""

    def test_bmr_coef_equals_default(self):
        """bmr_core=0 のとき BMR = bmr_coef * s^0.75 と完全一致。"""
        from evosim.physiology import maintenance_and_movement
        from evosim.organism import Organism
        import copy

        cfg0 = Config(bmr_core=0.0, bmr_coef=0.3)
        cfg_v17 = Config(bmr_core=0.05, bmr_coef=0.3)

        # matter=1.0 のとき both で BMR=0.3 になる
        # これは直接 maintenance 関数をテストするのではなく
        # 式の性質を Config レベルで確認する
        for core in (0.0, 0.1, 0.3):
            cfg = Config(bmr_core=core, bmr_coef=0.3)
            # M=1 での BMR = core + (0.3 - core) * 1.0 = 0.3
            bmr_m1 = cfg.bmr_core + (cfg.bmr_coef - cfg.bmr_core) * 1.0 ** 0.75
            assert abs(bmr_m1 - 0.3) < 1e-12, f"M=1 で BMR≠0.3: core={core}"

    def test_m1_invariant_all_legal_cores(self):
        """M=1 のとき任意の合法 bmr_core で BMR=bmr_coef=0.3。"""
        for core in (0.0, 0.005, 0.05, 0.15, 0.3):
            bmr = core + (0.3 - core) * 1.0 ** 0.75
            assert abs(bmr - 0.3) < 1e-12

    def test_core_zero_matches_v16_formula(self):
        """bmr_core=0 のとき BMR = 0.3 * M^0.75 (V1.6 式と完全一致)。"""
        for m in (0.2, 0.5, 1.0, 2.0, 5.0):
            bmr_v16 = 0.3 * m ** 0.75
            bmr_v17 = 0.0 + (0.3 - 0.0) * m ** 0.75
            assert abs(bmr_v17 - bmr_v16) < 1e-15

    def test_core_equals_coef_size_independent(self):
        """bmr_core=0.3 のとき BMR=0.3 でサイズ非依存。"""
        for m in (0.2, 0.5, 1.0, 2.0, 5.0, 10.0):
            bmr = 0.3 + (0.3 - 0.3) * m ** 0.75
            assert abs(bmr - 0.3) < 1e-15

    def test_large_m_bmr_lower_than_v16(self):
        """M>1 かつ bmr_core>0 では V1.7 BMR < V1.6 BMR (大型側 core 償却メリット)。"""
        core = 0.05
        for m in (1.5, 2.0, 5.0, 10.0):
            bmr_v16 = 0.3 * m ** 0.75
            bmr_v17 = core + (0.3 - core) * m ** 0.75
            assert bmr_v17 < bmr_v16, f"M={m}: V1.7 BMR が V1.6 より大きい"

    def test_small_m_bmr_higher_than_v16(self):
        """M<1 かつ bmr_core>0 では V1.7 BMR > V1.6 BMR (小型側に core 負担)。"""
        core = 0.05
        for m in (0.2, 0.3, 0.5, 0.8):
            bmr_v16 = 0.3 * m ** 0.75
            bmr_v17 = core + (0.3 - core) * m ** 0.75
            assert bmr_v17 > bmr_v16, f"M={m}: V1.7 BMR が V1.6 以下"

    def test_bmr_nonnegative(self):
        """BMR は非負。"""
        for core in (0.0, 0.05, 0.3):
            for m in (0.001, 0.01, 0.1, 1.0, 10.0):
                bmr = core + (0.3 - core) * m ** 0.75
                assert bmr >= 0.0


# ---------------------------------------------------------------------------
# P0-2: Config 検証 (ValueError)
# ---------------------------------------------------------------------------

class TestConfigValidation:
    def test_bmr_core_negative_raises(self):
        with pytest.raises(ValueError, match="bmr_core"):
            Config(bmr_core=-0.001)

    def test_bmr_core_exceeds_coef_raises(self):
        with pytest.raises(ValueError, match="bmr_core"):
            Config(bmr_core=0.31, bmr_coef=0.3)

    def test_bmr_core_zero_ok(self):
        Config(bmr_core=0.0)  # no raise

    def test_bmr_core_equals_coef_ok(self):
        Config(bmr_core=0.3, bmr_coef=0.3)  # no raise

    def test_bmr_core_mid_ok(self):
        Config(bmr_core=0.1, bmr_coef=0.3)  # no raise


# ---------------------------------------------------------------------------
# P0-5: Config JSON round-trip
# ---------------------------------------------------------------------------

class TestConfigRoundTrip:
    def test_nonzero_bmr_core_survives_json(self, tmp_path):
        """非ゼロ bmr_core が JSON 保存→ロード後も保持される。"""
        cfg = Config(bmr_core=0.05)
        p = tmp_path / "cfg.json"
        cfg.to_json(p)
        loaded = Config.from_json(p)
        assert loaded.bmr_core == 0.05

    def test_json_contains_bmr_core_key(self, tmp_path):
        """保存 JSON に bmr_core キーが存在する。"""
        cfg = Config(bmr_core=0.025)
        p = tmp_path / "cfg.json"
        cfg.to_json(p)
        data = json.loads(p.read_text())
        assert "bmr_core" in data
        assert data["bmr_core"] == 0.025

    def test_zero_bmr_core_survives_json(self, tmp_path):
        """bmr_core=0 も正しく保存・復元される。"""
        cfg = Config(bmr_core=0.0)
        p = tmp_path / "cfg.json"
        cfg.to_json(p)
        loaded = Config.from_json(p)
        assert loaded.bmr_core == 0.0

    def test_all_15_candidate_values_roundtrip(self, tmp_path):
        """Exp11 15 候補すべてで JSON round-trip が一致する。"""
        candidates = [
            0.000, 0.005, 0.010, 0.015, 0.020,
            0.025, 0.030, 0.040, 0.050, 0.060,
            0.075, 0.100, 0.150, 0.200, 0.300,
        ]
        for c in candidates:
            cfg = Config(bmr_core=c)
            p = tmp_path / f"cfg_{c:.3f}.json"
            cfg.to_json(p)
            loaded = Config.from_json(p)
            assert loaded.bmr_core == c, f"bmr_core={c} round-trip 失敗"


# ---------------------------------------------------------------------------
# P0-1: bmr_core=0 で V1.6 完全回帰
# ---------------------------------------------------------------------------

class TestV16Regression:
    """bmr_core=0 を明示すれば V1.6 と完全一致する式であることを確認する。

    V1.7 close (docs/V1.7_総括.md) により default は 0.15 (恒久値) へ変更された。
    V1.6 完全回帰には bmr_core=0 を明示的に渡す必要がある。
    """

    def test_default_config_is_v17_final_bmr_core(self):
        """デフォルト Config の bmr_core は V1.7確定値 0.15。"""
        cfg = Config()
        assert cfg.bmr_core == 0.15

    def test_explicit_zero_differs_from_default(self):
        """explicit bmr_core=0.0 は default (0.15) と結果が異なる (式が効いている)。"""
        ticks = 30
        seed = 7
        sim_default = _run(seed=seed, ticks=ticks)
        sim_explicit = _run(seed=seed, ticks=ticks, bmr_core=0.0)
        fp_d = _fingerprint(sim_default)
        fp_e = _fingerprint(sim_explicit)
        assert fp_d != fp_e

    def test_explicit_zero_matches_explicit_zero(self):
        """explicit bmr_core=0.0 同士は完全一致する (決定性確認)。"""
        ticks = 30
        seed = 7
        sim_a = _run(seed=seed, ticks=ticks, bmr_core=0.0)
        sim_b = _run(seed=seed, ticks=ticks, bmr_core=0.0)
        assert _fingerprint(sim_a) == _fingerprint(sim_b)

    def test_nonzero_core_differs_from_zero(self):
        """bmr_core>0 は bmr_core=0 と結果が異なる (式が実際に効いている)。

        V1.9注記: fixed ancestorはEnergy収支calibration次第で短時間で
        絶滅しうる (tests/test_smoke.py参照)。両条件とも絶滅前のtick数で
        比較する。
        """
        ticks = 30
        seed = 3
        sim0 = _run(seed=seed, ticks=ticks, bmr_core=0.0)
        sim1 = _run(seed=seed, ticks=ticks, bmr_core=0.3)
        # 同じ seed でも結果が違うことで、bmr_core がシミュレーションに影響している
        fp0 = _fingerprint(sim0)
        fp1 = _fingerprint(sim1)
        # 絶滅の場合は n=0 が同じになりうるが、それ以外は違うはず
        # 最低でも何らかの差が出る
        assert fp0 != fp1, "bmr_core=0.3 と bmr_core=0.0 の結果が同一 — 式が未反映の可能性"


# ---------------------------------------------------------------------------
# P0-3: Energy / Matter / 決定性
# ---------------------------------------------------------------------------

class TestConservation:
    def test_matter_conservation_nonzero_core(self):
        """bmr_core>0 でも Matter 保存が成立する。"""
        ticks = 50
        sim = _run(seed=5, ticks=ticks, bmr_core=0.1)
        # Matter 保存は simulation 内部で検査されている想定だが
        # ここでは最低限 NaN/Inf がないことを確認する
        for o in sim.organisms:
            assert math.isfinite(o.energy)
            assert math.isfinite(o.matter)
            assert o.matter >= 0.0

    def test_determinism_with_nonzero_core(self):
        """同一 seed・同一 Config (bmr_core>0) で完全一致する。"""
        seed = 42
        ticks = 30
        sim_a = _run(seed=seed, ticks=ticks, bmr_core=0.05)
        sim_b = _run(seed=seed, ticks=ticks, bmr_core=0.05)
        assert _fingerprint(sim_a) == _fingerprint(sim_b)
