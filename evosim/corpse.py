"""死骸。仕様書 Ver.1.1 §8。物質循環の要であり分解者戦略の資源。"""
from __future__ import annotations


class Corpse:
    __slots__ = ("x", "y", "matter", "energy", "photo_structural_n_mol")

    def __init__(self, x: float, y: float, matter: float, energy: float,
                 photo_structural_n_mol: float = 0.0):
        self.x = x
        self.y = y
        self.matter = matter
        self.energy = max(0.0, energy)
        # V1.11: 死亡個体が持っていたphototrophy apparatus構造Nは、silent
        # lossにせずcorpse decayを通じてfixed-N fieldへ戻す
        # (docs/V1.11_原始Phototrophy_実装仕様_rev2.md §7.3)。
        self.photo_structural_n_mol = max(0.0, photo_structural_n_mol)
