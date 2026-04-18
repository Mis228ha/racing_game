"""
Event Bus — шина событий.
Системы общаются через события, не напрямую.
Примеры: ON_COLLISION, ON_LAP_COMPLETE, ON_NITRO_ACTIVATED
"""

from collections import defaultdict
from typing import Callable, Any


class EventBus:
    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._queue: list[tuple[str, dict]] = []

    def subscribe(self, event: str, callback: Callable):
        self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        if callback in self._listeners[event]:
            self._listeners[event].remove(callback)

    def emit(self, event: str, data: dict = None):
        """Немедленная отправка события."""
        if data is None:
            data = {}
        for cb in self._listeners.get(event, []):
            cb(data)

    def post(self, event: str, data: dict = None):
        """Отложенная отправка (в конце кадра)."""
        self._queue.append((event, data or {}))

    def flush(self):
        """Обработать отложенные события."""
        for event, data in self._queue:
            self.emit(event, data)
        self._queue.clear()


# Константы событий
class Events:
    ON_COLLISION       = "ON_COLLISION"
    ON_LAP_COMPLETE    = "ON_LAP_COMPLETE"
    ON_RACE_START      = "ON_RACE_START"
    ON_RACE_FINISH     = "ON_RACE_FINISH"
    ON_NITRO_ACTIVATED = "ON_NITRO_ACTIVATED"
    ON_DRIFT_START     = "ON_DRIFT_START"
    ON_DRIFT_END       = "ON_DRIFT_END"
    ON_SURFACE_CHANGE  = "ON_SURFACE_CHANGE"
    ON_CAR_DAMAGED     = "ON_CAR_DAMAGED"
    ON_CHECKPOINT      = "ON_CHECKPOINT"
