"""
Menu — главное меню с поддержкой мыши и клавиатуры.
"""

import pygame
import math
from src.engine.game_state import BaseState


class MenuState(BaseState):
    def __init__(self, screen, event_bus, assets, **kwargs):
        super().__init__(screen, event_bus, assets)
        self._time = 0.0
        self._sel  = 0
        self._items = [
            ("1 ИГРОК  vs AI",         "1p"),
            ("2 ИГРОКА  локально",      "2p"),
            ("ЛОКАЛЬНАЯ СЕТЬ  HOST",    "host"),
            ("ЛОКАЛЬНАЯ СЕТЬ  JOIN",    "join"),
            ("ВЫХОД",                   "quit"),
        ]
        self._item_rects: list[pygame.Rect] = []

    def _item_y(self, i: int, h: int) -> int:
        return h//2 - 30 + i * 52

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._sel = (self._sel - 1) % len(self._items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._sel = (self._sel + 1) % len(self._items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(self._sel)

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            for i, rect in enumerate(self._item_rects):
                if rect.collidepoint(mx, my):
                    self._sel = i

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for i, rect in enumerate(self._item_rects):
                if rect.collidepoint(mx, my):
                    self._activate(i)

    def _activate(self, idx: int):
        _, mode = self._items[idx]
        if mode == "quit":
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif mode == "1p":
            self.manager.replace("map_select", two_player=False, num_bots=3)
        elif mode == "2p":
            self.manager.replace("map_select", two_player=True, num_bots=2)
        elif mode == "host":
            self.manager.replace("map_select", two_player=False, num_bots=0,
                                 network_mode="host")
        elif mode == "join":
            self.manager.replace("map_select", two_player=False, num_bots=0,
                                 network_mode="join")

    def update(self, dt: float):
        self._time += dt

    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill((10, 10, 18))
        t = self._time

        for i in range(0, w+60, 60):
            x = i + math.sin(t*0.3+i*0.01)*4
            pygame.draw.line(self.screen,(18,18,30),(int(x),0),(int(x),h))
        for j in range(0, h+60, 60):
            y = j + math.sin(t*0.3+j*0.01)*4
            pygame.draw.line(self.screen,(18,18,30),(0,int(y)),(w,int(y)))

        gv   = int(180+70*math.sin(t*2))
        ftit = self.assets.get_font(68, bold=True)
        ts   = ftit.render("DRIFT KINGS", True, (gv, 50, 50))
        self.screen.blit(ts, (w//2-ts.get_width()//2, h//5))

        fsub = self.assets.get_font(16)
        sub  = fsub.render("Python Racing", True, (70,70,95))
        self.screen.blit(sub, (w//2-sub.get_width()//2, h//5+76))

        fmenu = self.assets.get_font(28, bold=True)
        self._item_rects = []
        for i, (label, mode) in enumerate(self._items):
            sel   = (i == self._sel)
            color = (255,220,60) if sel else (130,130,155)
            if not sel and mode in ("host","join"):
                color = (80,130,180)
            prefix = "> " if sel else "  "
            surf   = fmenu.render(prefix + label, True, color)
            iy     = self._item_y(i, h)
            ix     = w//2 - surf.get_width()//2
            self.screen.blit(surf, (ix, iy))
            # Прямоугольник для мыши
            rect = pygame.Rect(ix, iy, surf.get_width(), surf.get_height())
            self._item_rects.append(rect)
            # Подсветка при наведении
            if sel:
                hl = pygame.Surface((surf.get_width()+20, surf.get_height()+6), pygame.SRCALPHA)
                hl.fill((255,220,60,18))
                self.screen.blit(hl, (ix-10, iy-3))

        fhint = self.assets.get_font(13)
        hints = [
            "1P: W/A/S/D — езда   LSHIFT — нитро   SPACE — тормоз",
            "2P: P2 стрелки + RSHIFT    ESC — меню    R — рестарт",
        ]
        for i, hint in enumerate(hints):
            hs = fhint.render(hint, True, (55,55,78))
            self.screen.blit(hs, (w//2-hs.get_width()//2, h-60+i*22))
