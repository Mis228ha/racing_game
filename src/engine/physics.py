"""
Physics — аркадная физика автомобиля.
Простая, стабильная, без дрифта.
Машина едет по треку как надо.
"""

import math
from dataclasses import dataclass, field
from src.engine.event_bus import EventBus, Events

SURFACE_GRIP = {
    "asphalt": 1.00,
    "dirt":    0.65,
    "grass":   0.45,
    "sand":    0.40,
}

PHYSICS_DT = 1.0 / 120.0  # 120Hz для стабильности


@dataclass
class CarConfig:
    max_speed:      float = 300.0   # пикс/с
    acceleration:   float = 220.0   # пикс/с²
    braking:        float = 400.0   # пикс/с²
    friction:       float = 160.0   # естественное замедление
    steer_speed:    float = 2.8     # рад/с при повороте
    steer_return:   float = 4.0     # возврат руля к нулю
    off_track_drag: float = 0.92    # множитель скорости вне трека (per-dt)
    nitro_boost:    float = 1.6
    nitro_drain:    float = 0.30
    nitro_refill:   float = 0.07


@dataclass
class CarPhysicsState:
    x:     float = 0.0
    y:     float = 0.0
    angle: float = 0.0

    speed: float = 0.0
    steer: float = 0.0
    nitro: float = 1.0
    nitro_active: bool = False

    rpm:  float = 900.0
    gear: int   = 1

    surface:  str   = "asphalt"
    on_track: bool  = True
    health:   float = 1.0

    throttle:     float = 0.0
    brake:        float = 0.0
    _steer_input: float = 0.0
    _accumulator: float = 0.0


class PhysicsEngine:
    PIXELS_PER_METER = 50.0

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._cars: list[tuple] = []

    def register(self, state: CarPhysicsState, config: CarConfig, car_id: str):
        self._cars.append((state, config, car_id))

    def unregister(self, car_id: str):
        self._cars = [(s, c, i) for s, c, i in self._cars if i != car_id]

    def clear(self):
        self._cars.clear()

    def update(self, dt: float):
        for state, config, car_id in self._cars:
            state._accumulator += dt
            while state._accumulator >= PHYSICS_DT:
                self._step(state, config, PHYSICS_DT)
                state._accumulator -= PHYSICS_DT

    def _step(self, s: CarPhysicsState, c: CarConfig, dt: float):
        grip = SURFACE_GRIP.get(s.surface, 1.0)

        # Нитро
        if s.nitro_active and s.nitro > 0:
            s.nitro = max(0.0, s.nitro - c.nitro_drain * dt)
        else:
            s.nitro = min(1.0, s.nitro + c.nitro_refill * dt)
            s.nitro_active = False

        accel_mult = c.nitro_boost if (s.nitro_active and s.nitro > 0) else 1.0
        max_spd    = c.max_speed * (1.3 if s.nitro_active else 1.0)

        # Ускорение / торможение / трение
        if s.throttle > 0:
            s.speed += c.acceleration * accel_mult * grip * s.throttle * dt
        elif s.brake > 0:
            s.speed -= c.braking * s.brake * dt
        else:
            s.speed -= c.friction * dt

        if not s.on_track:
            s.speed *= (c.off_track_drag ** dt)

        s.speed = max(0.0, min(max_spd, s.speed))

        # Руление — плавное, пропорционально скорости
        s.steer += (s._steer_input - s.steer) * min(1.0, c.steer_return * dt * 3)
        speed_factor = min(1.0, s.speed / 80.0)
        if s.speed > 2.0:
            s.angle += s.steer * c.steer_speed * speed_factor * dt

        # Движение вперёд по углу
        s.x += math.cos(s.angle) * s.speed * dt
        s.y += math.sin(s.angle) * s.speed * dt

        # RPM / gear (косметика)
        ratio = s.speed / (c.max_speed + 1e-6)
        thresholds = [0.0, 0.18, 0.36, 0.55, 0.74, 0.90]
        s.gear = 1
        for g, thr in enumerate(thresholds):
            if ratio >= thr:
                s.gear = g + 1
        s.rpm = int(900 + ratio * 7100)

    @staticmethod
    def check_collision(s1: CarPhysicsState, s2: CarPhysicsState,
                        radius: float = 24.0) -> bool:
        dx = s1.x - s2.x
        dy = s1.y - s2.y
        return dx * dx + dy * dy < radius * radius

    @staticmethod
    def resolve_collision(s1: CarPhysicsState, s2: CarPhysicsState):
        dx = s1.x - s2.x
        dy = s1.y - s2.y
        dist = math.hypot(dx, dy) + 1e-6
        nx, ny = dx / dist, dy / dist

        v1n = s1.speed * (math.cos(s1.angle) * nx + math.sin(s1.angle) * ny)
        v2n = s2.speed * (math.cos(s2.angle) * nx + math.sin(s2.angle) * ny)

        bounce = abs(v1n - v2n) * 0.4
        s1.speed = max(0.0, s1.speed - bounce)
        s2.speed = max(0.0, s2.speed - bounce)

        overlap = 24.0 - dist
        if overlap > 0:
            s1.x += nx * overlap * 0.55
            s1.y += ny * overlap * 0.55
            s2.x -= nx * overlap * 0.55
            s2.y -= ny * overlap * 0.55
