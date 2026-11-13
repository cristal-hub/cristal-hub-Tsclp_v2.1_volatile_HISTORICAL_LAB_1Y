# historical_lab/tests/conftest.py
# Tsclp_v2.1_volatile — ЭТАП C. Общие фикстуры тестов.

import sys
from pathlib import Path

# Гарантируем, что historical_lab импортируется как пакет из корня.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))