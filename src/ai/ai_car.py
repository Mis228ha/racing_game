"""
AI — умные боты.
Предсмотрительное торможение на поворотах, возврат на трассу,
объезд других машин, оптимальная траектория.
"""

import math
import random
from enum import Enum
from dataclasses import dataclass

from src.game_objects.car import Car
from src.game_objects.track import Track


class AIType(Enum):
    AGGRESSIVE = "aggressive"
    CAREFUL    = "careful"
    BALANCED   = "balanced"


class AIController:
    # Дальность взгляда вперёд (в точках трека)
    LOOKAHEAD  = {"aggressive": 14, "careful": 22, "balanced": 18}
    # Базовый газ
    MAX_THROT  = {"aggressive": 0.97, "careful": 0.85, "balanced": 0.92}
    # Вероятность случайной ошибки
    ERR_PROB   = {"aggressive": 0.018, "careful": 0.005, "balanced": 0.010}

    def __init__(self, car: Car, track: Track, ai_type: AIType = AIType.BALANCED):
        self.car   = car
        self.track = track
        self.tname = ai_type.value
        self._err_active = False
        self._err_timer  = 0.0
        self._err_dir    = 0.0
        self._nitro_cd   = random.uniform(0, 3.0)
        self._stuck_timer = 0.0
        self._last_pos    = (car.state.x, car.state.y)
        self._stuck_cd    = 0.0

    def update(self, dt: float, others: list):
        s   = self.car.state
        trk = self.track
        tname = self.tname

        # ── Проверка застревания ─────────────────────────────────────────
        dx = s.x - self._last_pos[0]; dy = s.y - self._last_pos[1]
        moved = math.hypot(dx, dy)
        if moved < 2.0:
            self._stuck_timer += dt
        else:
            self._stuck_timer = 0.0
        self._last_pos = (s.x, s.y)

        if self._stuck_timer > 1.8 and self._stuck_cd <= 0:
            # Дать задний ход, потом рулить
            self.car.apply_input(0.0, 1.0, random.choice([-1.0, 1.0]), False)
            self._stuck_cd = 1.2
            return

        self._stuck_cd   = max(0.0, self._stuck_cd - dt)

        # ── Случайная ошибка ─────────────────────────────────────────────
        self._err_timer -= dt
        if self._err_active and self._err_timer <= 0:
            self._err_active = False
        if not self._err_active and random.random() < self.ERR_PROB[tname] * dt:
            self._err_active = True
            self._err_timer  = random.uniform(0.6, 1.8)
            self._err_dir    = random.choice([-1, 1])

        # ── Базовый индекс на треке ──────────────────────────────────────
        idx = trk.nearest_point_index(s.x, s.y)

        # ── Если вне трека — приоритетный возврат ───────────────────────
        if not s.on_track:
            p   = trk.points[idx]
            tdx = p.x - s.x; tdy = p.y - s.y
            want = math.atan2(tdy, tdx)
            diff = self._angle_diff(want, s.angle)
            steer = max(-1.0, min(1.0, diff * 3.0))
            self.car.apply_input(0.65, 0.0, steer, False)
            return

        # ── Кривизна впереди → скорость торможения ──────────────────────
        la        = self.LOOKAHEAD[tname]
        curvature = trk.get_curvature(idx, window=la // 2)

        # Точка прицела — чуть внутри поворота (гоночная линия)
        tidx = (idx + la) % trk.get_total_points()
        tp   = trk.points[tidx]
        tidy2 = (idx + la // 2) % trk.get_total_points()
        tp2  = trk.points[tidy2]
        # Среднее между дальней и средней точкой для плавности
        target_x = tp.x * 0.55 + tp2.x * 0.45
        target_y = tp.y * 0.55 + tp2.y * 0.45

        diff  = self._angle_diff(math.atan2(target_y - s.y, target_x - s.x), s.angle)

        if self._err_active:
            diff += self._err_dir * 0.28

        steer    = max(-1.0, min(1.0, diff * 2.8))
        throttle = self.MAX_THROT[tname]

        # Снижение скорости на поворотах
        brake = 0.0
        if curvature > 0.25:
            brake_amount = (curvature - 0.25) * 1.6
            brake = min(0.7, brake_amount)
            throttle = max(0.25, throttle - brake)
        # Снижение от угла рулежки
        if abs(diff) > 0.45:
            throttle = max(0.3, throttle - abs(diff) * 0.35)

        # ── Объезд других машин ─────────────────────────────────────────
        steer_avoidance = 0.0
        for other in others:
            if other.car_id == self.car.car_id:
                continue
            odx = other.state.x - s.x; ody = other.state.y - s.y
            odist = math.hypot(odx, ody)
            if odist < 70 and odist > 1:
                # Боковое смещение к другой машине
                perp_angle = s.angle + math.pi / 2
                side = math.cos(perp_angle) * odx + math.sin(perp_angle) * ody
                if abs(side) < 50:
                    avoid_str = (70 - odist) / 70 * 0.8
                    steer_avoidance -= math.copysign(avoid_str, side)
        steer = max(-1.0, min(1.0, steer + steer_avoidance))

        # ── Нитро — на прямых ───────────────────────────────────────────
        self._nitro_cd -= dt
        use_nitro = (s.nitro > 0.35 and abs(diff) < 0.12
                     and curvature < 0.2
                     and self._nitro_cd <= 0
                     and random.random() < 0.008)
        if use_nitro:
            self._nitro_cd = 5.0

        self.car.apply_input(throttle, brake, steer, use_nitro)

    @staticmethod
    def _angle_diff(want: float, have: float) -> float:
        d = want - have
        while d >  math.pi: d -= 2 * math.pi
        while d < -math.pi: d += 2 * math.pi
        return d


class AIManager:
    TYPES = [AIType.BALANCED, AIType.AGGRESSIVE, AIType.CAREFUL,
             AIType.AGGRESSIVE, AIType.BALANCED]

    def __init__(self, track: Track):
        self.track = track
        self.controllers: list[AIController] = []

    def add_car(self, car: Car, index: int = 0):
        t = self.TYPES[index % len(self.TYPES)]
        self.controllers.append(AIController(car, self.track, t))

    def update(self, dt: float, all_cars: list):
        for ctrl in self.controllers:
            ctrl.update(dt, all_cars)

    def clear(self):
        self.controllers.clear()
