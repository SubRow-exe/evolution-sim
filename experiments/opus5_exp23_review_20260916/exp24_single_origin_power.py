"""Exp24 single-origin invasion assay の検出力計算 (Opus5レビュー用・診断のみ)。

Exp24 計画 (docs/Exp24_実験計画.md §13) の strong-support 基準は

    paired-origin gate を通った seed の 6/8 以上で
    N_photo(+240h, flux=0.5) > N_photo(+240h, flux=0.0)

である。founder は1個体なので、この endpoint は「1個体から始まる系統が
240h 後にどれだけ残っているか」という branching process の実現値である。

本スクリプトは Exp23 の実測値から出生率・死亡率・選択係数を推定し、
線形 birth-death 過程の Monte Carlo で

  * founder lineage の 240h 生存確率 (= establishment probability)
  * P(N_photo(高flux) > N_photo(低flux)) / P(tie) / P(<)
  * 6/8 基準を満たす確率 (= 検出力)
  * 必要な独立 origin 数

を求める。シミュレータは実行しない。
"""
from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------- Exp23 実測
# docs/Exp24_実験計画.md §3: flux=0 の総出生数中央値 ≈ 241 births / 120h run。
TOTAL_BIRTHS_120H = 241.0
N_INIT = 100.0
# Exp23 flux=0 の最終 N (f_photo の最小分母から復元、seed 23008 除く):
#   111, 55, 197, 118, 71, 146, 9(以上)
N_FINAL_FLUX0_MEDIAN = 118.0
DURATION_H = 120.0

# Exp23 の中央値 f_photo から求めた logit slope (= 選択係数 s [1/h])。
#   s(flux) = [logit(median f_photo(flux)) - logit(median f_photo(0.0))] / 120h
MEDIAN_F = {0.0: 0.4965, 0.5: 0.5565, 1.5: 0.6317}
EXP24_WINDOW_H = 240.0


def logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def estimate_rates() -> tuple[float, float]:
    """flux=0 集団の per-capita 出生率 b と死亡率 d [1/h]。

    平均個体数を初期値と最終値の対数平均で近似し、総出生数から b を、
    個体数収支 N_final = N_init + births - deaths から d を求める。
    """
    n0, n1 = N_INIT, N_FINAL_FLUX0_MEDIAN
    n_mean = (n1 - n0) / math.log(n1 / n0) if n1 != n0 else n0
    b = TOTAL_BIRTHS_120H / (n_mean * DURATION_H)
    deaths = N_INIT + TOTAL_BIRTHS_120H - N_FINAL_FLUX0_MEDIAN
    d = deaths / (n_mean * DURATION_H)
    return b, d


def selection_coefficient(flux: float) -> float:
    return (logit(MEDIAN_F[flux]) - logit(MEDIAN_F[0.0])) / DURATION_H


def survival_prob_analytic(b: float, d: float, t: float) -> float:
    """1個体から始まる線形 birth-death 過程が時刻 t で絶滅していない確率。"""
    r = b - d
    if abs(r) < 1e-12:
        return 1.0 / (1.0 + b * t)
    return r / (b - d * math.exp(-r * t))


def simulate_lineage_sizes(b: float, d: float, t: float, n_rep: int,
                           rng: np.random.Generator) -> np.ndarray:
    """線形 birth-death 過程 (1個体スタート) の時刻 t における個体数。

    絶滅確率 p0 と、生存条件つき幾何分布という解析解を使う
    (Kendall 1948)。個体ごとの Gillespie を回すより速く厳密。
    """
    r = b - d
    if abs(r) < 1e-12:
        alpha = beta = b * t / (1.0 + b * t)
    else:
        e = math.exp(-r * t)
        alpha = d * (1.0 - e) / (b - d * e)   # P(extinct at t)
        beta = b * (1.0 - e) / (b - d * e)
    u = rng.random(n_rep)
    out = np.zeros(n_rep, dtype=np.int64)
    alive = u >= alpha
    n_alive = int(alive.sum())
    if n_alive:
        # 生存時のサイズは success prob (1-beta) の幾何分布 (1以上)
        g = rng.geometric(1.0 - beta, size=n_alive)
        out[alive] = g
    return out


def main() -> None:
    rng = np.random.default_rng(20260916)
    b, d = estimate_rates()
    print("=" * 74)
    print("1. Exp23 flux=0 から推定した per-capita rate")
    print("=" * 74)
    print(f"    総出生数 (120h, 中央値)      = {TOTAL_BIRTHS_120H:.0f}")
    print(f"    最終 N (flux=0, 中央値)      = {N_FINAL_FLUX0_MEDIAN:.0f}")
    print(f"    出生率 b = {b:.5f} /individual/h")
    print(f"    死亡率 d = {d:.5f} /individual/h")
    print(f"    正味 r   = {b - d:+.5f} /h  (240h で {math.exp((b-d)*240):.2f} 倍)")

    print()
    print("=" * 74)
    print("2. Exp23 の中央値から求めた選択係数")
    print("=" * 74)
    s = {f: selection_coefficient(f) for f in (0.5, 1.5)}
    for f, sv in s.items():
        print(f"    flux {f}: s = {sv:.5f} /h  (120h で logit +{sv*120:.3f})")

    print()
    print("=" * 74)
    print("3. founder 1個体の 240h establishment probability")
    print("=" * 74)
    print("    (利益が出生側に出る場合と死亡側に出る場合の両方を示す)")
    rates: dict[tuple[float, str], tuple[float, float]] = {(0.0, "-"): (b, d)}
    for f in (0.5, 1.5):
        rates[(f, "birth")] = (b + s[f], d)
        rates[(f, "death")] = (b, max(d - s[f], 1e-9))
    print(f"    {'flux':>5} {'side':>6} {'b':>9} {'d':>9} {'P_est(240h)':>13}")
    p_est: dict[tuple[float, str], float] = {}
    for key, (bb, dd) in rates.items():
        p = survival_prob_analytic(bb, dd, EXP24_WINDOW_H)
        p_est[key] = p
        print(f"    {key[0]:5.1f} {key[1]:>6} {bb:9.5f} {dd:9.5f} {p:13.3f}")

    print()
    print("=" * 74)
    print("4. Exp24 primary endpoint: P(N_photo(高flux) > N_photo(低flux))")
    print("=" * 74)
    n_rep = 400_000
    base = simulate_lineage_sizes(b, d, EXP24_WINDOW_H, n_rep, rng)
    results = {}
    for f in (0.5, 1.5):
        for side in ("birth", "death"):
            bb, dd = rates[(f, side)]
            hi = simulate_lineage_sizes(bb, dd, EXP24_WINDOW_H, n_rep, rng)
            p_gt = float(np.mean(hi > base))
            p_eq = float(np.mean(hi == base))
            p_lt = float(np.mean(hi < base))
            p_both0 = float(np.mean((hi == 0) & (base == 0)))
            results[(f, side)] = p_gt
            print(f"\n    flux {f} ({side}-side advantage) vs flux 0.0:")
            print(f"      P(>)  = {p_gt:.3f}")
            print(f"      P(=)  = {p_eq:.3f}   (うち両方絶滅 = {p_both0:.3f})")
            print(f"      P(<)  = {p_lt:.3f}")

    print()
    print("=" * 74)
    print("5. 事前登録した 6/8 基準の検出力")
    print("=" * 74)
    print("    '6/8 seed 以上で N_photo(0.5) > N_photo(0.0)' を満たす確率。")
    print("    tie (両方絶滅など) は '>' を満たさないので失敗として数える。")
    print()
    print(f"    {'flux':>5} {'side':>6} {'P(>)':>7} {'P(>=6/8)':>10} {'P(>=7/8)':>10}")
    for (f, side), p_gt in results.items():
        pw6 = sum(math.comb(8, k) * p_gt**k * (1 - p_gt)**(8 - k) for k in range(6, 9))
        pw7 = sum(math.comb(8, k) * p_gt**k * (1 - p_gt)**(8 - k) for k in range(7, 9))
        print(f"    {f:5.1f} {side:>6} {p_gt:7.3f} {pw6:10.3f} {pw7:10.3f}")

    print()
    print("=" * 74)
    print("6. 必要な独立 origin 数 (endpoint を establishment probability にした場合)")
    print("=" * 74)
    print("    2群比較 (両側 alpha=0.05, power=0.80) の正規近似。")
    z_a, z_b = 1.959964, 0.841621
    print(f"    {'flux':>5} {'side':>6} {'p0':>7} {'p1':>7} {'n/群':>8}")
    for f in (0.5, 1.5):
        for side in ("birth", "death"):
            p0 = p_est[(0.0, "-")]
            p1 = p_est[(f, side)]
            pbar = 0.5 * (p0 + p1)
            if abs(p1 - p0) < 1e-9:
                n = float("inf")
            else:
                n = ((z_a * math.sqrt(2 * pbar * (1 - pbar))
                      + z_b * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
                     / (p1 - p0) ** 2)
            print(f"    {f:5.1f} {side:>6} {p0:7.3f} {p1:7.3f} {math.ceil(n):8d}")
    print()
    print("    Exp24 の設計では 1 run = 1 origin なので、n/群 = 必要 run 数。")
    print("    8 seeds では 1 群あたり 8 origin しかない。")




def sensitivity() -> None:
    """b, d の推定に対する結論の頑健性。

    Exp23 の最終 N は f_photo の最小分母から復元した下限なので、
    真の N はその整数倍でありうる。最終 N を変えて establishment
    probability と 6/8 検出力がどう動くかを見る。
    """
    rng = np.random.default_rng(20260917)
    print()
    print("=" * 74)
    print("7. 感度解析: flux=0 の最終 N を変えた場合")
    print("=" * 74)
    print(f"    {'N_final':>8} {'b':>9} {'d':>9} {'r':>9} "
          f"{'P_est(0.0)':>11} {'P_est(0.5)':>11} {'P(>=6/8)':>10}")
    for n_final in (55.0, 80.0, 118.0, 200.0, 350.0, 500.0):
        n0 = N_INIT
        n_mean = (n_final - n0) / math.log(n_final / n0)
        b = TOTAL_BIRTHS_120H / (n_mean * DURATION_H)
        d = (n0 + TOTAL_BIRTHS_120H - n_final) / (n_mean * DURATION_H)
        if d < 0:
            d = 0.0
        s05 = selection_coefficient(0.5)
        p0 = survival_prob_analytic(b, d, EXP24_WINDOW_H)
        p1 = survival_prob_analytic(b, max(d - s05, 1e-9), EXP24_WINDOW_H)
        base = simulate_lineage_sizes(b, d, EXP24_WINDOW_H, 200_000, rng)
        hi = simulate_lineage_sizes(b, max(d - s05, 1e-9), EXP24_WINDOW_H,
                                    200_000, rng)
        p_gt = float(np.mean(hi > base))
        pw6 = sum(math.comb(8, k) * p_gt**k * (1 - p_gt)**(8 - k) for k in range(6, 9))
        print(f"    {n_final:8.0f} {b:9.5f} {d:9.5f} {b-d:+9.5f} "
              f"{p0:11.3f} {p1:11.3f} {pw6:10.3f}")
    print()
    print("    N_final >= 350 の行は deaths=0 に張り付く非物理な極限 "
          "(births=241 固定のため)。")
    print("    その極限まで含めても 6/8 基準の検出力は最大 0.12 程度で、"
          "0.8 には遠く届かない。")


def origins_per_run() -> None:
    """recurrent innovation を止めない場合の1 runあたり origin 数。"""
    print()
    print("=" * 74)
    print("8. recurrent innovation を維持した場合の origin 供給")
    print("=" * 74)
    b, d = estimate_rates()
    r = b - d
    for hours in (240.0, 480.0):
        n_end = N_INIT * math.exp(r * hours)
        n_mean = (n_end - N_INIT) / (r * hours) if r else N_INIT
        births = b * n_mean * hours
        for p_inn in (1e-4, 0.01):
            print(f"    {hours:5.0f} h, p_innovation={p_inn:g}: "
                  f"births≈{births:7.0f}, 期待 origin 数≈{births * p_inn:6.2f}")
    print()
    print("    -> p=0.01 を維持すれば 1 run で 10 origin 以上供給できる。")
    print("       single-origin lock はこの供給を 1 に捨てている。")




def window_length_effect() -> None:
    """post-origin window を伸ばすと必要 origin 数がどう変わるか。

    線形 birth-death 過程の生存確率は t -> inf で 1 - d/b に収束する。
    b が d をわずかに上回るだけの本系では P_est(240h)=0.22 だが
    P_est(inf)=0.075 まで下がる。絶対値は下がるが条件間の相対差は
    広がるため、window を伸ばすと必要 origin 数はむしろ減る。
    """
    z_a, z_b = 1.959964, 0.841621
    b, d = estimate_rates()
    print()
    print("=" * 74)
    print("9. post-origin window の長さと必要 origin 数 (death-side advantage)")
    print("=" * 74)
    print(f"    {'window[h]':>10} {'P_est(0.0)':>11} {'P_est(0.5)':>11} "
          f"{'n/群(0.5)':>11} {'P_est(1.5)':>11} {'n/群(1.5)':>11}")
    for t in (240.0, 480.0, 960.0, 1920.0, float("inf")):
        row = [f"{t:10.0f}" if t != float("inf") else f"{'inf':>10}"]
        ns = {}
        ps = {}
        for f in (0.0, 0.5, 1.5):
            dd = d if f == 0.0 else max(d - selection_coefficient(f), 1e-9)
            if t == float("inf"):
                pv = max(0.0, 1.0 - dd / b)
            else:
                pv = survival_prob_analytic(b, dd, t)
            ps[f] = pv
        for f in (0.5, 1.5):
            p0, p1 = ps[0.0], ps[f]
            pbar = 0.5 * (p0 + p1)
            n = ((z_a * math.sqrt(2 * pbar * (1 - pbar))
                  + z_b * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
                 / (p1 - p0) ** 2)
            ns[f] = math.ceil(n)
        print(f"{row[0]} {ps[0.0]:11.3f} {ps[0.5]:11.3f} {ns[0.5]:11d} "
              f"{ps[1.5]:11.3f} {ns[1.5]:11d}")
    print()
    print("    -> window を 240h から伸ばすほど必要 origin 数は減る。")
    print("       240h は『定着したかどうか』を決めるには短すぎる。")


if __name__ == "__main__":
    main()
    sensitivity()
    origins_per_run()
    window_length_effect()
