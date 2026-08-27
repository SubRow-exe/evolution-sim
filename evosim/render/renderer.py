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
        self.last_key = "-"

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
                    running = self._on_key(ev)
                elif ev.type == pygame.TEXTINPUT:
                    # IME等でKEYDOWNが届かない環境向けのフォールバック
                    running = self._on_char(ev.text)

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

    def _on_key(self, ev) -> bool:
        key = ev.key
        self.last_key = pygame.key.name(key)
        ch = (getattr(ev, "unicode", "") or "").lower()
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_SPACE or ch == " ":
            self._toggle_pause()
        elif key in (pygame.K_1, pygame.K_KP1) or ch == "1":
            self._set_speed(1)
        elif key in (pygame.K_2, pygame.K_KP2) or ch == "2":
            self._set_speed(10)
        elif key in (pygame.K_3, pygame.K_KP3) or ch == "3":
            self._set_speed(100)
        elif key == pygame.K_d or ch == "d":
            self._disaster()
        elif key == pygame.K_g or ch == "g":
            self._graphs()
        elif key == pygame.K_r or ch == "r":
            self._reset()
        return True

    def _on_char(self, text: str) -> bool:
        ch = (text or "").lower()
        self.last_key = f"'{ch}'"
        actions = {" ": self._toggle_pause,
                   "1": lambda: self._set_speed(1),
                   "2": lambda: self._set_speed(10),
                   "3": lambda: self._set_speed(100),
                   "d": self._disaster, "g": self._graphs, "r": self._reset}
        fn = actions.get(ch)
        if fn:
            fn()
        return True

    # --- キー動作 ---

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.message = "PAUSED" if self.paused else "RESUMED"

    def _set_speed(self, n: int) -> None:
        self.speed = n
        self.message = f"speed x{n}"

    def _disaster(self) -> None:
        n = random_disaster(self.sim)
        self.message = f"DISASTER: {n} killed ({int(self.sim.cfg.disaster_kill_frac*100)}%)"

    def _graphs(self) -> None:
        if not self.sim.recorder:
            self.message = "no recorder (--no-record)"
            return
        from .plots import plot_run
        out = plot_run(self.sim.recorder.dir)
        self.message = "plots saved -> opening folder"
        try:
            import os
            os.startfile(str(out))  # エクスプローラーでグラフフォルダを開く
        except OSError:
            self.message = f"plots -> {out}"

    def _reset(self) -> None:
        if self.make_sim is None:
            return
        self.sim.close()
        self.sim = self.make_sim()
        self.message = f"RESET seed={self.sim.seed}"

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
            f"last key  {self.last_key}",
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

        # 画面上部の目立つメッセージバー (直近のキー操作の結果)
        if self.message:
            bar = pygame.Surface((w, 28))
            bar.set_alpha(180)
            bar.fill((0, 0, 0))
            screen.blit(bar, (0, 0))
            screen.blit(font.render(self.message, True, (255, 230, 120)), (10, 6))
