"""生物進化シミュレーション エントリポイント。

GUI:       uv run python main.py [--seed N]
ヘッドレス: uv run python main.py --headless --ticks 100000 --seed 42
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from evosim.config import Config
from evosim.simulation import Simulation


def make_run_dir(base: str, seed: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(base) / f"{stamp}_seed{seed}"


def main() -> None:
    ap = argparse.ArgumentParser(description="生物進化シミュレーション (MVP)")
    ap.add_argument("--seed", type=int, default=None, help="乱数シード (省略時はランダム)")
    ap.add_argument("--ticks", type=int, default=100_000, help="ヘッドレス実行tick数")
    ap.add_argument("--headless", action="store_true", help="描画なし高速実行")
    ap.add_argument("--config", type=str, default=None, help="config JSONパス")
    ap.add_argument("--out", type=str, default="runs", help="記録出力先ディレクトリ")
    ap.add_argument("--no-record", action="store_true", help="記録を無効化")
    args = ap.parse_args()

    cfg = Config.from_json(args.config) if args.config else Config()
    seed = args.seed if args.seed is not None else int(time.time()) % 1_000_000

    run_dir = None if args.no_record else make_run_dir(args.out, seed)
    sim = Simulation(cfg, seed, run_dir=run_dir)
    print(f"seed={seed}  run_dir={run_dir}")

    if args.headless:
        t0 = time.perf_counter()
        for i in range(args.ticks):
            sim.step()
            if not sim.organisms:
                print(f"EXTINCT at tick {sim.tick}")
                break
            if (i + 1) % 5000 == 0:
                el = time.perf_counter() - t0
                print(f"tick {sim.tick:>8}  pop {len(sim.organisms):>5}  "
                      f"births {sim.births_cum:>7}  {sim.tick / el:,.0f} t/s")
        el = time.perf_counter() - t0
        print(f"done: {sim.tick} ticks in {el:.1f}s  final pop={len(sim.organisms)}")
        sim.close()
        if run_dir is not None:
            from evosim.render.plots import plot_run
            print(f"plots -> {plot_run(run_dir)}")
    else:
        from evosim.render.renderer import Viewer

        def make_sim():
            new_seed = int(time.time()) % 1_000_000
            new_dir = None if args.no_record else make_run_dir(args.out, new_seed)
            return Simulation(cfg, new_seed, run_dir=new_dir)

        Viewer(sim, make_sim=make_sim).run()


if __name__ == "__main__":
    main()
