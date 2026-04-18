# DRIFT KINGS 🏎️

Racing game — Python MVP по архитектуре из промта.

## Стек
- Python 3.10+
- Pygame 2.5+
- NumPy (для процедурного звука)

## Установка

```bash
pip install -r requirements.txt
python main.py
```

## Управление
| Клавиша | Действие |
|---------|----------|
| W / ↑ | Газ |
| S / ↓ | Тормоз |
| A / ← | Влево |
| D / → | Вправо |
| SHIFT | Nitro boost |
| SPACE | Ручной тормоз |
| ESC | Меню |
| R | Рестарт (на финише) |
| F11 | Полный экран |

## Архитектура

```
drift_kings/
├── main.py                     # Точка входа
├── src/
│   ├── engine/
│   │   ├── event_bus.py        # Шина событий (ON_COLLISION, ON_LAP...)
│   │   ├── physics.py          # Физика: Slip Angle, Weight Transfer, Drift
│   │   ├── asset_manager.py    # Ленивая загрузка + процедурная генерация
│   │   └── game_state.py       # State Machine: Menu → Race → Finish
│   ├── game_objects/
│   │   ├── car.py              # Автомобиль + частицы + VFX
│   │   └── track.py            # Процедурная трасса + Surface Map
│   ├── ai/
│   │   └── ai_car.py           # AI: Aggressive/Careful/Balanced + ошибки
│   └── ui/
│       ├── hud.py              # RaceState + HUD + камера + мини-карта
│       └── menu.py             # Главное меню
```

## Реализовано (MVP)

### Физика
- Bicycle model (велосипедная модель) — Slip Angle, Weight Transfer
- Torque Curve (кривая момента)
- Температура шин — оптимум 90-110°C
- Износ шин
- Нитро-буст с расходом
- Fixed timestep 60Hz

### AI (4 бота)
- 3 типа поведения: Aggressive / Careful / Balanced
- Racing line + look-ahead
- Система ошибок 1-3% (human factor)
- Психология: страх при близости к другим машинам

### VFX
- Частицы дрифта (дым/грязь)
- Нитро-свечение
- Screen shake при столкновениях
- Скид-марки
- Тени машин

### Трасса
- Процедурная генерация (Catmull-Rom сплайн)
- Разные типы покрытия: asphalt (1.0), dirt (0.5), grass (0.35)
- Surface Map влияет на сцепление

### UI / HUD
- Скорость, RPM, передача, лап, позиция, время, нитро, температура шин
- Мини-карта с позициями всех машин
- Камера с lag-эффектом
- Countdown 3-2-1-GO!
- Экран финиша с позицией и временем

### Event Bus
Системы не связаны напрямую — общаются через события:
- ON_COLLISION → shake + уведомление
- ON_LAP_COMPLETE → сообщение на экране
- ON_RACE_FINISH → финишный экран
- ON_DRIFT_START/END → VFX
- ON_NITRO_ACTIVATED → эффекты

## Следующие шаги
- Звук (granular engine + Doppler)
- Сеть (UDP Gaffer)
- OpenGL шейдеры (motion blur, heat distortion)
- Leaderboard / ELO
- Кастомизация машин
- Погода
