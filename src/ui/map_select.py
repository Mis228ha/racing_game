"""
MapSelect — выбор карты мышкой и клавиатурой.
"""

import math
import pygame
from src.engine.game_state import BaseState
from src.game_objects.track import NUM_MAPS, MAP_DEFS


class MapSelectState(BaseState):
    def __init__(self, screen, event_bus, assets, two_player: bool = False,
                 num_bots: int = 3, network_mode: str = "local", **kwargs):
        super().__init__(screen, event_bus, assets)
        self.two_player   = two_player
        self.num_bots     = num_bots
        self.network_mode = network_mode
        self._sel   = 0
        self._time  = 0.0
        self._previews: dict[int, pygame.Surface | None] = {}
        self._card_rects: list[pygame.Rect] = []

    def _get_preview(self, map_id: int) -> pygame.Surface | None:
        if map_id not in self._previews:
            try:
                from src.game_objects.track import Track
                t = Track(map_id)
                size = 180
                surf = pygame.Surface((size, size))
                surf.fill((15,15,25))
                rect = pygame.Rect(10, 10, size-20, size-20)
                t.draw_minimap(surf, rect)
                pts = t.points
                xs=[p.x for p in pts]; ys=[p.y for p in pts]
                mnx,mxx=min(xs),max(xs); mny,mxy=min(ys),max(ys)
                rx=mxx-mnx+1; ry=mxy-mny+1
                sp = t.start_pos
                sx = int(rect.x+(sp[0]-mnx)/rx*rect.width)
                sy = int(rect.y+(sp[1]-mny)/ry*rect.height)
                pygame.draw.circle(surf,(255,80,80),(sx,sy),5)
                self._previews[map_id] = surf
            except Exception:
                self._previews[map_id] = None
        return self._previews[map_id]

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._sel = (self._sel-1) % NUM_MAPS
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._sel = (self._sel+1) % NUM_MAPS
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._launch()
            elif event.key == pygame.K_ESCAPE:
                self.manager.replace("menu")

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            for i, rect in enumerate(self._card_rects):
                if rect.collidepoint(mx, my):
                    self._sel = i

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for i, rect in enumerate(self._card_rects):
                if rect.collidepoint(mx, my):
                    self._sel = i
                    self._launch()

    def _launch(self):
        if self.network_mode == "host":
            self.manager.replace("network_lobby", map_id=self._sel, role="host")
        elif self.network_mode == "join":
            self.manager.replace("network_lobby", map_id=self._sel, role="join")
        else:
            self.manager.replace("race", map_id=self._sel,
                                 two_player=self.two_player, num_bots=self.num_bots)

    def update(self, dt: float):
        self._time += dt
        for off in [-1, 0, 1]:
            self._get_preview((self._sel+off) % NUM_MAPS)

    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill((8,8,18))
        t = self._time

        for i in range(0, w+60, 60):
            x = i+math.sin(t*0.3+i*0.01)*4
            pygame.draw.line(self.screen,(16,16,28),(int(x),0),(int(x),h))
        for j in range(0, h+60, 60):
            y = j+math.sin(t*0.3+j*0.01)*4
            pygame.draw.line(self.screen,(16,16,28),(0,int(y)),(w,int(y)))

        ft = self.assets.get_font(42, bold=True)
        gv = int(160+70*math.sin(t*2))
        ts = ft.render("ВЫБОР ТРАССЫ", True, (gv,50,50))
        self.screen.blit(ts, (w//2-ts.get_width()//2, 28))

        card_w, card_h = 192, 244
        gap  = 22
        total_w = NUM_MAPS*card_w + (NUM_MAPS-1)*gap
        start_x = w//2 - total_w//2
        cy_card = h//2 - 22

        fn   = self.assets.get_font(14, bold=True)
        fd   = self.assets.get_font(12)
        fnum = self.assets.get_font(11)

        self._card_rects = []
        for i in range(NUM_MAPS):
            cx   = start_x + i*(card_w+gap)
            sel  = (i == self._sel)
            cy   = cy_card - (16 if sel else 0)

            # Фон карточки
            bg = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            if sel:
                bg.fill((32,32,58,230))
                pygame.draw.rect(bg,(255,200,50),bg.get_rect(),2,border_radius=10)
            else:
                bg.fill((18,18,36,200))
                pygame.draw.rect(bg,(50,50,82),bg.get_rect(),1,border_radius=8)
            self.screen.blit(bg, (cx, cy))

            # Миникарта-превью
            prev = self._get_preview(i)
            psize = 172
            if prev:
                scaled = pygame.transform.scale(prev, (psize, psize))
                self.screen.blit(scaled, (cx+(card_w-psize)//2, cy+8))
            else:
                pb = pygame.Surface((psize, psize)); pb.fill((25,25,40))
                self.screen.blit(pb, (cx+(card_w-psize)//2, cy+8))

            d  = MAP_DEFS[i]
            nc = (255,220,50) if sel else (160,160,192)
            ns = fn.render(d["name"], True, nc)
            self.screen.blit(ns, (cx+card_w//2-ns.get_width()//2, cy+card_h-56))

            nums = fnum.render(f"#{i+1}", True, (80,80,112) if not sel else (200,180,80))
            self.screen.blit(nums, (cx+8, cy+10))

            # Rect для мыши (чуть больше карточки)
            self._card_rects.append(pygame.Rect(cx, cy_card-20, card_w, card_h+30))



        # Описание
        d = MAP_DEFS[self._sel]
        ds = fd.render(d["desc"], True, (140,140,172))
        self.screen.blit(ds, (w//2-ds.get_width()//2, cy_card+card_h+18))

        # Подсказки
        fh = self.assets.get_font(14)
        hint = "← → или мышь — выбор     Клик / ENTER — старт     ESC — назад"
        hs = fh.render(hint, True, (50,50,76))
        self.screen.blit(hs, (w//2-hs.get_width()//2, h-36))
