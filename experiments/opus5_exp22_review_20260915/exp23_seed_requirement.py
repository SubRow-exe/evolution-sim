"""Exp22 の効果量と Exp21 の雑音床から、Exp23 に必要な seed 数を逆算する。

Issue #75 の M-3 で「working flux recommendation へ Exp23 の必要 seed 数
見積もりを含めること」を提案したが、`docs/Exp22_結果考察.md` §7 D2 の
とおり未実装のまま。本スクリプトはその計算を行う。

入力はすべて公開済みの報告値なので simulation は不要。

考察の正本: docs/Exp22_Opus5レビュー.md

    uv run python .../exp23_seed_requirement.py
"""
from __future__ import annotations

import math

# docs/Exp21_結果考察.md §3 — A2_DYNAMIC_VENT, 8 seed, 120 h
EXP21 = dict(median_pct=56.3, min_pct=45.6, max_pct=63.3, n=8, hours=120.0)

# docs/Exp22_結果考察.md §2 / §3 — A2, 72 h, median Δ total living matter
EXP22_FLUX_EFFECT = {
    0.15: dict(raw_pct=2.22, baseline_corrected_pct=2.22 + 4.56),
    0.5: dict(raw_pct=12.40, baseline_corrected_pct=18.3),   # §3 の実測値
    1.5: dict(raw_pct=55.35, baseline_corrected_pct=55.35 + 4.56),
}
EXP22_HOURS = 72.0
EXP23_HOURS = 120.0

# n=8 の正規標本で期待される range/SD
RANGE_OVER_SD_N8 = 2.85


def main() -> None:
    spread = EXP21["max_pct"] - EXP21["min_pct"]
    sd = spread / RANGE_OVER_SD_N8
    observed_shift = EXP21["median_pct"] - 50.0
    se = sd / math.sqrt(EXP21["n"])

    print("=" * 72)
    print("1. Exp21 が与える競争アッセイの雑音床")
    print("=" * 72)
    print(f"  median {EXP21['median_pct']}% / min {EXP21['min_pct']}% / "
          f"max {EXP21['max_pct']}% / n={EXP21['n']}")
    print(f"  range = {spread:.1f} pt,  range/SD(n=8) ≈ {RANGE_OVER_SD_N8}")
    print(f"  -> SD ≈ {sd:.2f} pt,  SE(n=8) ≈ {se:.2f} pt")
    print(f"  観測シフト {observed_shift:.1f} pt  ->  t ≈ {observed_shift / se:.2f}  (7/8 と整合)")

    print()
    print("=" * 72)
    print("2. Exp22 の効果量を Exp23 の頻度シフトへ換算")
    print("=" * 72)
    print("  monoculture の total living matter 比 (1+r) を per-capita 成長差とみなし、")
    print(f"  s = ln(1+r)/{EXP22_HOURS:.0f}h を {EXP23_HOURS:.0f}h へ外挿して 50:50 からの頻度シフトを出す。")
    print()
    print(f"  {'flux':>6}{'Δmatter(72h)':>15}{'s [/h]':>12}"
          f"{'頻度(120h)':>12}{'シフト':>9}{'必要seed(2σ)':>14}")
    for flux, eff in sorted(EXP22_FLUX_EFFECT.items()):
        for label, key in (("raw", "raw_pct"), ("補正", "baseline_corrected_pct")):
            r = eff[key] / 100.0
            if r <= -1.0:
                continue
            s = math.log1p(r) / EXP22_HOURS
            ratio = math.exp(s * EXP23_HOURS)
            freq = 100.0 * ratio / (1.0 + ratio)
            shift = freq - 50.0
            need = (2.0 * sd / shift) ** 2 if shift > 0 else float("inf")
            tag = f"{flux} ({label})"
            print(f"  {tag:>6}{eff[key]:>14.2f}%{s:>12.5f}{freq:>11.1f}%"
                  f"{shift:>8.1f}p{need:>13.1f}")

    print()
    print("=" * 72)
    print("3. 判定")
    print("=" * 72)
    print("  flux=0.5 の期待シフトは概ね 5-7 pt で、Exp21 が 8 seed で検出した")
    print("  6.3 pt と同オーダー。したがって Exp23 は 8 seed で足りる見込み。")
    print()
    print("  ただし Exp22 の flux=0.5 は 3 seed 中 1 seed がほぼ中立だったため、")
    print("  実際のシフトが 4 pt を下回ると 8 seed では不足する (n≈10-16 が必要)。")
    print()
    print("  推奨: flux=0.5 を primary、flux=1.5 を positive control として")
    print("        同じ seed 数で併走させる。0.5 が null でも 1.5 が明確に正なら")
    print("        「アッセイの失敗」ではなく「0.5 では効果量が小さい」と読める。")
    print("        結果を見てから seed を追加するのは optional stopping になるので、")
    print("        seed 数は事前登録で固定する。")


if __name__ == "__main__":
    main()
