"""
Asset Manager — менеджер ресурсов.
Ленивая загрузка, кэширование, процедурная генерация если файл не найден.
"""

import pygame
import os
import math
from typing import Optional


ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets")


class AssetManager:
    def __init__(self):
        self._images: dict[str, pygame.Surface] = {}
        self._sounds: dict[str, Optional[pygame.mixer.Sound]] = {}
        self._fonts:  dict[tuple, pygame.font.Font] = {}

    # ── Images ──────────────────────────────────────────────────────────
    def get_image(self, name: str) -> pygame.Surface:
        if name not in self._images:
            path = os.path.join(ASSET_DIR, "images", name)
            if os.path.exists(path):
                self._images[name] = pygame.image.load(path).convert_alpha()
            else:
                self._images[name] = self._generate_image(name)
        return self._images[name]

    def _generate_image(self, name: str) -> pygame.Surface:
        """Процедурная генерация спрайтов если файл отсутствует."""
        if "car" in name:
            return self._gen_car(name)
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.rect(surf, (180, 180, 180), (0, 0, 32, 32), border_radius=4)
        return surf

    def _gen_car(self, name: str) -> pygame.Surface:
        color_map = {
            "car_red":    (220,  60,  60),
            "car_blue":   ( 60, 160, 220),
            "car_yellow": (230, 200,  40),
            "car_green":  ( 60, 200,  80),
            "car_purple": (180,  60, 220),
        }
        color = color_map.get(name, (200, 200, 200))
        w, h = 40, 22
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Кузов
        pygame.draw.rect(surf, color,        (2, 3, w-4, h-6), border_radius=5)
        # Кабина
        pygame.draw.rect(surf, (30, 30, 50), (10, 5, 16, h-10), border_radius=3)
        # Колёса
        wheel_color = (30, 30, 30)
        for wx, wy in [(4, 1), (4, h-5), (w-12, 1), (w-12, h-5)]:
            pygame.draw.rect(surf, wheel_color, (wx, wy, 10, 4), border_radius=2)
        # Фары
        pygame.draw.rect(surf, (255, 240, 180), (w-5, 5,  3, 4))
        pygame.draw.rect(surf, (255, 240, 180), (w-5, h-9, 3, 4))
        return surf

    # ── Sounds ──────────────────────────────────────────────────────────
    def get_sound(self, name: str) -> Optional[pygame.mixer.Sound]:
        if name not in self._sounds:
            path = os.path.join(ASSET_DIR, "sounds", name)
            if os.path.exists(path):
                try:
                    self._sounds[name] = pygame.mixer.Sound(path)
                except Exception:
                    self._sounds[name] = None
            else:
                self._sounds[name] = self._gen_sound(name)
        return self._sounds[name]

    def _gen_sound(self, name: str) -> Optional[pygame.mixer.Sound]:
        """Процедурная генерация звука через синтез."""
        try:
            import numpy as np
            sr = 44100
            if "engine" in name:
                t = np.linspace(0, 0.1, int(sr * 0.1), False)
                freq = 80
                wave = (np.sin(2 * np.pi * freq * t) * 0.3 +
                        np.sin(2 * np.pi * freq * 2 * t) * 0.2 +
                        np.sin(2 * np.pi * freq * 3 * t) * 0.1)
                wave = (wave * 32767).astype(np.int16)
                stereo = np.column_stack([wave, wave])
                return pygame.sndarray.make_sound(stereo)
            elif "drift" in name:
                t = np.linspace(0, 0.3, int(sr * 0.3), False)
                noise = np.random.uniform(-0.4, 0.4, len(t))
                env = np.exp(-t * 3)
                wave = (noise * env * 32767).astype(np.int16)
                stereo = np.column_stack([wave, wave])
                return pygame.sndarray.make_sound(stereo)
            elif "nitro" in name:
                t = np.linspace(0, 0.5, int(sr * 0.5), False)
                wave = (np.sin(2 * np.pi * 200 * t) * np.exp(-t * 2) * 32767).astype(np.int16)
                stereo = np.column_stack([wave, wave])
                return pygame.sndarray.make_sound(stereo)
        except ImportError:
            pass
        return None

    # ── Fonts ────────────────────────────────────────────────────────────
    def get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont("monospace", size, bold=bold)
        return self._fonts[key]
