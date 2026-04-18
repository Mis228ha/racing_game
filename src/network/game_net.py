"""
Локальная сеть — простой UDP host/client для LAN-гонок.
Host: отправляет состояние игры, принимает инпут клиента.
Client: отправляет инпут, принимает состояние.
"""

import socket
import json
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional


PORT = 54321
TIMEOUT = 0.016  # 60fps


@dataclass
class CarState:
    car_id: str
    x: float; y: float
    angle: float; speed: float
    lap: int; progress: float
    nitro: float; on_track: bool


@dataclass
class InputState:
    throttle: float; brake: float
    steer: float; nitro: bool


class GameHost:
    """Хост — запускает сервер, принимает инпут клиента."""

    def __init__(self):
        self.client_input: InputState = InputState(0, 0, 0, False)
        self._sock: Optional[socket.socket] = None
        self._client_addr = None
        self._running = False
        self._lock = threading.Lock()

    def start(self, port: int = PORT):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", port))
        self._sock.settimeout(TIMEOUT)
        self._running = True
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()
        return self._get_local_ip()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]; s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(256)
                self._client_addr = addr
                inp = json.loads(data.decode())
                with self._lock:
                    self.client_input = InputState(**inp)
            except socket.timeout:
                pass
            except Exception:
                pass

    def send_state(self, states: list[dict]):
        if self._client_addr and self._sock:
            try:
                raw = json.dumps(states).encode()
                self._sock.sendto(raw, self._client_addr)
            except Exception:
                pass

    def get_client_input(self) -> InputState:
        with self._lock:
            return self.client_input

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()

    @property
    def has_client(self) -> bool:
        return self._client_addr is not None


class GameClient:
    """Клиент — подключается к хосту, отправляет инпут, принимает стейт."""

    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._host_addr = None
        self._running = False
        self._lock = threading.Lock()
        self.game_states: list[dict] = []
        self.connected = False

    def connect(self, host_ip: str, port: int = PORT) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(TIMEOUT)
            self._host_addr = (host_ip, port)
            # Отправить ping
            self._sock.sendto(b'{"throttle":0,"brake":0,"steer":0,"nitro":false}',
                              self._host_addr)
            self._running = True
            self.connected = True
            t = threading.Thread(target=self._recv_loop, daemon=True)
            t.start()
            return True
        except Exception:
            return False

    def _recv_loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(4096)
                states = json.loads(data.decode())
                with self._lock:
                    self.game_states = states
            except socket.timeout:
                pass
            except Exception:
                pass

    def send_input(self, inp: InputState):
        if self._sock and self._host_addr:
            try:
                raw = json.dumps(asdict(inp)).encode()
                self._sock.sendto(raw, self._host_addr)
            except Exception:
                pass

    def get_states(self) -> list[dict]:
        with self._lock:
            return list(self.game_states)

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()
