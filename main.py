"""
DRIFT KINGS — Racing Game
Main entry point
Stack: Python 3.12 + Pygame (fallback без Arcade/Pymunk для запуска без GPU)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.engine.game_state import GameStateManager
from src.engine.event_bus import EventBus
from src.engine.asset_manager import AssetManager
import pygame

def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption("DRIFT KINGS")
    clock = pygame.time.Clock()

    event_bus = EventBus()
    asset_manager = AssetManager()
    state_manager = GameStateManager(screen, event_bus, asset_manager)
    state_manager.push("menu")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 0.05)  # cap delta time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            state_manager.handle_event(event)

        state_manager.update(dt)
        state_manager.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
