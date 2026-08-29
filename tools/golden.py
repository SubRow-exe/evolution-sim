"""結果不変性の保証 (最適化の安全網)。

シミュレーションの内部実装を変更したとき、**結果が1ビットも変わっていないこと**を
検証する。高速化は「速くなったが結果が変わった」では意味がない。
結果が変われば v1.1-baseline との比較が壊れ、過去の実験がすべて無効になる。

    uv run python tools/golden.py --write    # 現在の実装の指紋を記録
    uv run python tools/golden.py            # 現在の実装が指紋と一致するか検証
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.simulation import Simulation

GOLDEN_PATH = ROOT / "tests" / "golden_state.json"

# (名前, seed, ticks, config上書き) — 主要な経路を通す組み合わせ
CASES = [
    ("default_s1_2000", 1, 2000, {}),
    ("default_s4_2000", 4, 2000, {}),
    ("fixed_body_s4_1200", 4, 1200, {"fixed_genes": ["body_size"]}),
    ("dense_s7_1500", 7, 1500, {"initial_population": 300}),
]


def fingerprint(sim: Simulation) -> str:
    """全個体・全フィールドをビット単位で畳み込んだ指紋。

    float は struct で生のIEEE754バイト列にするため、丸め表示による
    差異の見逃しが起きない。
    """
    h = hashlib.blake2b(digest_size=16)

    def f(*vals: float) -> None:
        h.update(struct.pack(f"<{len(vals)}d", *vals))

    def i(*vals: int) -> None:
        h.update(struct.pack(f"<{len(vals)}q", *vals))

    i(sim.tick, sim.next_id, sim.births_cum, sim.deaths_cum, len(sim.organisms),
      len(sim.corpses))
    for cause in sorted(sim.deaths_by_cause):
        i(sim.deaths_by_cause[cause])
    f(sim.energy_in_cum, sim.energy_out_cum)
    for k in sorted(sim.flows):
        f(sim.flows[k])

    for o in sim.organisms:
        i(o.id, o.parent_id, o.lineage_id, o.generation, o.birth_tick, o.age)
        f(o.x, o.y, o.heading, o.energy, o.matter, o.damage)
        f(*(float(g) for g in o.genome))
    for c in sim.corpses:
        f(c.x, c.y, c.matter, c.energy)

    h.update(sim.world.nutrients.tobytes())
    h.update(sim.world.chemical.tobytes())
    h.update(sim.world.light.tobytes())
    return h.hexdigest()


def run_case(seed: int, ticks: int, overrides: dict) -> str:
    sim = Simulation(Config(**overrides), seed)
    for _ in range(ticks):
        sim.step()
    return fingerprint(sim)


def main() -> None:
    ap = argparse.ArgumentParser(description="結果不変性の検証")
    ap.add_argument("--write", action="store_true", help="現在の実装の指紋を記録する")
    args = ap.parse_args()

    current = {name: run_case(seed, ticks, ov) for name, seed, ticks, ov in CASES}

    if args.write:
        GOLDEN_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"指紋を記録しました -> {GOLDEN_PATH}")
        for k, v in current.items():
            print(f"  {k:24s} {v}")
        return

    if not GOLDEN_PATH.exists():
        raise SystemExit(f"{GOLDEN_PATH} がありません。先に --write を実行してください")
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    ng = [k for k in current if golden.get(k) != current[k]]
    for name in current:
        mark = "NG" if name in ng else "OK"
        print(f"  [{mark}] {name:24s} {current[name]}")
    if ng:
        raise SystemExit(f"\n結果が変わっています: {', '.join(ng)}\n"
                         "実装変更が挙動を変えました。意図した変更なら --write で更新し、"
                         "その理由をコミットメッセージに残してください。")
    print("\n全ケース一致。結果は変わっていません。")


if __name__ == "__main__":
    main()
