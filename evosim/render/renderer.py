"""pygame-ce リアルタイムビューア (仕様書 Ver.1.1 §14)。

SPACE=Pause  1/2/3=x1/x10/x100  G=グラフ  D=災害  R=リセット  ESC=終了
個体の色: R=捕食能力 G=光利用能力 B=死骸分解能力 → 役割分化が色で見える。
"""
from __future__ import annotations

import time

import numpy as np
import pygame

from ..config import Config
from ..disasters import random_disaster
from ..genome import CORPSE_DIG, LIGHT_ABS, PREDATION
from ..simulation import Simulation

SIDEBAR = 230
FPS = 30
FRAME_BUDGET_SEC = 0.1  # 1フレームでシミュレーションに使う時間の上限


class Viewer:
    def __init__(self, sim: Simulation, make_sim=None):
        """make_sim: 新しいseedで Simulation を作るファクトリ (Rキー用)。"""
        self.sim = sim
        self.make_sim = make_sim
        self.paused = False
        self.speed = 1
        self.message = ""

    def run(self) -> None:
        pygame.init()
        # 日本語IMEがキー入力を横取りしてKEYDOWNが届かなくなるのを防ぐ
        pygame.key.stop_text_input()
        cfg = self.sim.cfg
        w = int(cfg.world_width)
        h = int(cfg.world_height)
        screen = pygame.display.set_mode((w + SIDEBAR, h))
        pygame.display.set_caption("Evolution Sim")
        font = pygame.font.SysFont("consolas", 15)
        clock = pygame.time.Clock()

        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    running = self._on_key(ev.key)

            if not self.paused:
                # 高速時も1フレームの実行時間に上限を設け、キー入力の応答性を保つ
                budget_end = time.perf_counter() + FRAME_BUDGET_SEC
                for _ in range(self.speed):
                    self.sim.step()
                    if not self.sim.organisms:
                        self.paused = True
                        self.message = "EXTINCT"
                        break
                    if time.perf_counter() > budget_end:
                        break

            self._draw(screen, font)
            pygame.display.flip()
            clock.tick(FPS)

        self.sim.close()
        pygame.quit()

    # ------------------------------------------------------------------

    def _on_key(self, key: int) -> bool:
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key in (pygame.K_1, pygame.K_KP1):
            self.speed = 1
        elif key in (pygame.K_2, pygame.K_KP2):
            self.speed = 10
        elif key in (pygame.K_3, pygame.K_KP3):
            self.speed = 100
        elif key == pygame.K_d:
            n = random_disaster(self.sim)
            self.message = f"DISASTER: {n} killed"
        elif key == pygame.K_g:
            if self.sim.recorder:
                from .plots import plot_run
                out = plot_run(self.sim.recorder.dir)
                self.message = f"plots -> {out}"
            else:
                self.message = "no recorder"
        elif key == pygame.K_r and self.make_sim is not None:
            self.sim.close()
            self.sim = self.make_sim()
            self.message = f"RESET seed={self.sim.seed}"
        return True

    # ------------------------------------------------------------------

    def _draw(self, screen, font) -> None:
        sim = self.sim
        cfg = sim.cfg
        w = int(cfg.world_width)
        h = int(cfg.world_height)

        # 背景: 光(明度) + 栄養(緑) + 化学(紫)
        light = sim.world.light / max(cfg.light_max, 1e-9)
        nut = np.clip(sim.world.nutrients / (cfg.nutrient_initial * 2.0), 0, 1)
        chem = np.clip(sim.world.chemical / max(cfg.chem_capacity, 1e-9), 0, 1)
        rgb = np.zeros((cfg.grid_w, cfg.grid_h, 3), dtype=np.uint8)
        base = 30 + 60 * light
        rgb[..., 0] = np.clip(base + 90 * chem, 0, 255)
        rgb[..., 1] = np.clip(base + 90 * nut, 0, 255)
        rgb[..., 2] = np.clip(base + 90 * chem, 0, 255)
        surf = pygame.surfarray.make_surface(rgb)
        screen.blit(pygame.transform.scale(surf, (w, h)), (0, 0))

        # 死骸
        for c in sim.corpses:
            r = max(2, int(cfg.radius_coef * np.sqrt(max(c.matter, 1e-9))))
            pygame.draw.circle(screen, (110, 100, 90), (int(c.x), int(c.y)), r, 1)

        # 個体 (色 = 栄養戦略)
        for o in sim.organisms:
            g = o.genome
            col = (
                min(255, int(60 + 195 * min(g[PREDATION] / 1.5, 1.0))),
                min(255, int(60 + 195 * min(g[LIGHT_ABS] / 1.5, 1.0))),
                min(255, int(60 + 195 * min(g[CORPSE_DIG] / 1.5, 1.0))),
            )
            r = max(2, int(o.radius(cfg.radius_coef)))
            pygame.draw.circle(screen, col, (int(o.x), int(o.y)), r)

        # サイドバー
        pygame.draw.rect(screen, (18, 18, 24), (w, 0, SIDEBAR, h))
        lines = [
            f"tick      {sim.tick}",
            f"pop       {len(sim.organisms)}",
            f"births    {sim.births_cum}",
            f"deaths    {sim.deaths_cum}",
            f"  starve  {sim.deaths_by_cause['starvation']}",
            f"  damage  {sim.deaths_by_cause['damage']}",
            f"  preda.  {sim.deaths_by_cause['predation']}",
            f"  disas.  {sim.deaths_by_cause['disaster']}",
            f"corpses   {len(sim.corpses)}",
            f"lineages  {len({o.lineage_id for o in sim.organisms})}",
            f"max gen   {max((o.generation for o in sim.organisms), default=0)}",
            f"seed      {sim.seed}",
            "",
            f"speed x{self.speed}" + ("  [PAUSED]" if self.paused else ""),
            "",
            "SPACE pause  1/2/3 speed",
            "G graphs  D disaster",
            "R reset   ESC quit",
            "",
            "color: R=pred G=light",
            "       B=scavenge",
        ]
        if self.message:
            lines += ["", self.message[:28]]
        y = 10
        for ln in lines:
            screen.blit(font.render(ln, True, (220, 220, 220)), (w + 10, y))
            y += 19
