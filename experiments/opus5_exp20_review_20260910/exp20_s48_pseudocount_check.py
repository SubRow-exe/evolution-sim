"""Exp20 primary endpoint (Delta_s48) が pseudocount artifact かを検算する。

Exp20結果考察 §6 は 0% arm の s48=+2.652/day を「phototrophが居ないための
数学的artifact」として解釈対象から外した。本スクリプトは、報告された
s48_A0 / Delta_s48 / P48 から A1 arm の A48 を逆算し、同じ artifact が
1/10/50% の primary arm にも及んでいないかを確認する。

シミュレーション不要。報告値だけで閉じる算術。
考察の正本: docs/Exp20_Opus5レビュー.md
"""
from __future__ import annotations

import math

PSEUDOCOUNT = 0.5

# docs/Exp20_結果考察.md §3 / §5 / §4.2 の報告値
REPORTED = {
    "1%":  dict(P0=1,  A0=99, s48_A0=1.199, delta=0.730, P48_range=(1, 3)),
    "10%": dict(P0=10, A0=90, s48_A0=1.363, delta=1.068, P48_range=(7, 10)),
    "50%": dict(P0=50, A0=50, s48_A0=1.382, delta=0.803, P48_range=(39, 55)),
}


def s48(p0: float, a0: float, p48: float, a48: float) -> float:
    """docs Exp20 §8 の事前登録式。"""
    return (math.log((p48 + PSEUDOCOUNT) / (a48 + PSEUDOCOUNT))
            - math.log((p0 + PSEUDOCOUNT) / (a0 + PSEUDOCOUNT))) / 2.0


def implied_a48(p0: float, a0: float, p48: float, s48_a1: float) -> float:
    log_ratio = 2.0 * s48_a1 + math.log((p0 + PSEUDOCOUNT) / (a0 + PSEUDOCOUNT))
    return (p48 + PSEUDOCOUNT) / math.exp(log_ratio) - PSEUDOCOUNT


def main() -> None:
    print("0. 式の検証 — 結果考察 §6 が報告した 0% arm の artifact を再現する")
    print(f"   s48(P0=0, A0=100, P48=0, A48=0) = {s48(0, 100, 0, 0):+.3f}/day"
          f"   (報告値 +2.652)")

    print()
    print("1. 報告された s48_A1 から A1 arm の A48 を逆算する")
    print(f"   {'freq':>5}{'s48_A0':>9}{'Δs48':>8}{'s48_A1':>9}"
          f"{'P48':>7}{'逆算A48':>10}{'A48=0なら':>11}")
    for name, r in REPORTED.items():
        s_a1 = r["s48_A0"] + r["delta"]
        p48 = sum(r["P48_range"]) / 2.0
        a48 = implied_a48(r["P0"], r["A0"], p48, s_a1)
        s_if_zero = s48(r["P0"], r["A0"], p48, 0.0)
        print(f"   {name:>5}{r['s48_A0']:9.3f}{r['delta']:8.3f}{s_a1:9.3f}"
              f"{p48:7.1f}{a48:10.2f}{s_if_zero:11.3f}")

    print()
    print("2. 判定")
    print("   ancestor-only control は 43-46 h で全滅 (結果考察 §4.1)。")
    print("   評価時点 48 h はその後なので、10% / 50% arm の A48 は実質 0 になる。")
    print("   そこでは Delta_s48 > 0 は pseudocount 0.5 で決まり、")
    print("   phototroph の相対fitnessを測っていない (§6 で 0% arm について")
    print("   指摘されたのと同じ artifact)。")


if __name__ == "__main__":
    main()
