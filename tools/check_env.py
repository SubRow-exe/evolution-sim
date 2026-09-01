"""実験群が同一の数値実行環境で実行されたかを確認する (Issue #20)。

結果は数値実行環境に依存するため、異なる環境で得たrunを同一seedだからという
理由で比較してはいけない。比較前に本ツールで揃っているか確認する。

    uv run python tools/check_env.py runs/exp03_20seeds_40k
    uv run python tools/check_env.py runs/a runs/b     # 複数群の照合
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def collect(root: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    metas = sorted(root.rglob("meta.json"))
    for m in metas:
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        env = d.get("numeric_environment")
        key = env["env_key"] if env else "(環境情報なし: Issue #20以前のrun)"
        sha = d.get("git_sha") or "(git不明)"
        groups[f"{key} | git {sha[:12] if sha else '-'}"].append(m.parent.name)
    return groups


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--strict"]
    strict = "--strict" in sys.argv[1:]
    if not args:
        raise SystemExit(
            "usage: python tools/check_env.py [--strict] <run_dir> [<run_dir> ...]")

    all_groups: dict[str, list[str]] = defaultdict(list)
    for arg in args:
        for k, v in collect(Path(arg)).items():
            all_groups[k].extend(v)

    if not all_groups:
        raise SystemExit("meta.json が見つかりません")

    for key, runs in sorted(all_groups.items()):
        print(f"[{len(runs):>3} run] {key}")
        if len(runs) <= 6:
            print(f"          {', '.join(sorted(runs))}")

    if len(all_groups) == 1:
        print("\n同一環境。比較可能。")
        return 0
    print(f"\n⚠ {len(all_groups)} 種類の数値実行環境が混在しています。")
    print("  異なる数値実行環境のrunを、同一seedだからという理由で直接比較しないこと。")
    print("  (コード変更を跨ぐ場合は git SHA の差も比較を無効にし得る)")
    # --strict では環境不一致を整合性違反として非ゼロ終了する
    # (Issue #41 再トライアル方針 §6: 環境不一致は workflow failure)。
    return 2 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
