"""
Track — 5 карт.
• Ровная дорога (RESOLUTION=10, сглаживание Лапласа)
• Ровные бордюры (полигоны, а не точки)
• Реалистичная трава
"""

import math
import random
import pygame
from dataclasses import dataclass
from typing import List, Tuple

WORLD_W = 2400
WORLD_H = 1800


@dataclass
class TrackPoint:
    x: float
    y: float
    surface: str = "asphalt"
    width: float = 72.0


@dataclass
class Checkpoint:
    x: float
    y: float
    angle: float
    index: int


MAP_DEFS = [
    {"name": "GRAND OVAL",     "desc": "Высокоскоростной овал",               "grass": (34, 85, 28), "dirt_frac": 0.0,  "track_w": 82, "ctrl": "oval"},
    {"name": "CITY CIRCUIT",   "desc": "Технически сложная городская трасса",  "grass": (28, 72, 22), "dirt_frac": 0.0,  "track_w": 68, "ctrl": "city"},
    {"name": "MOUNTAIN PASS",  "desc": "Горные серпантины, грязевые участки",  "grass": (30, 62, 18), "dirt_frac": 0.18, "track_w": 72, "ctrl": "mountain"},
    {"name": "HARBOR CIRCUIT", "desc": "Широкий портовый круг",                "grass": (20, 68, 55), "dirt_frac": 0.0,  "track_w": 78, "ctrl": "harbor"},
    {"name": "STREET CIRCUIT", "desc": "Монако-стайл: тесные повороты",        "grass": (26, 70, 22), "dirt_frac": 0.0,  "track_w": 60, "ctrl": "street"},
]
NUM_MAPS = len(MAP_DEFS)


def _oval():
    cx, cy, rx, ry = 1200, 900, 820, 360
    return [(cx + math.cos((i/16)*math.pi*2 - math.pi/2)*rx,
             cy + math.sin((i/16)*math.pi*2 - math.pi/2)*ry) for i in range(16)]

def _city():
    return [(700,340),(1100,300),(1650,320),(1820,420),(1870,680),(1780,760),
            (1560,740),(1440,860),(1460,1120),(1600,1210),(1700,1360),(1540,1460),
            (820,1460),(620,1380),(520,1160),(540,900),(680,780),(640,600),(540,480)]

def _mountain():
    return [(380,620),(560,380),(840,320),(1060,420),(1180,300),(1420,360),
            (1620,280),(1860,440),(2020,360),(2140,560),(2060,780),(1900,880),
            (1740,1020),(1860,1200),(1800,1380),(1580,1460),(1260,1380),
            (980,1420),(740,1460),(520,1340),(340,1100),(280,840)]

def _harbor():
    return [(480,380),(1000,300),(1600,300),(1940,420),(2080,620),(2100,960),
            (2020,1260),(1880,1440),(1540,1520),(900,1520),(540,1440),
            (380,1260),(300,900),(320,580)]

def _street():
    return [(780,280),(1200,260),(1640,280),(1820,380),(1900,560),(1920,820),
            (1780,960),(1800,1160),(1840,1380),(1700,1500),(1100,1520),
            (680,1500),(500,1400),(440,1200),(560,1060),(540,840),(460,680),(500,460)]

CTRL_FNS = {"oval": _oval, "city": _city, "mountain": _mountain,
            "harbor": _harbor, "street": _street}


class Track:
    RESOLUTION = 10   # точек на сегмент — больше = ровнее

    def __init__(self, map_id: int = 0):
        self.map_id      = map_id % NUM_MAPS
        self._def        = MAP_DEFS[self.map_id]
        self.TRACK_WIDTH = self._def["track_w"]
        self.points:      List[TrackPoint] = []
        self.checkpoints: List[Checkpoint] = []
        self.start_pos    = (0.0, 0.0)
        self.start_angle  = 0.0
        self._surface: pygame.Surface | None = None
        self._generate()

    # ── Генерация ────────────────────────────────────────────────────────
    def _generate(self):
        d    = self._def
        ctrl = CTRL_FNS[d["ctrl"]]()
        raw  = self._catmull_chain(ctrl)
        # Сглаживание Лапласа (убирает «рябь»)
        raw  = self._smooth(raw, passes=4)
        n    = len(raw)

        surfaces = ["asphalt"] * n
        df = d["dirt_frac"]
        if df > 0:
            ds = int(n * 0.30); dl = int(n * df)
            for i in range(dl):
                surfaces[(ds + i) % n] = "dirt"

        tw = self.TRACK_WIDTH
        self.points = [TrackPoint(x, y, surfaces[i], tw) for i, (x, y) in enumerate(raw)]

        p0, p1 = self.points[0], self.points[1]
        self.start_pos   = (p0.x, p0.y)
        self.start_angle = math.atan2(p1.y - p0.y, p1.x - p0.x)

        n_cp = 12; step = max(1, n // n_cp)
        for i in range(n_cp):
            idx = i * step; p = self.points[idx]; pn = self.points[(idx+1)%n]
            self.checkpoints.append(Checkpoint(p.x, p.y,
                math.atan2(pn.y-p.y, pn.x-p.x), idx))

        self._bake_surface()

    def _catmull_chain(self, ctrl):
        raw = []; n = len(ctrl)
        for i in range(n):
            p0=ctrl[(i-1)%n]; p1=ctrl[i]; p2=ctrl[(i+1)%n]; p3=ctrl[(i+2)%n]
            for ts in range(self.RESOLUTION):
                t = ts / self.RESOLUTION
                raw.append((self._catmull(p0[0],p1[0],p2[0],p3[0],t),
                             self._catmull(p0[1],p1[1],p2[1],p3[1],t)))
        return raw

    @staticmethod
    def _catmull(p0,p1,p2,p3,t):
        t2=t*t; t3=t2*t
        return 0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t2+(-p0+3*p1-3*p2+p3)*t3)

    @staticmethod
    def _smooth(pts, passes=4):
        """Сглаживание Лапласа — убирает мелкие неровности."""
        n = len(pts)
        for _ in range(passes):
            out = []
            for i in range(n):
                px = (pts[(i-1)%n][0] + pts[i][0] + pts[(i+1)%n][0]) / 3
                py = (pts[(i-1)%n][1] + pts[i][1] + pts[(i+1)%n][1]) / 3
                out.append((px, py))
            pts = out
        return pts

    # ── Пре-рендер ───────────────────────────────────────────────────────
    def _bake_surface(self):
        self._surface = pygame.Surface((WORLD_W, WORLD_H))
        surf = self._surface
        d    = self._def
        gc   = d["grass"]
        tw   = self.TRACK_WIDTH
        n    = len(self.points)

        # ── 1. ТРАВА — реалистичная ──────────────────────────────────────
        self._draw_grass(surf, gc)

        # ── 2. Асфальт / грязь ──────────────────────────────────────────
        for i in range(n):
            p=self.points[i]; pn=self.points[(i+1)%n]
            c = (44,44,54) if p.surface=="asphalt" else (108,80,44)
            pygame.draw.line(surf, c, (int(p.x),int(p.y)), (int(pn.x),int(pn.y)), tw*2+8)

        # Внутренняя чуть светлее
        for i in range(n):
            p=self.points[i]; pn=self.points[(i+1)%n]
            c = (54,54,66) if p.surface=="asphalt" else (120,92,56)
            pygame.draw.line(surf, c, (int(p.x),int(p.y)), (int(pn.x),int(pn.y)), tw*2-4)

        # ── 3. БОРДЮРЫ — ровные полосы полигонами ───────────────────────
        self._draw_curbs(surf, tw, n)

        # ── 4. Прерывистая осевая ────────────────────────────────────────
        stripe_len = 6   # точек = одна белая полоса
        gap_len    = 6   # пропуск
        for i in range(0, n, stripe_len + gap_len):
            for k in range(min(stripe_len, n-i)):
                idx = (i + k) % n
                p   = self.points[idx]
                pn  = self.points[(idx+1) % n]
                pygame.draw.line(surf, (200,192,70),
                                 (int(p.x),int(p.y)), (int(pn.x),int(pn.y)), 3)

        # ── 5. Стартовая линия ───────────────────────────────────────────
        self._draw_start_line(surf, tw)

    # ── Трава ─────────────────────────────────────────────────────────────
    def _draw_grass(self, surf: pygame.Surface, gc: tuple):
        """Реалистичная трава: базовый фон + кластеры разных оттенков + отдельные травинки."""
        surf.fill(gc)
        rng = random.Random(self.map_id * 7 + 13)

        # Базовые большие пятна — неравномерность почвы
        for _ in range(120):
            gx = rng.randint(0, WORLD_W)
            gy = rng.randint(0, WORLD_H)
            r  = rng.randint(40, 140)
            br = rng.randint(-22, 22)
            c  = (max(0,min(255,gc[0]+br)), max(0,min(255,gc[1]+br+8)), max(0,min(255,gc[2]+br-4)))
            pygame.draw.ellipse(surf, c, (gx-r, gy-r//2, r*2, r), 0)

        # Средние кластеры — тёмные и светлые пятна
        for _ in range(600):
            gx = rng.randint(0, WORLD_W)
            gy = rng.randint(0, WORLD_H)
            r  = rng.randint(8, 35)
            br = rng.randint(-30, 30)
            c  = (max(0,min(255,gc[0]+br)), max(0,min(255,gc[1]+br+12)), max(0,min(255,gc[2]+br)))
            pygame.draw.ellipse(surf, c, (gx-r, gy-r*2//3, r*2, r*4//3), 0)

        # Мелкие тёмные пятнышки — земля, тени
        for _ in range(900):
            gx = rng.randint(0, WORLD_W)
            gy = rng.randint(0, WORLD_H)
            r  = rng.randint(3, 10)
            br = rng.randint(-40, -10)
            c  = (max(0,gc[0]+br), max(0,gc[1]+br), max(0,gc[2]+br))
            pygame.draw.circle(surf, c, (gx, gy), r)

        # Отдельные травинки — вертикальные черточки
        for _ in range(4000):
            gx = rng.randint(0, WORLD_W)
            gy = rng.randint(0, WORLD_H)
            h_blade = rng.randint(4, 11)
            shade = rng.randint(-35, 35)
            tip_shade = shade + rng.randint(20, 50)  # кончик травинки светлее
            base_c = (max(0,min(255,gc[0]+shade)), max(0,min(255,gc[1]+shade+10)), max(0,min(255,gc[2]+shade-5)))
            tip_c  = (max(0,min(255,gc[0]+tip_shade)), max(0,min(255,gc[1]+tip_shade+18)), max(0,min(255,gc[2]+tip_shade)))
            # Стебель
            lean = rng.randint(-3, 3)
            pygame.draw.line(surf, base_c, (gx, gy), (gx+lean, gy-h_blade), 1)
            # Кончик — чуть другой цвет
            pygame.draw.line(surf, tip_c, (gx+lean, gy-h_blade), (gx+lean, gy-h_blade-2), 1)

        # Жёлтые соцветия / одуванчики (редко)
        for _ in range(180):
            gx = rng.randint(0, WORLD_W)
            gy = rng.randint(0, WORLD_H)
            pygame.draw.circle(surf, (210, 190, 40), (gx, gy), rng.randint(2,4))

    # ── Бордюры ───────────────────────────────────────────────────────────
    def _draw_curbs(self, surf: pygame.Surface, tw: int, n: int):
        """
        Ровные красно-белые бордюры: строим полигон для каждой полосы.
        Полоса = STRIPE_PTS точек трека.
        """
        STRIPE_PTS = max(2, n // 60)   # длина одной полосы в точках трека
        CURB_W = 12                    # ширина бордюра в пикселях

        for side in [-1, 1]:
            for seg_idx in range(0, n, STRIPE_PTS):
                is_red = (seg_idx // STRIPE_PTS) % 2 == 0
                color  = (215, 35, 35) if is_red else (235, 235, 235)

                # Внутренний край (на расстоянии tw) и внешний (tw + CURB_W)
                inner = []
                outer = []
                for k in range(STRIPE_PTS + 1):
                    i   = (seg_idx + k) % n
                    p   = self.points[i]
                    pn  = self.points[(i+1) % n]
                    ang  = math.atan2(pn.y-p.y, pn.x-p.x)
                    perp = ang + math.pi/2

                    ox_in  = math.cos(perp) * tw * side
                    oy_in  = math.sin(perp) * tw * side
                    ox_out = math.cos(perp) * (tw + CURB_W) * side
                    oy_out = math.sin(perp) * (tw + CURB_W) * side

                    inner.append((int(p.x + ox_in),  int(p.y + oy_in)))
                    outer.append((int(p.x + ox_out), int(p.y + oy_out)))

                # Полигон = inner вперёд + outer назад
                poly = inner + list(reversed(outer))
                if len(poly) >= 3:
                    try:
                        pygame.draw.polygon(surf, color, poly)
                    except Exception:
                        pass

    # ── Стартовая линия ───────────────────────────────────────────────────
    def _draw_start_line(self, surf: pygame.Surface, tw: int):
        p0  = self.points[0]; p1 = self.points[1]
        ang  = math.atan2(p1.y-p0.y, p1.x-p0.x) + math.pi/2
        TILE = 10
        for i in range(-tw, tw, TILE):
            sx = p0.x + math.cos(ang) * i
            sy = p0.y + math.sin(ang) * i
            c  = (255,255,255) if (i//TILE)%2==0 else (20,20,20)
            pygame.draw.rect(surf, c, (int(sx)-2, int(sy)-5, TILE, TILE))

    # ── Draw ─────────────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float):
        if self._surface:
            surface.blit(self._surface, (int(camera_x), int(camera_y)))

    def draw_minimap(self, surface: pygame.Surface, rect: pygame.Rect):
        pts = [(p.x,p.y) for p in self.points]
        if not pts: return
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        mnx,mxx=min(xs),max(xs); mny,mxy=min(ys),max(ys)
        rx=mxx-mnx+1; ry=mxy-mny+1
        def mm(px,py): return (int(rect.x+(px-mnx)/rx*rect.width),
                               int(rect.y+(py-mny)/ry*rect.height))
        mpts=[mm(p[0],p[1]) for p in pts]
        pygame.draw.lines(surface,(50,50,65),True,mpts,8)
        pygame.draw.lines(surface,(90,90,110),True,mpts,4)

    # ── Утилиты ──────────────────────────────────────────────────────────
    def nearest_point_index(self, x: float, y: float) -> int:
        bi, bd = 0, float("inf")
        for i, p in enumerate(self.points):
            d=(x-p.x)**2+(y-p.y)**2
            if d<bd: bd=d; bi=i
        return bi

    def get_surface_at(self, x, y) -> str:
        i=self.nearest_point_index(x,y); p=self.points[i]
        return p.surface if (x-p.x)**2+(y-p.y)**2<(p.width*1.15)**2 else "grass"

    def is_on_track(self, x, y) -> bool:
        i=self.nearest_point_index(x,y); p=self.points[i]
        return (x-p.x)**2+(y-p.y)**2<(p.width*1.2)**2

    def dist_to_center(self, x, y) -> float:
        i=self.nearest_point_index(x,y); p=self.points[i]
        return math.hypot(x-p.x, y-p.y)

    def get_progress(self, x, y) -> float:
        return self.nearest_point_index(x,y)/len(self.points)

    def get_ahead_point(self, index: int, steps: int = 8) -> TrackPoint:
        return self.points[(index+steps)%len(self.points)]

    def get_total_points(self) -> int:
        return len(self.points)

    def get_curvature(self, index: int, window: int = 8) -> float:
        n=len(self.points); pts=[self.points[(index+j)%n] for j in range(window)]
        angles=[]
        for i in range(len(pts)-1):
            angles.append(math.atan2(pts[i+1].y-pts[i].y, pts[i+1].x-pts[i].x))
        turn=0.0
        for i in range(len(angles)-1):
            diff=angles[i+1]-angles[i]
            while diff>math.pi:  diff-=2*math.pi
            while diff<-math.pi: diff+=2*math.pi
            turn+=abs(diff)
        return min(1.0, turn/(math.pi*0.45))

    @property
    def map_name(self): return self._def["name"]
    @property
    def map_desc(self):  return self._def["desc"]
