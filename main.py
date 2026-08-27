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
    ap.add_argument("--disaster-at", type=str, default=None,
                    help="災害を起こすtick (カンマ区切り可)。例: --disaster-at 25000,50000")
    ap.add_argument("--fix-genes", type=str, default=None,
                    help="変異を止める遺伝子 (カンマ区切り)。アブレーション実験用")
    args = ap.parse_args()

    cfg = Config.from_json(args.config) if args.config else Config()
    if args.fix_genes:
        cfg.fixed_genes = [g.strip() for g in args.fix_genes.split(",") if g.strip()]
    disaster_ticks = set()
    if args.disaster_at:
        disaster_ticks = {int(t) for t in args.disaster_at.split(",") if t.strip()}
    seed = args.seed if args.seed is not None else int(time.time()) % 1_000_000

    run_dir = None if args.no_record else make_run_dir(args.out, seed)
    sim = Simulation(cfg, seed, run_dir=run_dir)
    print(f"seed={seed}  run_dir={run_dir}")
    if cfg.fixed_genes:
        print(f"固定遺伝子 (変異なし): {', '.join(cfg.fixed_genes)}")
    if disaster_ticks:
        print(f"災害予定tick: {sorted(disaster_ticks)}")

    if args.headless:
        t0 = time.perf_counter()
        try:
            for i in range(args.ticks):
                ts = time.perf_counter()
                sim.step()
                dt = time.perf_counter() - ts
                if sim.recorder:
                    sim.recorder.performance(sim, dt)
                if sim.tick in disaster_ticks:
                    from evosim.disasters import random_disaster
                    n = random_disaster(sim)
                    print(f"tick {sim.tick}: 災害発生 — {n} 個体が死亡")
                if not sim.organisms:
                    print(f"EXTINCT at tick {sim.tick}")
                    break
                if cfg.max_population_halt and len(sim.organisms) >= cfg.max_population_halt:
                    print(f"個体数が上限 {cfg.max_population_halt} に到達: "
                          f"tick {sim.tick} で自動保存して停止します")
                    break
                if (i + 1) % 5000 == 0:
                    el = time.perf_counter() - t0
                    print(f"tick {sim.tick:>8}  pop {len(sim.organisms):>5}  "
                          f"births {sim.births_cum:>7}  {sim.tick / el:,.0f} t/s  "
                          f"last {dt*1000:.2f} ms/tick")
        except KeyboardInterrupt:
            print(f"\n中断 (Ctrl+C): tick {sim.tick} までの結果を出力します")
        el = time.perf_counter() - t0
        print(f"done: {sim.tick} ticks in {el:.1f}s  final pop={len(sim.organisms)}")
        if sim.recorder:
            sim.recorder.finalize(sim)
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
