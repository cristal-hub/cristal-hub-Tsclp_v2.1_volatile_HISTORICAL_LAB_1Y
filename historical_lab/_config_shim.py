# historical_lab/_config_shim.py
# Tsclp_v2.1_volatile — ЭТАП C. Заглушка config для лаборатории.
#
# strategy.py импортирует config. В лаборатории config.py тянет dotenv/.env.
# Эта заглушка подменяет config в sys.modules ДО импорта strategy.
# Все числовые константы — из config_lab (SHA256 d4ce8d21...).
#
# STRATEGY LOGIC: UNCHANGED.

import sys
import types

from . import config_lab as C


def install():
    """Подменяет config в sys.modules заглушкой с числовыми константами."""
    shim = types.ModuleType("config")
    # Копируем ВСЕ числовые/строковые константы из config_lab.
    for name in dir(C):
        if name.isupper():
            setattr(shim, name, getattr(C, name))
    # validate() — заглушка (в лаборатории не нужна).
    shim.validate = lambda: None
    sys.modules["config"] = shim