"""シミュレーション計算性能のベンチマーク (クラウド環境選定用の基準値取得)。

ローカルPC / GitHub Codespaces / クラウド計算環境で**同一条件**を実行し、
結果を比較できるようにする。描画・UI・記録I/Oを除いた
「純粋なシミュレーション計算性能」を測ることを主目的とする。

    uv run python tools/benchmark.py                      # 標準 (約2〜4分)
    uv run python tools/benchmark.py --quick              # 短縮 (約40秒)
    uv run python tools/benchmark.py --scaling 1,2,4,8    # 並列スケーリングも測る
    uv run python tools/benchmark.py --full               # 全項目
    uv run python tools/benchmark.py --out bench_local.json
    uv run python tools/benchmark.py --compare a.json b.json

## 設計方針

- **既存コードを一切変更しない。** evosim は import して使うだけ
- 固定seed・固定Config・固定tick数で完全に再現可能
- 記録 (Recorder) は既定で無効。I/O影響を除く。別項目で影響量を測る
- 描画は既定で測らない。`--full` 時に SDL のダミードライバで測る
- psutil が無い環境でも、取れる範囲で動作する

## 測定シナリオ

個体数は世代とともに増えるため、「初期個体数 + ウォームアップtick数」を
固定することで測定時点の個体数を決定的にしている (結果に population を併記)。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from evosim.config import Config
from evosim.simulation import Simulation

try:
    import psutil
except ImportError:  # psutil が無い環境でも動かす
    psutil = None

SCHEMA = 1

# (名前, Config上書き, seed, ウォームアップtick, 計測tick)
SCENARIOS = {
    "light": ({}, 1, 300, 1500),
    "standard": ({}, 1, 5000, 2000),
    "dense": ({"initial_population": 3000}, 11, 200, 300),
}
QUICK = {
    "light": ({}, 1, 200, 500),
    "dense": ({"initial_population": 3000}, 11, 150, 120),
}

# cProfile の関数を処理フェーズへ対応付ける (ファイル名の末尾, 関数名) -> フェーズ
PHASE_MAP = {
    ("world.py", "update"): "環境更新",
    ("simulation.py", "_build_hashes"): "空間インデックス構築",
    ("simulation.py", "_photo_weights"): "光の分配計算",
    ("behavior.py", "decide_and_move"): "行動判断 (AI) と移動",
    ("simulation.py", "_absorb"): "資源吸収",
    ("simulation.py", "_eat_corpse"): "死骸摂取 (接触判定)",
    ("simulation.py", "_predate"): "捕食 (接触判定)",
    ("physiology.py", "maintenance_and_movement"): "生理 (代謝・移動コスト)",
    ("physiology.py", "repair"): "生理 (修復)",
    ("simulation.py", "_try_reproduce"): "繁殖・突然変異",
    ("simulation.py", "_decay_corpses"): "死骸分解",
    ("simulation.py", "_kill"): "死亡処理",
    ("recorder.py", "stats"): "記録 I/O",
    ("recorder.py", "snapshot"): "記録 I/O",
}


# ---------------------------------------------------------------- 環境情報

def _cpu_model() -> str:
    """CPU型番。platform.processor() は Linux で空になることが多い。"""
    p = platform.processor()
    if p and not p.isdigit():
        return p
    try:
        if platform.system() == "Linux":
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return p or "unknown"


def environment_info() -> dict:
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "logical_cpus": os.cpu_count(),
        "physical_cpus": None,
        "cpu_freq_mhz": None,
        "total_ram_gb": None,
        "cgroup_cpu_limit": _cgroup_cpu_limit(),
        "psutil_available": psutil is not None,
    }
    if psutil:
        try:
            info["physical_cpus"] = psutil.cpu_count(logical=False)
            f = psutil.cpu_freq()
            info["cpu_freq_mhz"] = round(f.max or f.current, 0) if f else None
            info["total_ram_gb"] = round(psutil.virtual_memory().total / 1024 ** 3, 2)
        except (OSError, RuntimeError):
            pass
    # コンテナでは os.cpu_count() が実際に使える数と一致しないことがある
    try:
        info["usable_cpus"] = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
    except AttributeError:
        info["usable_cpus"] = info["logical_cpus"]
    return info


def _cgroup_cpu_limit() -> float | None:
    """コンテナ (Codespaces等) のCPU割当。無ければ None。"""
    for path, parse in (
        ("/sys/fs/cgroup/cpu.max", lambda s: None if s.split()[0] == "max"
         else float(s.split()[0]) / float(s.split()[1])),
        ("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", None),
    ):
        try:
            text = Path(path).read_text().strip()
        except OSError:
            continue
        if parse:
            try:
                return parse(text)
            except (ValueError, IndexError, ZeroDivisionError):
                return None
        try:
            quota = float(text)
            period = float(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
            return quota / period if quota > 0 else None
        except (OSError, ValueError, ZeroDivisionError):
            return None
    return None


# ---------------------------------------------------------------- 計測補助

class ResourceSampler:
    """実行中の RSS と CPU時間をサンプリングする。"""

    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self.peak_rss = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc = psutil.Process() if psutil else None
        self._cpu_start = None

    def __enter__(self):
        if self._proc:
            self._cpu_start = self._proc.cpu_times()
            self.peak_rss = self._proc.memory_info().rss
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        self.wall_start = time.perf_counter()
        return self

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self.peak_rss = max(self.peak_rss, self._proc.memory_info().rss)
            except (psutil.Error, OSError):
                return

    def __exit__(self, *exc):
        self.wall = time.perf_counter() - self.wall_start
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self.cpu_seconds = None
        if self._proc and self._cpu_start:
            e = self._proc.cpu_times()
            self.cpu_seconds = ((e.user - self._cpu_start.user)
                                + (e.system - self._cpu_start.system))
        return False

    @property
    def cpu_utilization(self) -> float | None:
        """1.0 = 1コアを使い切っている。>1.0 なら複数コアを同時使用。"""
        if self.cpu_seconds is None or self.wall <= 0:
            return None
        return self.cpu_seconds / self.wall


# ---------------------------------------------------------------- シナリオ

def run_scenario(name: str, overrides: dict, seed: int,
                 warmup: int, measure: int, record_dir: Path | None = None) -> dict:
    """1シナリオを計測する。ウォームアップは計測に含めない。"""
    sim = Simulation(Config(**overrides), seed, run_dir=record_dir)
    for _ in range(warmup):
        sim.step()
    pop_start = len(sim.organisms)

    per_step = np.empty(measure, dtype=np.float64)
    with ResourceSampler() as s:
        for i in range(measure):
            t0 = time.perf_counter()
            sim.step()
            per_step[i] = time.perf_counter() - t0
    sim.close()

    ms = per_step * 1000.0
    return {
        "scenario": name,
        "seed": seed,
        "config_overrides": overrides,
        "warmup_ticks": warmup,
        "measured_ticks": measure,
        "population_start": pop_start,
        "population_end": len(sim.organisms),
        "corpses_end": len(sim.corpses),
        "recording": record_dir is not None,
        "total_seconds": round(s.wall, 4),
        "ms_per_step_mean": round(float(ms.mean()), 4),
        "ms_per_step_median": round(float(np.median(ms)), 4),
        "ms_per_step_p95": round(float(np.percentile(ms, 95)), 4),
        "steps_per_second": round(measure / s.wall, 2),
        "cpu_seconds": round(s.cpu_seconds, 3) if s.cpu_seconds is not None else None,
        "cpu_utilization_cores": (round(s.cpu_utilization, 3)
                                  if s.cpu_utilization is not None else None),
        "peak_rss_mb": round(s.peak_rss / 1024 ** 2, 1) if s.peak_rss else None,
    }


# ---------------------------------------------------------------- 内訳

def profile_phases(overrides: dict, seed: int, warmup: int, measure: int) -> dict:
    """cProfile で処理フェーズ別の時間内訳を出す。

    プロファイラ自体のオーバーヘッドがあるため、**速度の値には使わない**。
    比率だけを見る。
    """
    import cProfile
    import pstats

    sim = Simulation(Config(**overrides), seed)
    for _ in range(warmup):
        sim.step()

    pr = cProfile.Profile()
    pr.enable()
    for _ in range(measure):
        sim.step()
    pr.disable()

    st = pstats.Stats(pr)
    phases: dict[str, float] = {}
    step_total = 0.0
    for (fn, _line, func), (_cc, _nc, _tt, ct, _cal) in st.stats.items():
        base = os.path.basename(fn)
        if base == "simulation.py" and func == "step":
            step_total = ct
        key = PHASE_MAP.get((base, func))
        if key:
            phases[key] = phases.get(key, 0.0) + ct

    known = sum(phases.values())
    if step_total > known:
        phases["その他 (ループ制御・属性参照など)"] = step_total - known
    total = sum(phases.values()) or 1.0
    return {
        "note": "cProfile計測。オーバーヘッドを含むため比率のみ参照する",
        "population": len(sim.organisms),
        "measured_ticks": measure,
        "phases": {k: {"seconds": round(v, 4), "share": round(v / total, 4)}
                   for k, v in sorted(phases.items(), key=lambda kv: -kv[1])},
    }


# ---------------------------------------------------------------- 並列

def _worker_cmd(ticks: int, seed: int) -> list[str]:
    code = (
        "import sys,time;sys.path.insert(0,r'%s');"
        "from evosim.config import Config;from evosim.simulation import Simulation;"
        "s=Simulation(Config(),%d);t=time.perf_counter();"
        "[s.step() for _ in range(%d)];"
        "print(time.perf_counter()-t)" % (str(ROOT), seed, ticks)
    )
    return [sys.executable, "-c", code]


def scaling_test(worker_counts: list[int], ticks: int) -> dict:
    """同一負荷を N プロセス並列で実行し、総スループットの伸びを測る。

    各プロセスは独立したシミュレーション。プロセス間通信は無い。
    これは「run単位の並列化 (seedを分けて同時実行)」の上限性能に相当する。
    """
    results = []
    base = None
    for n in worker_counts:
        procs = [subprocess.Popen(_worker_cmd(ticks, 100 + i),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) for i in range(n)]
        t0 = time.perf_counter()
        outs = [p.communicate() for p in procs]
        wall = time.perf_counter() - t0
        if any(p.returncode != 0 for p in procs):
            results.append({"workers": n, "error": outs[0][1][-300:]})
            continue
        # 各workerが自身で計測したシミュレーション時間 (プロセス起動を含まない)。
        # wall基準だと Python 起動 (約1秒) が混ざり、並列数が少ないほど
        # 相対的に大きく効いてスケーリングを歪めるため両方を出す。
        sim_times = [float(o[0].strip().splitlines()[-1]) for o in outs]
        total_steps = n * ticks
        thr_wall = total_steps / wall
        thr_sim = total_steps / max(sim_times)  # 最も遅いworkerが律速
        if base is None:
            base = (thr_wall, thr_sim)
        results.append({
            "workers": n,
            "wall_seconds": round(wall, 3),
            "sim_seconds_max": round(max(sim_times), 3),
            "sim_seconds_min": round(min(sim_times), 3),
            "aggregate_steps_per_second": round(thr_wall, 1),
            "aggregate_steps_per_second_simonly": round(thr_sim, 1),
            "speedup_vs_1": round(thr_wall / base[0], 3),
            "speedup_vs_1_simonly": round(thr_sim / base[1], 3),
            "efficiency": round((thr_wall / base[0]) / n, 3),
            "efficiency_simonly": round((thr_sim / base[1]) / n, 3),
        })
    return {"ticks_per_worker": ticks, "results": results}


# ---------------------------------------------------------------- 付随項目

def io_overhead(overrides: dict, seed: int, warmup: int, measure: int) -> dict:
    """記録 (Recorder) を有効にした場合の速度差 = I/O影響。"""
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="evosim_bench_io_"))
    try:
        rec = run_scenario("standard+recording", overrides, seed, warmup, measure,
                           record_dir=tmp / "run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rec


def render_cost(overrides: dict, seed: int, warmup: int, frames: int) -> dict:
    """描画1フレームのコスト。SDLのダミードライバで画面なしに測る。"""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    try:
        import pygame

        from evosim.render.renderer import SIDEBAR, Viewer
    except Exception as e:  # pygame が無い/初期化できない環境
        return {"available": False, "reason": str(e)[:200]}

    try:
        sim = Simulation(Config(**overrides), seed)
        for _ in range(warmup):
            sim.step()
        pygame.init()
        cfg = sim.cfg
        screen = pygame.display.set_mode(
            (int(cfg.world_width) + SIDEBAR, int(cfg.world_height)))
        font = pygame.font.SysFont("consolas", 15)
        viewer = Viewer(sim)
        viewer._draw(screen, font)  # 初回はキャッシュ生成を含むので除外
        t0 = time.perf_counter()
        for _ in range(frames):
            viewer._draw(screen, font)
        el = time.perf_counter() - t0
        pygame.quit()
        return {
            "available": True,
            "population": len(sim.organisms),
            "frames": frames,
            "ms_per_frame": round(el / frames * 1000.0, 3),
            "max_fps_draw_only": round(frames / el, 1),
        }
    except Exception as e:
        return {"available": False, "reason": str(e)[:200]}


# ---------------------------------------------------------------- 出力

def _fmt(v, unit="", nd=2):
    return "n/a" if v is None else f"{v:,.{nd}f}{unit}"


def print_report(res: dict) -> None:
    e = res["environment"]
    print("=" * 78)
    print("シミュレーション計算性能ベンチマーク")
    print("=" * 78)
    print(f"OS            {e['os']} {e['os_release']} ({e['machine']})")
    print(f"CPU           {e['cpu_model']}")
    print(f"コア          物理 {e['physical_cpus']} / 論理 {e['logical_cpus']} / "
          f"利用可能 {e['usable_cpus']}"
          + (f" / cgroup制限 {e['cgroup_cpu_limit']:.2f}コア"
             if e.get("cgroup_cpu_limit") else ""))
    print(f"メモリ        {_fmt(e['total_ram_gb'], ' GB')}")
    print(f"Python        {e['python_version']} ({e['python_implementation']}) "
          f"/ NumPy {e['numpy_version']}")

    print("\n--- 単一プロセス性能 (描画・記録なし) ---")
    print(f"{'シナリオ':<12} {'個体数':>7} {'ms/step':>9} {'step/s':>9} "
          f"{'CPU使用':>9} {'最大RSS':>10}")
    for r in res["scenarios"]:
        print(f"{r['scenario']:<12} {r['population_start']:>7,} "
              f"{r['ms_per_step_mean']:>9.3f} {r['steps_per_second']:>9.1f} "
              f"{_fmt(r['cpu_utilization_cores'], 'コア'):>9} "
              f"{_fmt(r['peak_rss_mb'], ' MB', 1):>10}")

    if res.get("io_overhead"):
        io = res["io_overhead"]
        base = next((r for r in res["scenarios"] if r["scenario"] == "standard"), None)
        print("\n--- 記録 I/O の影響 ---")
        if base:
            d = (io["ms_per_step_mean"] - base["ms_per_step_mean"])
            print(f"記録なし {base['ms_per_step_mean']:.3f} ms/step → "
                  f"記録あり {io['ms_per_step_mean']:.3f} ms/step "
                  f"({d:+.3f} ms, {d / base['ms_per_step_mean']:+.1%})")

    if res.get("render"):
        r = res["render"]
        print("\n--- 描画コスト (SDLダミードライバ) ---")
        if r.get("available"):
            print(f"個体数 {r['population']:,} で {r['ms_per_frame']:.2f} ms/frame "
                  f"(描画のみなら最大 {r['max_fps_draw_only']:.0f} FPS)")
        else:
            print(f"測定不可: {r.get('reason')}")

    if res.get("phase_profile"):
        p = res["phase_profile"]
        print(f"\n--- 処理フェーズ別の内訳 (個体数 {p['population']:,}) ---")
        print(f"{'フェーズ':<34} {'割合':>7}")
        for k, v in p["phases"].items():
            print(f"{k:<34} {v['share']:>6.1%}")
        print(f"  ({p['note']})")

    if res.get("scaling"):
        print("\n--- プロセス並列スケーリング (run単位の並列) ---")
        print("  計算のみ = プロセス起動時間を除いた純粋な計算性能")
        print("  実測     = Python起動を含む実際のバッチ実行に相当")
        print(f"{'並列数':>6} | {'計算のみ step/s':>16} {'倍率':>7} {'効率':>6}"
              f" | {'実測 step/s':>12} {'倍率':>7} {'効率':>6}")
        for r in res["scaling"]["results"]:
            if "error" in r:
                print(f"{r['workers']:>6} 失敗")
                continue
            print(f"{r['workers']:>6} | {r['aggregate_steps_per_second_simonly']:>16,.0f} "
                  f"{r['speedup_vs_1_simonly']:>6.2f}x {r['efficiency_simonly']:>5.0%}"
                  f" | {r['aggregate_steps_per_second']:>12,.0f} "
                  f"{r['speedup_vs_1']:>6.2f}x {r['efficiency']:>5.0%}")


def compare(paths: list[str]) -> None:
    runs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    print(f"{'環境':<34} {'CPU':>6} " + "".join(f"{s:>12}" for s in SCENARIOS))
    for r, p in zip(runs, paths):
        e = r["environment"]
        label = f"{e['os']}/{e['cpu_model'][:24]}"
        row = {s["scenario"]: s["steps_per_second"] for s in r["scenarios"]}
        print(f"{label:<34} {e['logical_cpus']:>6} "
              + "".join(f"{row.get(s, float('nan')):>12,.1f}" for s in SCENARIOS))
    print("\n(値は step/s。大きいほど速い)")


def main() -> None:
    ap = argparse.ArgumentParser(description="シミュレーション計算性能ベンチマーク")
    ap.add_argument("--quick", action="store_true", help="短縮版")
    ap.add_argument("--full", action="store_true",
                    help="内訳・I/O・描画・並列スケーリングをすべて測る")
    ap.add_argument("--profile", action="store_true", help="処理フェーズ内訳を測る")
    ap.add_argument("--scaling", default=None,
                    help="並列スケーリングを測る。例: 1,2,4,8")
    ap.add_argument("--out", default=None, help="結果JSONの保存先")
    ap.add_argument("--compare", nargs="+", default=None,
                    help="保存済みJSONを比較する")
    ap.add_argument("--label", default=None, help="環境の識別名 (任意)")
    args = ap.parse_args()

    if args.compare:
        compare(args.compare)
        return

    scenarios = QUICK if args.quick else SCENARIOS
    res = {
        "schema": SCHEMA,
        "label": args.label,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "environment": environment_info(),
        "scenarios": [],
    }

    for name, (ov, seed, warm, meas) in scenarios.items():
        print(f"[実行中] {name} ...", file=sys.stderr, flush=True)
        res["scenarios"].append(run_scenario(name, ov, seed, warm, meas))

    if args.full or args.profile:
        print("[実行中] 処理フェーズ内訳 ...", file=sys.stderr, flush=True)
        ov, seed, warm, meas = scenarios.get("dense", scenarios["light"])
        res["phase_profile"] = profile_phases(ov, seed, warm, min(meas, 120))

    if args.full:
        print("[実行中] 記録I/Oの影響 ...", file=sys.stderr, flush=True)
        ov, seed, warm, meas = scenarios.get("standard", scenarios["light"])
        res["io_overhead"] = io_overhead(ov, seed, warm, meas)
        print("[実行中] 描画コスト ...", file=sys.stderr, flush=True)
        res["render"] = render_cost({}, 1, 1000, 60)

    if args.scaling or args.full:
        spec = args.scaling or "1,2,4,8"
        counts = [int(x) for x in spec.split(",") if x.strip()]
        print(f"[実行中] 並列スケーリング {counts} ...", file=sys.stderr, flush=True)
        res["scaling"] = scaling_test(counts, 400 if args.quick else 1200)

    print_report(res)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        print(f"\n結果JSON -> {args.out}")


if __name__ == "__main__":
    main()
