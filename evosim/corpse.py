"""死骸。仕様書 Ver.1.1 §8。物質循環の要であり分解者戦略の資源。"""
from __future__ import annotations


class Corpse:
    __slots__ = ("x", "y", "matter", "energy")

    def __init__(self, x: float, y: float, matter: float, energy: float):
        self.x = x
        self.y = y
        self.matter = matter
        self.energy = max(0.0, energy)
