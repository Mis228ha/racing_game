"""
NetworkLobby — простое понятное LAN-лобби.
HOST: показывает свой IP, ждёт подключения клиента.
JOIN: вводит IP хоста и подключается.
Оба игрока видят ботов. У каждого — своя камера за своей машиной.
HOST управляет P1 (WASD), CLIENT управляет P2 (тоже WASD).
"""

import math
import socket
import pygame
from src.engine.game_state import BaseState


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class NetworkLobbyState(BaseState):
    def __init__(self, screen, event_bus, assets,
                 role: str = "host", map_id: int = 0, **kwargs):
        super().__init__(screen, event_bus, assets)
        self.role    = role
        self.map_id  = map_id
        self._time   = 0.0
        self._status = ""
        self._sub    = ""
        self._ip_input = ""
        self._net    = None
        self._error  = ""
        self._ready  = False
        self._local_ip = _get_local_ip()

    def on_enter(self):
        if self.role == "host":
            self._start_host()
        else:
            self._status = "Введите IP-адрес хоста"
            self._sub    = "Нажмите ENTER для подключения"

    def _start_host(self):
        try:
            from src.network.game_net import GameHost
            self._net = GameHost()
            self._net.start()
            self._status = f"Ваш IP-адрес:"
            self._sub    = self._local_ip
            self._error  = ""
        except Exception as e:
            self._error = f"Ошибка: {e}"

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._net: self._net.stop()
                self.manager.replace("menu")

            elif self.role == "join":
                if event.key == pygame.K_BACKSPACE:
                    self._ip_input = self._ip_input[:-1]
                elif event.key == pygame.K_RETURN:
                    self._try_connect()
                elif event.unicode and (event.unicode.isdigit() or event.unicode == "."):
                    if len(self._ip_input) < 15:
                        self._ip_input += event.unicode

            elif self.role == "host":
                if event.key == pygame.K_RETURN and self._ready:
                    self._launch_host()

    def _try_connect(self):
        ip = self._ip_input.strip()
        if not ip:
            self._error = "Введите IP-адрес!"
            return
        try:
            from src.network.game_net import GameClient
            client = GameClient()
            if client.connect(ip):
                self._net  = client
                self._status = "Подключено!"
                self._sub    = f"Сервер: {ip}"
                self._ready  = True
                self._error  = ""
                # Сразу запускаем (клиент — P2)
                self.manager.replace("race", map_id=self.map_id,
                                     two_player=True, num_bots=3,
                                     net_client=self._net)
            else:
                self._error = f"Не удалось подключиться к {ip}"
        except Exception as e:
            self._error = str(e)

    def _launch_host(self):
        # Хост — P1, клиент получает управление P2
        self.manager.replace("race", map_id=self.map_id,
                             two_player=True, num_bots=3,
                             net_host=self._net)

    def update(self, dt: float):
        self._time += dt
        if self.role == "host" and self._net:
            try:
                if self._net.has_client and not self._ready:
                    self._ready  = True
                    self._status = "Игрок подключился!"
                    self._sub    = "Нажмите ENTER — начать гонку"
            except Exception:
                pass

    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill((8, 8, 18))
        t = self._time
        # Фон
        for i in range(0, w+60, 60):
            x = i+math.sin(t*0.3+i*0.01)*4
            pygame.draw.line(self.screen,(16,16,28),(int(x),0),(int(x),h))
        for j in range(0, h+60, 60):
            y = j+math.sin(t*0.3+j*0.01)*4
            pygame.draw.line(self.screen,(16,16,28),(0,int(y)),(w,int(y)))

        # Заголовок
        ft = self.assets.get_font(44, bold=True)
        gv = int(160+70*math.sin(t*2))
        icon = "📡 ХОСТ" if self.role=="host" else "🔌 ПОДКЛЮЧЕНИЕ"
        icon = "HOST" if self.role=="host" else "JOIN"
        ts = ft.render(f"СЕТЬ — {icon}", True, (gv, 50, 50))
        self.screen.blit(ts, (w//2-ts.get_width()//2, 55))

        # Инструкция
        cy = h//2 - 80
        fm = self.assets.get_font(22, bold=True)
        sm = self.assets.get_font(18)
        sh = self.assets.get_font(15)

        if self.role == "host":
            # Показываем IP
            box_w, box_h = 420, 100
            bx = w//2 - box_w//2
            pygame.draw.rect(self.screen,(18,18,38),(bx, cy, box_w, box_h),border_radius=12)
            pygame.draw.rect(self.screen,(80,80,140),(bx, cy, box_w, box_h),2,border_radius=12)

            ls = sm.render(self._status, True, (160,160,200))
            self.screen.blit(ls, (w//2-ls.get_width()//2, cy+14))
            ip_s = fm.render(self._sub, True, (80,200,255))
            self.screen.blit(ip_s, (w//2-ip_s.get_width()//2, cy+46))

            # Статус подключения
            if self._ready:
                rs = fm.render("✓ Игрок подключён — ENTER чтобы начать", True, (80,230,100))
                self.screen.blit(rs, (w//2-rs.get_width()//2, cy+120))
            else:
                # Анимация ожидания
                dots = "." * (int(t*2)%4)
                ws = sh.render(f"Ожидание игрока{dots}", True, (100,100,140))
                self.screen.blit(ws, (w//2-ws.get_width()//2, cy+120))

            # Кто за кого играет
            hint1 = sh.render("ВЫ играете за  P1  (WASD + LSHIFT)", True, (200,160,80))
            hint2 = sh.render("Клиент играет за  P2", True, (80,160,200))
            self.screen.blit(hint1, (w//2-hint1.get_width()//2, cy+175))
            self.screen.blit(hint2, (w//2-hint2.get_width()//2, cy+200))

        else:
            # JOIN — поле ввода IP
            label = sh.render("IP-адрес хоста:", True, (140,140,180))
            self.screen.blit(label, (w//2-label.get_width()//2, cy))

            box_w, box_h = 360, 56
            bx = w//2 - box_w//2
            pygame.draw.rect(self.screen,(22,22,44),(bx,cy+30,box_w,box_h),border_radius=8)
            pygame.draw.rect(self.screen,(80,80,140),(bx,cy+30,box_w,box_h),2,border_radius=8)
            cursor = "|" if int(t*2)%2==0 else " "
            tip = fm.render(self._ip_input + cursor, True, (220,220,255))
            self.screen.blit(tip, (bx+14, cy+44))

            ent = sh.render("ENTER — подключиться", True, (80,80,120))
            self.screen.blit(ent, (w//2-ent.get_width()//2, cy+100))

            hint1 = sh.render("ВЫ играете за  P2  (WASD + LSHIFT)", True, (80,160,200))
            self.screen.blit(hint1, (w//2-hint1.get_width()//2, cy+140))

        # Ошибка
        if self._error:
            es = self.assets.get_font(15).render(self._error, True, (220,60,60))
            self.screen.blit(es, (w//2-es.get_width()//2, h-80))

        # Нижняя подсказка
        esc = self.assets.get_font(14).render("ESC — назад в меню", True, (45,45,70))
        self.screen.blit(esc, (w//2-esc.get_width()//2, h-40))
