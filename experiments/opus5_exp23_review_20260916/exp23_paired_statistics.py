"""Exp23 結果の対応ありseed解析 (Opus5レビュー用・診断のみ)。

Exp23 は同一 seed の flux 0.0 / 0.5 / 1.5 で initial population・lineage
割当・pre-light dynamics が完全に共通なので、seed を対応ありブロックとして
扱える。公開された `docs/Exp23_結果考察.md` は flux ごとの中央値と
「> 50% の seed 数」だけを報告しており、この対応構造を使っていない。

本スクリプトは Actions run 34951226448 の各 run job ログに出力された
final_f_photo (24 run 全部) をそのまま入力とし、

  1. 公開された中央値・範囲・カウントの再現
  2. seed 内 paired 差の符号検定
  3. seed ごとの flux 単調性
  4. final population N の復元 (f_photo の有理数表現から)

を計算する。シミュレーションは実行しない。
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import comb

# Actions run 34951226448 の run job ログ (exp23_runs (2300X)) に
# 出力された summary JSON の final_f_photo。24/24 run。
F_PHOTO = {
    23001: {0.0: 0.5225225225225225, 0.5: 0.5414847161572053, 1.5: 0.570281124497992},
    23002: {0.0: 0.4909090909090909, 0.5: 0.6171875,          1.5: 0.6651162790697674},
    23003: {0.0: 0.5025380710659898, 0.5: 0.5714285714285714, 1.5: 0.5983263598326359},
    23004: {0.0: 0.4830508474576271, 0.5: 0.5838926174496645, 1.5: 0.7714285714285715},
    23005: {0.0: 0.49295774647887325, 0.5: 0.518348623853211, 1.5: 0.5498938428874734},
    23006: {0.0: 0.5136986301369864, 0.5: 0.5300546448087432, 1.5: 0.6954887218045113},
    23007: {0.0: 0.4444444444444444, 0.5: 0.6739130434782609, 1.5: 0.7267441860465116},
    23008: {0.0: 0.5,                0.5: 0.5,                1.5: 0.5},
}
FLUXES = (0.0, 0.5, 1.5)
SEEDS = tuple(sorted(F_PHOTO))


def median(xs: list[float]) -> float:
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2] if n % 2 else 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def smallest_denominator(x: float, max_den: int = 4000) -> Fraction:
    """f_photo = N_ON / N_total の最小分母表現。N_total の最小候補を与える。"""
    return Fraction(x).limit_denominator(max_den)


def sign_test_one_sided(n_pos: int, n_neg: int) -> float:
    """帰無仮説 p=1/2 の片側符号検定 (tie は除外)。"""
    n = n_pos + n_neg
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(n_pos, n + 1)) / 2 ** n


def main() -> None:
    print("=" * 72)
    print("1. 公開値の再現 (docs/Exp23_結果考察.md §2)")
    print("=" * 72)
    print(f"{'flux':>5} {'median':>9} {'mean':>9} {'min':>9} {'max':>9} {'>50%':>6}")
    for f in FLUXES:
        vals = [F_PHOTO[s][f] for s in SEEDS]
        n_gt = sum(1 for v in vals if v > 0.5)
        print(f"{f:5.1f} {median(vals):9.4f} {sum(vals)/len(vals):9.4f} "
              f"{min(vals):9.4f} {max(vals):9.4f} {n_gt:5d}/8")

    print()
    print("=" * 72)
    print("2. final population N の復元 (f_photo の最小分母)")
    print("=" * 72)
    print("   f_photo は N_ON/N_total の有理数なので、最小分母は N_total の")
    print("   下限にしかならない (真の N はその整数倍)。")
    print("   実測: seed 23007 / flux 0.0 をローカル再現すると N=99 (=9x11)、")
    print("   f_photo=0.4444444444444444 が CI と完全一致した。")
    print("   したがって下表の分母は『N の下限』であり、N そのものではない。")
    print(f"{'seed':>6} " + " ".join(f"{'flux'+str(f):>14}" for f in FLUXES))
    for s in SEEDS:
        cells = []
        for f in FLUXES:
            fr = smallest_denominator(F_PHOTO[s][f])
            cells.append(f"{fr.numerator}/{fr.denominator}".rjust(14))
        print(f"{s:6d} " + " ".join(cells))

    print()
    print("=" * 72)
    print("3. seed 内 paired 差 (同一 seed の flux 間比較)")
    print("=" * 72)
    for lo, hi in combinations(FLUXES, 2):
        diffs = {s: F_PHOTO[s][hi] - F_PHOTO[s][lo] for s in SEEDS}
        pos = sum(1 for d in diffs.values() if d > 0)
        neg = sum(1 for d in diffs.values() if d < 0)
        tie = sum(1 for d in diffs.values() if d == 0)
        p = sign_test_one_sided(pos, neg)
        print(f"\n  Δf_photo({hi} − {lo}):")
        for s in SEEDS:
            mark = "tie" if diffs[s] == 0 else ("+" if diffs[s] > 0 else "-")
            print(f"    seed {s}: {diffs[s]:+8.4f}  {mark}")
        print(f"    positive={pos}  negative={neg}  tie={tie}")
        print(f"    median Δ = {median(list(diffs.values())):+.4f}")
        print(f"    符号検定 (tie除外) 片側 p = {p:.5f}")

    print()
    print("=" * 72)
    print("4. seed ごとの flux 単調性 f(0.0) < f(0.5) < f(1.5)")
    print("=" * 72)
    mono = 0
    informative = 0
    for s in SEEDS:
        v = [F_PHOTO[s][f] for f in FLUXES]
        if v[0] == v[1] == v[2]:
            print(f"    seed {s}: すべて同値 ({v[0]:.4f}) — 情報なし (degenerate)")
            continue
        informative += 1
        ok = v[0] < v[1] < v[2]
        mono += ok
        print(f"    seed {s}: {v[0]:.4f} < {v[1]:.4f} < {v[2]:.4f} ? {'YES' if ok else 'NO'}")
    print(f"\n    厳密単調: {mono}/{informative} (情報のある seed のうち)")
    print(f"    3値の順序がランダムなら1 seedあたり 1/6。")
    print(f"    {mono}/{informative} 全部が同じ順序になる確率 = (1/6)^{informative}"
          f" = {(1/6) ** informative:.3e}")

    print()
    print("=" * 72)
    print("5. 事前登録 gate (docs/Exp23_実験計画.md §14) との照合")
    print("=" * 72)
    f05 = [F_PHOTO[s][0.5] for s in SEEDS]
    n_gt = sum(1 for v in f05 if v > 0.5)
    med = median(f05)
    print(f"    F05: seed数 f_photo > 0.5 = {n_gt}/8  (>= 7 が strong support) "
          f"-> {'PASS' if n_gt >= 7 else 'FAIL'}")
    print(f"    F05: median f_photo = {med:.4f}  (>= 0.53) "
          f"-> {'PASS' if med >= 0.53 else 'FAIL'}")
    print(f"    注: seed 23008 は f_photo = 0.5 ちょうどで、'> 0.5' にも")
    print(f"        '< 0.5' にも入らない tie である。")


if __name__ == "__main__":
    main()
