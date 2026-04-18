"""
Game State Machine — машина состояний.
Состояния: Menu → MapSelect → [NetworkLobby →] Race → Pause → Finish
"""

import pygame
from typing import Optional


class BaseState:
    def __init__(self, screen, event_bus, assets):
        self.screen    = screen
        self.event_bus = event_bus
        self.assets    = assets
        self.manager: Optional["GameStateManager"] = None

    def on_enter(self): pass
    def on_exit(self):  pass
    def handle_event(self, event): pass
    def update(self, dt: float):   pass
    def draw(self):                pass


class GameStateManager:
    def __init__(self, screen, event_bus, assets):
        self.screen    = screen
        self.event_bus = event_bus
        self.assets    = assets
        self._stack: list[BaseState] = []
        self._states: dict[str, type] = {}
        self._register_states()

    def _register_states(self):
        from src.ui.menu          import MenuState
        from src.ui.hud           import RaceState
        from src.ui.map_select    import MapSelectState
        from src.ui.network_lobby import NetworkLobbyState
        self._states["menu"]          = MenuState
        self._states["race"]          = RaceState
        self._states["map_select"]    = MapSelectState
        self._states["network_lobby"] = NetworkLobbyState

    def push(self, name: str, **kwargs):
        StateClass = self._states[name]
        state = StateClass(self.screen, self.event_bus, self.assets, **kwargs)
        state.manager = self
        if self._stack:
            self._stack[-1].on_exit()
        self._stack.append(state)
        state.on_enter()

    def pop(self):
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        if self._stack:
            self._stack[-1].on_enter()

    def replace(self, name: str, **kwargs):
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        self.push(name, **kwargs)

    def handle_event(self, event):
        if self._stack:
            self._stack[-1].handle_event(event)

    def update(self, dt: float):
        self.event_bus.flush()
        if self._stack:
            self._stack[-1].update(dt)

    def draw(self):
        if self._stack:
            self._stack[-1].draw()
