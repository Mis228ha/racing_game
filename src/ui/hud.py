"""
RaceState — разделённый экран для 2 игроков, камера за каждым.
• Сплит-скрин: левая половина P1, правая — P2
• Без тряски камеры при столкновении
• Отскок от бордюров (не застревание)
• Миникарта со стрелками направления
• Сеть: оба имеют ботов, каждый видит свою машину
"""

import math
import random
import time
import pygame

from src.engine.game_state import BaseState
from src.engine.event_bus  import EventBus, Events
from src.engine.physics    import PhysicsEngine, CarConfig
from src.engine.asset_manager import AssetManager
from src.game_objects.car  import Car
from src.game_objects.track import Track
from src.ai.ai_car         import AIManager

TOTAL_LAPS = 3
POSITIONS  = ["1st", "2nd", "3rd", "4th", "5th", "6th"]


# ── Камера (без тряски) ───────────────────────────────────────────────────────
class Camera:
    def __init__(self, vw: int, vh: int):
        """vw, vh — размер вьюпорта (половина экрана или весь)."""
        self.vw = vw; self.vh = vh
        self.x = 0.0; self.y = 0.0

    def set_target(self, tx: float, ty: float, dt: float):
        lag = 0.10
        self.x += (self.vw / 2 - tx - self.x) * (1 - lag)
        self.y += (self.vh / 2 - ty - self.y) * (1 - lag)

    @property
    def ox(self): return self.x
    @property
    def oy(self): return self.y


# ── Вспомогательный HUD-бокс ─────────────────────────────────────────────────
def draw_box(surface, font_sm, font_big, x, y, label, value, w=90, color=(255,255,255)):
    bg = pygame.Surface((w, 50), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    pygame.draw.rect(bg, (70,70,95,200), bg.get_rect(), 1, border_radius=5)
    surface.blit(bg, (x, y))
    l = font_sm.render(label, True, (110,110,145))
    v = font_big.render(str(value), True, color)
    surface.blit(l, (x+5, y+3))
    surface.blit(v, (x+5, y+20))


# ── RaceState ─────────────────────────────────────────────────────────────────
class RaceState(BaseState):
    def __init__(self, screen, event_bus, assets,
                 two_player: bool = False,
                 num_bots:   int  = 3,
                 map_id:     int  = 0,
                 seed:       int  = 42,
                 net_host=None,
                 net_client=None,
                 **kwargs):
        super().__init__(screen, event_bus, assets)
        self.two_player  = two_player
        self.num_bots    = num_bots
        self.map_id      = map_id
        self.net_host    = net_host
        self.net_client  = net_client
        self._is_network = (net_host is not None or net_client is not None)

    def on_enter(self):
        w, h = self.screen.get_size()
        self.screen_w = w; self.screen_h = h

        # Определяем количество игроков и вьюпорты
        self._split = self.two_player or self._is_network
        if self._split:
            # Левая и правая половины
            half_w = w // 2
            self._vp = [
                pygame.Rect(0,    0, half_w, h),
                pygame.Rect(half_w, 0, half_w, h),
            ]
            self._cams = [Camera(half_w, h), Camera(half_w, h)]
        else:
            self._vp  = [pygame.Rect(0, 0, w, h)]
            self._cams = [Camera(w, h)]

        self.track   = Track(self.map_id)
        self.physics = PhysicsEngine(self.event_bus)
        self.ai_mgr  = AIManager(self.track)
        self.cars:    list[Car] = []
        self.players: list[Car] = []

        self.race_finished  = False
        self.countdown      = 3.5
        self.countdown_done = False
        self.start_time     = 0.0
        self.race_time      = 0.0
        self.lap_msgs: list[tuple[str, float, tuple]] = []

        # Офф-скрин поверхности для каждого вьюпорта
        if self._split:
            half_w = w // 2
            self._vsurf = [pygame.Surface((half_w, h)),
                           pygame.Surface((half_w, h))]
        else:
            self._vsurf = [pygame.Surface((w, h))]

        self._setup_cars()
        self._subscribe()

    def _setup_cars(self):
        trk = self.track
        n   = trk.get_total_points()
        # Сеть: оба игрока + боты на обоих
        num_humans = 2 if (self.two_player or self._is_network) else 1
        # num_bots уже задан снаружи (в сети передаём 3)
        total = num_humans + self.num_bots

        tw = trk.TRACK_WIDTH
        offsets_lat = [0, -tw*0.42, tw*0.42, -tw*0.80, tw*0.80, 0]
        offsets_lon = [0, 0, 0, tw, tw, tw*2]

        for i in range(total):
            idx = max(0, (n // 60) * (i // 2))
            p   = trk.points[idx]; pn = trk.points[(idx+1)%n]
            ang  = math.atan2(pn.y-p.y, pn.x-p.x); perp = ang + math.pi/2
            lat  = offsets_lat[i % len(offsets_lat)]
            lon  = offsets_lon[i % len(offsets_lon)]
            cx   = p.x + math.cos(perp)*lat - math.cos(ang)*lon
            cy   = p.y + math.sin(perp)*lat - math.sin(ang)*lon

            is_human = i < num_humans
            if is_human:
                car_id = "player" if i==0 else "player2"
                c_idx  = 0 if i==0 else 2
            else:
                car_id = f"bot_{i}"; c_idx = [1,3,4,2][(i-num_humans)%4]

            cfg = CarConfig()
            if not is_human:
                cfg.max_speed    *= random.uniform(0.94, 1.05)
                cfg.acceleration *= random.uniform(0.94, 1.05)

            car = Car(car_id, c_idx, cx, cy, ang, self.event_bus, self.assets, cfg)
            car.sector = idx
            self.cars.append(car)
            self.physics.register(car.state, car.config, car_id)
            if is_human:
                self.players.append(car)
            else:
                self.ai_mgr.add_car(car, i - num_humans)

    def _subscribe(self):
        self.event_bus.subscribe(Events.ON_LAP_COMPLETE, self._on_lap)
        self.event_bus.subscribe(Events.ON_RACE_FINISH,  self._on_finish)

    def _on_lap(self, data):
        cid = data.get("car_id",""); lap = data.get("lap",0)
        col = (255,255,255) if cid=="player" else (255,220,60)
        who = "P1" if cid=="player" else ("P2" if cid=="player2" else "BOT")
        self.lap_msgs.append((f"{who}: КРУГ {lap}!", 2.2, col))
    def _on_finish(self, data): self.race_finished = True

    # ── Events ───────────────────────────────────────────────────────────────
    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._cleanup(); self.manager.replace("menu")
            if event.key == pygame.K_r and self.race_finished:
                self._cleanup()
                self.manager.replace("race", map_id=self.map_id,
                                     two_player=self.two_player,
                                     num_bots=self.num_bots)

    # ── Update ───────────────────────────────────────────────────────────────
    def update(self, dt: float):
        if not self.countdown_done:
            self.countdown -= dt
            if self.countdown <= 0:
                self.countdown_done = True
                self.start_time = time.time()
            return
        if self.race_finished: return

        self.race_time = time.time() - self.start_time
        keys = pygame.key.get_pressed()

        # ── LAN-клиент: применяем стейт с хоста ─────────────────────────
        if self.net_client:
            states = self.net_client.get_states()
            self._apply_net_states(states)
            # Клиент управляет player2
            from src.network.game_net import InputState
            self.net_client.send_input(InputState(
                throttle=1.0 if keys[pygame.K_w] else 0.0,
                brake   =1.0 if keys[pygame.K_s]  else 0.0,
                steer   =(-1.0 if keys[pygame.K_a] else 0.0)+(1.0 if keys[pygame.K_d] else 0.0),
                nitro   =bool(keys[pygame.K_LSHIFT]),
            ))
            self._update_cameras(dt)
            self.lap_msgs = [(t,d-dt,c) for t,d,c in self.lap_msgs if d-dt>0]
            return

        # ── P1 (WASD) ────────────────────────────────────────────────────
        self.players[0].apply_input(
            throttle=1.0 if keys[pygame.K_w] else 0.0,
            brake   =1.0 if (keys[pygame.K_s] or keys[pygame.K_SPACE]) else 0.0,
            steer   =(-1.0 if keys[pygame.K_a] else 0.0)+(1.0 if keys[pygame.K_d] else 0.0),
            nitro   =bool(keys[pygame.K_LSHIFT]),
        )

        # ── P2 (стрелки) ─────────────────────────────────────────────────
        if len(self.players) > 1:
            p2_inp = None
            if self.net_host:
                ci = self.net_host.get_client_input()
                p2_inp = (ci.throttle, ci.brake, ci.steer, ci.nitro)
            if p2_inp:
                self.players[1].apply_input(*p2_inp)
            else:
                self.players[1].apply_input(
                    throttle=1.0 if keys[pygame.K_UP]    else 0.0,
                    brake   =1.0 if keys[pygame.K_DOWN]  else 0.0,
                    steer   =(-1.0 if keys[pygame.K_LEFT] else 0.0)+(1.0 if keys[pygame.K_RIGHT] else 0.0),
                    nitro   =bool(keys[pygame.K_RSHIFT]),
                )

        # ── AI ───────────────────────────────────────────────────────────
        self.ai_mgr.update(dt, self.cars)

        # ── Физика ───────────────────────────────────────────────────────
        self.physics.update(dt)

        # ── Трек / граница / лапы ────────────────────────────────────────
        for car in self.cars:
            s = car.state
            s.surface  = self.track.get_surface_at(s.x, s.y)
            s.on_track = self.track.is_on_track(s.x, s.y)
            self._bounce_boundary(car)
            car.update(dt)
            self._update_lap(car)

        # ── Коллизии между машинами ───────────────────────────────────────
        for i in range(len(self.cars)):
            for j in range(i+1, len(self.cars)):
                a, b = self.cars[i], self.cars[j]
                if PhysicsEngine.check_collision(a.state, b.state):
                    PhysicsEngine.resolve_collision(a.state, b.state)

        self._update_cameras(dt)

        # ── Хост: отправляем стейт клиенту ───────────────────────────────
        if self.net_host:
            self._send_net_state()

        self.lap_msgs = [(t,d-dt,c) for t,d,c in self.lap_msgs if d-dt>0]

    def _bounce_boundary(self, car: Car):
        """Отскок от бортика — машина не застревает, а отталкивается назад."""
        s   = car.state
        tw  = self.track.TRACK_WIDTH
        idx = self.track.nearest_point_index(s.x, s.y)
        p   = self.track.points[idx]
        dist = math.hypot(s.x - p.x, s.y - p.y)

        hard_limit = tw * 1.28
        if dist > hard_limit and dist > 1.0:
            # Нормаль — направление ОТ центра
            nx = (s.x - p.x) / dist
            ny = (s.y - p.y) / dist

            # Прижать к границе
            s.x = p.x + nx * hard_limit
            s.y = p.y + ny * hard_limit

            # Проекция скорости на нормаль бортика
            vx = math.cos(s.angle) * s.speed
            vy = math.sin(s.angle) * s.speed
            vn = vx * nx + vy * ny  # скорость вдоль нормали

            # Отскок: гасим нормальную компоненту + разворачиваем угол
            if vn > 0:  # машина движется в стену
                # Отразить скорость
                bounce = 0.18
                vx -= (1 + bounce) * vn * nx
                vy -= (1 + bounce) * vn * ny
                s.speed = math.hypot(vx, vy) * 0.88
                s.angle = math.atan2(vy, vx)
            s.on_track = False

    def _update_cameras(self, dt: float):
        for i, cam in enumerate(self._cams):
            if i < len(self.players):
                car = self.players[i]
                cam.set_target(car.x, car.y, dt)

    def _apply_net_states(self, states: list):
        for sd in states:
            cid = sd.get("car_id")
            for car in self.cars:
                if car.car_id == cid:
                    s = car.state
                    s.x=sd["x"]; s.y=sd["y"]
                    s.angle=sd["angle"]; s.speed=sd["speed"]
                    car.lap=sd["lap"]; car.progress=sd["progress"]
                    s.nitro=sd["nitro"]; s.on_track=sd["on_track"]
                    break

    def _send_net_state(self):
        states = [{
            "car_id": car.car_id,
            "x": round(car.state.x,1), "y": round(car.state.y,1),
            "angle": round(car.state.angle,3), "speed": round(car.state.speed,1),
            "lap": car.lap, "progress": round(car.progress,4),
            "nitro": round(car.state.nitro,3), "on_track": car.state.on_track,
        } for car in self.cars]
        self.net_host.send_state(states)

    def _update_lap(self, car: Car):
        n  = self.track.get_total_points()
        ns = self.track.nearest_point_index(car.x, car.y)
        fwd = (ns - car.sector + n) % n
        if 0 < fwd < 10:
            car.sector = ns
        progress = car.sector / n
        if car.sector == 0 and car.progress > 0.85:
            car.lap += 1; car.progress = 0.0
            is_human = car.car_id in ("player","player2")
            self.event_bus.emit(Events.ON_LAP_COMPLETE,{"car_id":car.car_id,"lap":car.lap})
            if is_human and car.lap >= TOTAL_LAPS and not self.race_finished:
                car.finish_time = self.race_time
                self.event_bus.emit(Events.ON_RACE_FINISH,{"car_id":car.car_id})
        else:
            car.progress = progress

    # ── Draw ─────────────────────────────────────────────────────────────────
    def draw(self):
        self.screen.fill((15, 15, 15))

        if self._split:
            self._draw_split()
        else:
            self._draw_viewport(0, self._vsurf[0], self._cams[0], self._vp[0])
            self.screen.blit(self._vsurf[0], (0, 0))
            self._draw_hud_single(self._vp[0])

        # Обратный отсчёт / финиш — поверх всего
        w, h = self.screen_w, self.screen_h
        if not self.countdown_done:
            self._draw_countdown(w, h)
        self._draw_lap_msgs(w, h)
        if self.race_finished:
            self._draw_finish(w, h)

    def _draw_split(self):
        """Сплит-скрин: каждый вьюпорт рисует мир через свою камеру."""
        w, h = self.screen_w, self.screen_h
        half_w = w // 2

        for vi in range(2):
            surf = self._vsurf[vi]
            cam  = self._cams[vi]
            vp   = self._vp[vi]
            self._draw_viewport(vi, surf, cam, vp)
            self.screen.blit(surf, (vp.x, vp.y))
            # HUD для этого игрока
            if vi < len(self.players):
                self._draw_hud_player(self.players[vi], vp, vi)
            # Миникарта
            self._draw_minimap(surf, cam, vp, vi)
            self.screen.blit(surf, (vp.x, vp.y))  # reblit after minimap

        # Разделительная линия
        pygame.draw.line(self.screen, (40,40,60), (half_w-1, 0), (half_w-1, h), 3)
        pygame.draw.line(self.screen, (80,80,110),(half_w, 0), (half_w, h), 1)

    def _draw_viewport(self, vi: int, surf: pygame.Surface,
                       cam: Camera, vp: pygame.Rect):
        """Рисует весь мир в surf через смещение cam."""
        surf.fill((18, 18, 22))
        self._draw_grid_on(surf, cam)
        self.track.draw(surf, cam.ox, cam.oy)

        player_ids = {p.car_id for p in self.players}
        # Боты
        for car in self.cars:
            if car.car_id not in player_ids:
                car.draw(surf, cam.ox, cam.oy)
        # Игроки поверх
        for car in self.players:
            car.draw(surf, cam.ox, cam.oy)

    def _draw_grid_on(self, surf: pygame.Surface, cam: Camera):
        w, h = surf.get_size()
        ox = int(cam.ox) % 80; oy = int(cam.oy) % 80
        for gx in range(-80, w+80, 80):
            pygame.draw.line(surf,(22,22,34),(gx+ox,0),(gx+ox,h))
        for gy in range(-80, h+80, 80):
            pygame.draw.line(surf,(22,22,34),(0,gy+oy),(w,gy+oy))

    # ── HUD ──────────────────────────────────────────────────────────────────
    def _draw_hud_single(self, vp: pygame.Rect):
        car = self.players[0]
        self._draw_hud_player(car, vp, 0)
        self._draw_minimap_full(vp)

    def _draw_hud_player(self, car: Car, vp: pygame.Rect, idx: int):
        """Рисует HUD-полоску в вьюпорте idx."""
        fsm  = self.assets.get_font(11)
        fbig = self.assets.get_font(18, bold=True)
        s    = car.state

        spd   = int(car.speed_kmh)
        lap   = f"{min(car.lap+1, TOTAL_LAPS)}/{TOTAL_LAPS}"
        pos   = self._get_position(car)
        pos_s = POSITIONS[pos-1] if pos<=len(POSITIONS) else f"{pos}th"
        t_s   = f"{self.race_time:.1f}s"
        sp_col = (255,190,0) if spd>160 else (255,255,255)

        px = vp.x; vw = vp.width

        # Фон полоски
        bg = pygame.Surface((vw, 56), pygame.SRCALPHA)
        bg.fill((0,0,0,160))
        self.screen.blit(bg, (px, 0))

        label = "P1" if car.car_id=="player" else "P2"
        col   = (255,100,100) if car.car_id=="player" else (100,180,255)
        pl = self.assets.get_font(14, bold=True).render(label, True, col)
        self.screen.blit(pl, (px+5, 20))

        draw_box(self.screen, fsm, fbig, px+36,  4, "СКОРОСТЬ", spd, w=84, color=sp_col)
        draw_box(self.screen, fsm, fbig, px+124, 4, "КРУГ",     lap, w=76)
        draw_box(self.screen, fsm, fbig, px+204, 4, "МЕСТО",    pos_s, w=76,
                 color=(100,230,100) if pos==1 else (255,255,255))
        draw_box(self.screen, fsm, fbig, px+284, 4, "ВРЕМЯ",    t_s, w=76)

        # Нитро-бар
        nx = px + 368
        pygame.draw.rect(self.screen,(25,25,45),(nx,12,100,10),border_radius=3)
        nw = int(100*s.nitro)
        if nw>1:
            nc=(0,210,255) if s.nitro>0.3 else (80,80,140)
            pygame.draw.rect(self.screen,nc,(nx,12,nw,10),border_radius=3)
        nl = fsm.render("NOS",True,(80,160,210)); self.screen.blit(nl,(nx,24))

        # Предупреждение вне трека
        if not s.on_track:
            warn = self.assets.get_font(12,bold=True).render("⚠ ВНЕ ТРАССЫ",True,(255,70,70))
            self.screen.blit(warn,(px+vw-warn.get_width()-8, 20))

    # ── Миникарта ─────────────────────────────────────────────────────────────
    def _minimap_transform(self, rect: pygame.Rect):
        pts = self.track.points
        xs=[p.x for p in pts]; ys=[p.y for p in pts]
        mnx,mxx=min(xs),max(xs); mny,mxy=min(ys),max(ys)
        rx=mxx-mnx+1; ry=mxy-mny+1
        def to_mm(px,py):
            return (int(rect.x+(px-mnx)/rx*rect.width),
                    int(rect.y+(py-mny)/ry*rect.height))
        return to_mm, mnx, mny, rx, ry

    def _draw_minimap(self, surf: pygame.Surface, cam: Camera,
                      vp: pygame.Rect, vi: int):
        """Рисует миникарту с направлением машин в угол вьюпорта."""
        mm_w, mm_h = 140, 105
        mm_x = vp.width - mm_w - 6
        mm_y = vp.height - mm_h - 6
        mm   = pygame.Rect(mm_x, mm_y, mm_w, mm_h)

        bg = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
        bg.fill((0,0,0,175))
        pygame.draw.rect(bg,(60,60,85,220),bg.get_rect(),1,border_radius=6)
        surf.blit(bg, (mm_x, mm_y))

        self.track.draw_minimap(surf, mm)
        to_mm, mnx, mny, rx, ry = self._minimap_transform(mm)

        player_ids = {p.car_id for p in self.players}
        for car in self.cars:
            cx, cy = to_mm(car.x, car.y)
            is_p   = car.car_id in player_ids
            r      = 5 if is_p else 3

            # Кружок
            pygame.draw.circle(surf, car.color, (cx,cy), r)
            if is_p:
                pygame.draw.circle(surf, (255,255,255),(cx,cy),r,1)

            # Стрелка направления движения
            if is_p:
                alen = 10
                ax = cx + math.cos(car.state.angle)*alen
                ay = cy + math.sin(car.state.angle)*alen
                pygame.draw.line(surf, (255,255,255),(cx,cy),(int(ax),int(ay)),2)
                # наконечник
                perp = car.state.angle + math.pi*0.75
                tip_x = int(ax + math.cos(perp)*4)
                tip_y = int(ay + math.sin(perp)*4)
                pygame.draw.line(surf,(255,255,255),(int(ax),int(ay)),(tip_x,tip_y),2)
            else:
                # Боты — маленькая точка-направление
                ax = cx + math.cos(car.state.angle)*6
                ay = cy + math.sin(car.state.angle)*6
                pygame.draw.line(surf,(180,180,180),(cx,cy),(int(ax),int(ay)),1)

        # Метка: P1 / P2
        label = f"P{vi+1}"
        fl = self.assets.get_font(10,bold=True).render(label, True,
             (255,100,100) if vi==0 else (100,180,255))
        surf.blit(fl, (mm_x+4, mm_y+4))

    def _draw_minimap_full(self, vp: pygame.Rect):
        """Одиночный режим — миникарта в правый нижний угол экрана."""
        mm_w, mm_h = 150, 112
        mm = pygame.Rect(self.screen_w - mm_w - 6, self.screen_h - mm_h - 6, mm_w, mm_h)
        bg = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
        bg.fill((0,0,0,175))
        pygame.draw.rect(bg,(60,60,85,220),bg.get_rect(),1,border_radius=6)
        self.screen.blit(bg, mm.topleft)
        self.track.draw_minimap(self.screen, mm)
        to_mm, *_ = self._minimap_transform(mm)
        player_ids = {p.car_id for p in self.players}
        for car in self.cars:
            cx, cy = to_mm(car.x, car.y)
            is_p = car.car_id in player_ids
            r = 5 if is_p else 3
            pygame.draw.circle(self.screen, car.color, (cx,cy), r)
            if is_p:
                alen = 11
                ax = cx + math.cos(car.state.angle)*alen
                ay = cy + math.sin(car.state.angle)*alen
                pygame.draw.line(self.screen,(255,255,255),(cx,cy),(int(ax),int(ay)),2)
                perp = car.state.angle + math.pi*0.75
                pygame.draw.line(self.screen,(255,255,255),(int(ax),int(ay)),
                                 (int(ax+math.cos(perp)*4), int(ay+math.sin(perp)*4)),2)

    # ── Обратный отсчёт / Финиш ───────────────────────────────────────────────
    def _draw_countdown(self, w, h):
        font = self.assets.get_font(100, bold=True)
        n    = max(0, int(self.countdown))
        text = str(n) if n > 0 else "GO!"
        color = (255,80,80) if n>0 else (80,255,120)
        surf  = font.render(text, True, color)
        surf.set_alpha(int(255*min(1.0, self.countdown%1+0.3)))
        self.screen.blit(surf, (w//2 - surf.get_width()//2, h//2 - 70))

    def _draw_lap_msgs(self, w, h):
        font = self.assets.get_font(28, bold=True)
        for i, (text, dur, color) in enumerate(self.lap_msgs[-3:]):
            surf = font.render(text, True, color)
            surf.set_alpha(min(255, int(255*dur/0.5)))
            self.screen.blit(surf, (w//2-surf.get_width()//2, 62+i*38))

    def _draw_finish(self, w, h):
        overlay = pygame.Surface((w,h), pygame.SRCALPHA)
        overlay.fill((0,0,0,175))
        self.screen.blit(overlay,(0,0))
        f1=self.assets.get_font(52,bold=True)
        f2=self.assets.get_font(22)
        f3=self.assets.get_font(16)
        if len(self.players)>=2:
            p1p=self._get_position(self.players[0])
            p2p=self._get_position(self.players[1])
            winner="P1 ПОБЕДИЛ!" if p1p<p2p else "P2 ПОБЕДИЛ!"
            ts=f1.render(winner,True,(255,220,60))
            self.screen.blit(ts,(w//2-ts.get_width()//2,h//2-100))
            info=f2.render(f"P1: {POSITIONS[p1p-1]}   P2: {POSITIONS[min(p2p,5)-1]}",True,(200,200,200))
            self.screen.blit(info,(w//2-info.get_width()//2,h//2-20))
        else:
            pos=self._get_position(self.players[0])
            title="ПОБЕДА!" if pos==1 else f"ФИНИШ — {POSITIONS[pos-1]}"
            col=(255,220,60) if pos==1 else (200,200,200)
            surf=f1.render(title,True,col)
            self.screen.blit(surf,(w//2-surf.get_width()//2,h//2-90))
        ts2=f2.render(f"Время: {self.race_time:.2f}с",True,(180,180,200))
        self.screen.blit(ts2,(w//2-ts2.get_width()//2,h//2+30))
        hs=f3.render("R — рестарт   ESC — меню",True,(100,100,130))
        self.screen.blit(hs,(w//2-hs.get_width()//2,h//2+80))

    def _get_position(self, car: Car) -> int:
        ranked = sorted(self.cars, key=lambda c: c.lap+c.progress, reverse=True)
        for i, c in enumerate(ranked):
            if c.car_id == car.car_id: return i+1
        return 1

    def _cleanup(self):
        try: self.event_bus.unsubscribe(Events.ON_LAP_COMPLETE, self._on_lap)
        except: pass
        try: self.event_bus.unsubscribe(Events.ON_RACE_FINISH,  self._on_finish)
        except: pass
        self.physics.clear()
        self.ai_mgr.clear()
        if self.net_host:   self.net_host.stop()
        if self.net_client: self.net_client.stop()

    def on_exit(self):
        self._cleanup()
