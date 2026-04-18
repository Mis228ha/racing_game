"""
Car — игровой объект автомобиля.
Аркадная физика, без дрифта, частицы только нитро и пыль вне трека.
"""

import math
import random
import pygame
from dataclasses import dataclass
from typing import List, Tuple, Optional

from src.engine.physics import CarPhysicsState, CarConfig, PhysicsEngine
from src.engine.event_bus import EventBus, Events
from src.engine.asset_manager import AssetManager


@dataclass
class Particle:
    x: float; y: float
    vx: float; vy: float
    life: float; max_life: float
    r: float
    color: Tuple[int, int, int]


class Car:
    CAR_NAMES = ["car_red", "car_blue", "car_yellow", "car_green", "car_purple"]
    COLORS    = [(220, 60, 60), (60, 160, 220), (230, 200, 40), (60, 200, 80), (180, 60, 220)]

    def __init__(self, car_id: str, color_index: int,
                 x: float, y: float, angle: float,
                 event_bus: EventBus, assets: AssetManager,
                 config: CarConfig = None):
        self.car_id = car_id
        self.color  = self.COLORS[color_index % len(self.COLORS)]
        self.event_bus = event_bus
        self.assets    = assets

        self.state  = CarPhysicsState(x=x, y=y, angle=angle)
        self.config = config or CarConfig()
        self.particles: List[Particle] = []

        # Прогресс
        self.lap:      int   = 0
        self.sector:   int   = 0
        self.progress: float = 0.0
        self.finished: bool  = False
        self.finish_time: float = 0.0

        # Спрайт
        name = self.CAR_NAMES[color_index % len(self.CAR_NAMES)]
        base = assets.get_image(name)
        self._sprite = pygame.transform.scale(base, (44, 24))
        self._sprite_cache: dict[int, pygame.Surface] = {}
        self._nitro_frame = 0

    def update(self, dt: float):
        self._update_particles(dt)
        self._spawn_particles()

    def _spawn_particles(self):
        s = self.state
        # Пыль вне трека
        if not s.on_track and s.speed > 20:
            rx = s.x - math.cos(s.angle) * 16
            ry = s.y - math.sin(s.angle) * 16
            self.particles.append(Particle(
                x=rx + random.uniform(-4, 4),
                y=ry + random.uniform(-4, 4),
                vx=random.uniform(-20, 20),
                vy=random.uniform(-20, 20),
                life=0.5, max_life=0.5,
                r=random.uniform(3, 6),
                color=(120, 90, 50)
            ))
        # Нитро выхлоп
        if s.nitro_active and s.nitro > 0:
            rx = s.x - math.cos(s.angle) * 22
            ry = s.y - math.sin(s.angle) * 22
            for _ in range(3):
                self.particles.append(Particle(
                    x=rx, y=ry,
                    vx=-math.cos(s.angle) * random.uniform(50, 100) + random.uniform(-10, 10),
                    vy=-math.sin(s.angle) * random.uniform(50, 100) + random.uniform(-10, 10),
                    life=0.25, max_life=0.25,
                    r=random.uniform(4, 9),
                    color=(0, 180, 255)
                ))

    def _update_particles(self, dt: float):
        alive = []
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 0.92; p.vy *= 0.92
            p.life -= dt
            if p.life > 0:
                alive.append(p)
        self.particles = alive

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float):
        s = self.state
        sx, sy = s.x + cam_x, s.y + cam_y

        # Частицы
        for p in self.particles:
            alpha = int(220 * (p.life / p.max_life))
            r = max(1, int(p.r))
            try:
                ps = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
                pygame.draw.circle(ps, (*p.color, alpha), (r, r), r)
                surface.blit(ps, (int(p.x + cam_x) - r, int(p.y + cam_y) - r))
            except Exception:
                pass

        # Тень
        shadow = pygame.Surface((50, 28), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), (0, 0, 50, 28))
        rs = pygame.transform.rotate(shadow, -math.degrees(s.angle))
        surface.blit(rs, (sx - rs.get_width()//2 + 3, sy - rs.get_height()//2 + 4))

        # Спрайт с кэшем
        angle_key = int(math.degrees(s.angle)) % 360
        if angle_key not in self._sprite_cache:
            self._sprite_cache[angle_key] = pygame.transform.rotate(self._sprite, -angle_key)
            if len(self._sprite_cache) > 360:
                self._sprite_cache.clear()
        rot = self._sprite_cache[angle_key]
        surface.blit(rot, (sx - rot.get_width()//2, sy - rot.get_height()//2))

        # Стрелка над игроком
        if self.car_id in ("player", "player2"):
            col = (255, 255, 255) if self.car_id == "player" else (255, 220, 60)
            pygame.draw.polygon(surface, col, [
                (sx, sy - 26), (sx - 6, sy - 18), (sx + 6, sy - 18)
            ])

        # Нитро-свечение
        if s.nitro_active and s.nitro > 0:
            self._nitro_frame = (self._nitro_frame + 1) % 6
            gr = 12 + self._nitro_frame
            glow = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (0, 180, 255, 140), (gr, gr), gr)
            rx = sx - math.cos(s.angle) * 22
            ry = sy - math.sin(s.angle) * 22
            surface.blit(glow, (int(rx) - gr, int(ry) - gr))

    def apply_input(self, throttle: float, brake: float,
                    steer: float, nitro: bool):
        self.state.throttle     = throttle
        self.state.brake        = brake
        self.state._steer_input = steer
        self.state.nitro_active = nitro and self.state.nitro > 0.01

    @property
    def x(self): return self.state.x
    @property
    def y(self): return self.state.y

    @property
    def speed_kmh(self):
        return self.state.speed * 3.6 / PhysicsEngine.PIXELS_PER_METER
