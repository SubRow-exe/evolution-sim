"""実験群の健全性チェック (Exp04_実行手順.md §4)。

本番実行の直後に、結果を解釈する前の前提が成立しているかを確認する。

    uv run python tools/health_check.py runs/exp04_* --ticks 40000

確認する項目:
- 条件ごとのrun数
- 早期終了run (extinction / max_population_halt 等)
  → **除外せず「早期終了という結果」として一覧に出す**
- 固定対象遺伝子が全期間固定されているか (分散が全区間で0か)
- meta.json の欠損
- 数値実行環境の混在 (ランナーイメージ版まで含めて照合)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def check(conds: list[Path], want_ticks: int) -> int:
    early: list[tuple] = []
    missing: list[str] = []
    unfixed: list[tuple] = []
    envs: dict[str, list[str]] = defaultdict(list)
    problems = 0

    print(f"期待tick数: {want_ticks:,}\n")
    print(f"{'条件':<34} {'run数':>6} {'固定分散max':>12}")
    for c in sorted(conds):
        runs = sorted(d for d in c.iterdir() if d.is_dir() and (d / "stats.csv").exists())
        max_var = 0.0
        for d in runs:
            meta = d / "meta.json"
            if not meta.exists():
                missing.append(f"{c.name}/{d.name}")
            else:
                m = json.loads(meta.read_text(encoding="utf-8"))
                env = m.get("numeric_environment") or {}
                key = env.get("env_key", "(不明)")
                img = env.get("ci_image_version")
                envs[f"{key} | image={img or '-'}"].append(d.name)

            with open(d / "stats.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                early.append((c.name, d.name, 0, 0))
                continue
            last = rows[-1]
            t = int(float(last["tick"]))
            if t < want_ticks:
                early.append((c.name, d.name, t, int(float(last["population"]))))

            cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
            for g in cfg.get("fixed_genes") or []:
                col = f"var_{g}"
                if col not in rows[0]:
                    continue
                v = max(abs(float(r[col])) for r in rows)
                max_var = max(max_var, v)
                if v > 0.0:
                    unfixed.append((c.name, d.name, g, v))
        print(f"{c.name:<34} {len(runs):>6} {max_var:>12.3g}")

    print()
    if early:
        problems += 1
        print(f"早期終了run: {len(early)} 件 "
              "(実行手順書§3により除外せず、早期終了という結果として記録する)")
        for cond, run, t, pop in early:
            print(f"  {cond}/{run}: tick {t:,} で終了 (個体数 {pop:,})")
    else:
        print("早期終了run: なし")

    if unfixed:
        problems += 1
        print(f"\n★ 固定が効いていないrun: {len(unfixed)} 件")
        for cond, run, g, v in unfixed[:10]:
            print(f"  {cond}/{run}: {g} の分散最大 {v:.3g}")
    else:
        print("固定遺伝子: 全期間で分散0 (正しく固定されている)")

    if missing:
        problems += 1
        print(f"\n★ meta.json 欠損: {len(missing)} 件 -> {missing[:5]}")

    print(f"\n数値実行環境: {len(envs)} 種類")
    for k, v in sorted(envs.items()):
        print(f"  [{len(v):>3} run] {k}")
    if len(envs) > 1:
        problems += 1
        print("  ★ 環境が混在している。条件間比較の前提が崩れている可能性がある")

    print()
    print("問題なし" if problems == 0 else f"要確認の項目: {problems} 種類")
    return 0  # 判断材料の提示が目的。早期終了自体は失敗ではない


def main() -> None:
    ap = argparse.ArgumentParser(description="実験群の健全性チェック")
    ap.add_argument("dirs", nargs="+", help="条件ディレクトリ (runs/exp04_*)")
    ap.add_argument("--ticks", type=int, required=True, help="期待するtick数")
    args = ap.parse_args()
    conds = [Path(d) for d in args.dirs if Path(d).is_dir()]
    if not conds:
        raise SystemExit("対象ディレクトリがありません")
    sys.exit(check(conds, args.ticks))


if __name__ == "__main__":
    main()
