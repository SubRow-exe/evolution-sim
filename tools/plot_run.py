"""事後グラフ生成: uv run python tools/plot_run.py runs/<run_id>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim.render.plots import plot_run

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python tools/plot_run.py <run_dir>")
        sys.exit(1)
    out = plot_run(sys.argv[1])
    print(f"plots -> {out}")
