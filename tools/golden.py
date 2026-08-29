"""結果不変性の保証 (最適化の安全網・記録済み数値実行環境内)。

実装を変更したとき **同一数値実行環境で結果が1ビットも変わっていないこと** を検証する。
高速化は「速くなったが結果が変わった」では意味がない。結果が変われば
v1.1-baseline との比較が壊れ、過去の実験が無効になる。

    uv run python tools/golden.py --write    # 現在の実装の指紋を記録
    uv run python tools/golden.py            # 指紋と一致するか検証
    uv run python tools/golden.py --print    # 指紋をJSONで標準出力 (比較ツール用)

## 重要: 指紋は数値実行環境に依存する

本シミュレーションは math.sin / cos / atan2 / hypot と ** 0.75 (pow) を使う。
これらの最終ビットはOS側の数学ライブラリ等に依存し、WindowsとLinuxで一致しないことがある。
その微差は長期シミュレーションで増幅されるため、同じseedでも結果が異なり得る。

指紋は便宜上 `os-machine` をキーとして保存するが、このキーだけで将来の全環境差を
表現できる保証はない。Goldenは記録した環境での高速回帰チェックとして使う。
実装変更の等価性は tools/verify_vs_ref.py で、同じマシン上の旧refと現在実装を直接比較する。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
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


def platform_key() -> str:
    """Golden保存用の粗い環境キー (OS + アーキテクチャ)。"""
    return f"{platform.system().lower()}-{platform.machine().lower()}"


def compute_all() -> dict[str, str]:
    """全ケースの指紋を計算する。verify_vs_ref.py からも使う。"""
    return {name: run_case(seed, ticks, ov) for name, seed, ticks, ov in CASES}


def main() -> None:
    ap = argparse.ArgumentParser(description="結果不変性の検証 (記録済み数値実行環境内)")
    ap.add_argument("--write", action="store_true", help="現在の実装の指紋を記録する")
    ap.add_argument("--print", dest="print_json", action="store_true",
                    help="指紋をJSONで標準出力する (verify_vs_ref.py 用)")
    args = ap.parse_args()

    current = compute_all()
    if args.print_json:
        print(json.dumps(current, indent=2))
        return

    key = platform_key()
    store = (json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
             if GOLDEN_PATH.exists() else {})

    if args.write:
        store[key] = current
        GOLDEN_PATH.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(f"指紋を記録しました [{key}] -> {GOLDEN_PATH}")
        for k, v in current.items():
            print(f"  {k:24s} {v}")
        return

    if key not in store:
        raise SystemExit(
            f"この環境キー [{key}] の指紋が未記録です。\n"
            "指紋は数値実行環境に依存するため他環境の値とは比較できません。\n"
            "--write でこの環境の指紋を記録するか、実装変更の比較には "
            "tools/verify_vs_ref.py を使ってください。")

    golden = store[key]
    ng = [k for k in current if golden.get(k) != current[k]]
    print(f"platform key: {key}")
    for name in current:
        print(f"  [{'NG' if name in ng else 'OK'}] {name:24s} {current[name]}")
    if ng:
        raise SystemExit(f"\n結果が変わっています: {', '.join(ng)}\n"
                         "実装変更が挙動を変えました。意図した変更なら --write で更新し、"
                         "その理由をコミットメッセージに残してください。")
    print("\n全ケース一致。記録済み環境では結果は変わっていません。")


if __name__ == "__main__":
    main()
