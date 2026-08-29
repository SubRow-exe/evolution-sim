"""実験群の健全性チェック (Exp04_実行手順.md §4)。

本番実行の直後に、結果を解釈する前の前提が成立しているかを確認する。

    uv run python tools/health_check.py runs/exp04_* --ticks 40000 --expect-runs 20

**前提が崩れている場合は非ゼロ終了する。** 解釈できないデータのまま
解析へ進ませないため、CI/Actions をここで止める。

停止する (exit 1):
- run数不足 (--expect-runs 指定時、条件ごとに照合)
- meta.json の欠損 (再現条件を特定できない)
- 固定対象遺伝子の分散が0でない (遺伝子固定が効いていない)
- 数値実行環境が2種類以上 (条件間比較の前提が崩れる)
- git SHA が不統一 (異なるコードのrunが混在している)

停止しない (警告のみ):
- 早期終了run (extinction / max_population_halt 等)
  → **除外せず「早期終了という結果」として一覧に出す**。実験の観測結果であり
    異常ではないため、ここでは止めない
- git SHA の dirty (未コミット変更のまま実行された)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def check(conds: list[Path], want_ticks: int, expect_runs: int | None) -> int:
    early: list[tuple] = []
    missing: list[str] = []
    unfixed: list[tuple] = []
    short: list[tuple] = []
    envs: dict[str, list[str]] = defaultdict(list)
    shas: dict[str, list[str]] = defaultdict(list)
    fatal: list[str] = []
    warn: list[str] = []

    print(f"期待tick数: {want_ticks:,}"
          + (f" / 期待run数: {expect_runs} (条件ごと)" if expect_runs else "")
          + "\n")
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
                shas[m.get("git_sha") or "(git不明)"].append(f"{c.name}/{d.name}")

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
        if expect_runs is not None and len(runs) < expect_runs:
            short.append((c.name, len(runs)))
        print(f"{c.name:<34} {len(runs):>6} {max_var:>12.3g}")

    print()
    if short:
        fatal.append("run数不足")
        print(f"★ run数が不足している条件: {len(short)} 件 (期待 {expect_runs})")
        for cond, n in short:
            print(f"  {cond}: {n} run (不足 {expect_runs - n})")

    if early:
        warn.append("早期終了run")
        print(f"早期終了run: {len(early)} 件 "
              "(実行手順書§3により除外せず、早期終了という結果として記録する)")
        for cond, run, t, pop in early:
            print(f"  {cond}/{run}: tick {t:,} で終了 (個体数 {pop:,})")
    else:
        print("早期終了run: なし")

    if unfixed:
        fatal.append("遺伝子固定が効いていない")
        print(f"\n★ 固定が効いていないrun: {len(unfixed)} 件")
        for cond, run, g, v in unfixed[:10]:
            print(f"  {cond}/{run}: {g} の分散最大 {v:.3g}")
    else:
        print("固定遺伝子: 全期間で分散0 (正しく固定されている)")

    if missing:
        fatal.append("meta.json欠損")
        print(f"\n★ meta.json 欠損: {len(missing)} 件 -> {missing[:5]}")

    print(f"\n数値実行環境: {len(envs)} 種類")
    for k, v in sorted(envs.items()):
        print(f"  [{len(v):>3} run] {k}")
    if len(envs) > 1:
        fatal.append("数値実行環境の混在")
        print("  ★ 環境が混在している。条件間比較の前提が崩れている")

    print(f"\nコード (git SHA): {len(shas)} 種類")
    for k, v in sorted(shas.items()):
        print(f"  [{len(v):>3} run] {k[:20]}")
    if len(shas) > 1:
        fatal.append("git SHA不統一")
        print("  ★ 異なるコードのrunが混在している。同一実験として比較できない")
    if any(k.endswith("-dirty") for k in shas):
        warn.append("git SHAがdirty")
        print("  未コミット変更のまま実行されたrunがある (コードを特定できない)")

    print()
    if warn:
        print(f"警告 (停止しない): {', '.join(warn)}")
    if fatal:
        print(f"★ 停止条件に該当: {', '.join(fatal)}")
        print("  この結果を解釈してはいけない。原因を解消して再実行すること。")
        return 1
    print("問題なし。前提は成立している。")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="実験群の健全性チェック (異常時は非ゼロ終了)")
    ap.add_argument("dirs", nargs="+", help="条件ディレクトリ (runs/exp04_*)")
    ap.add_argument("--ticks", type=int, required=True, help="期待するtick数")
    ap.add_argument("--expect-runs", type=int, default=None,
                    help="条件ごとに期待するrun数。下回れば異常として停止する")
    args = ap.parse_args()
    conds = [Path(d) for d in args.dirs if Path(d).is_dir()]
    if not conds:
        raise SystemExit("対象ディレクトリがありません")
    sys.exit(check(conds, args.ticks, args.expect_runs))


if __name__ == "__main__":
    main()
