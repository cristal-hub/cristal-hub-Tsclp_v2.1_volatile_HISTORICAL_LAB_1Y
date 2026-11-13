# historical_lab/config_lab.py
# Tsclp_v2.1_volatile — ЭТАП C. Константы лаборатории.
#
# ВАЖНО: НЕ импортирует config.py (чтобы не тянуть .env/токены).
# Копирует числовые параметры из config.py (SHA256 d4ce8d21...).
# STRATEGY LOGIC: UNCHANGED.
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

from pathlib import Path

# --- Пути ---
LAB_ROOT = Path(__file__).resolve().parent
DATA_DIR = LAB_ROOT / "data"
CANDLES_DIR = DATA_DIR / "candles"          # 5-мин свечи (parquet/CSV) — пользователь
DAILY_DIR = DATA_DIR / "daily"              # дневные свечи (parquet/CSV) — пользователь
INSTRUMENTS_FILE = DATA_DIR / "instruments.json"
TOP10_FILE = DATA_DIR / "top10_rolling.json"
OUTPUT_DIR = LAB_ROOT / "output"

# --- Капитал (Q5) ---
STARTING_BALANCE = 1_000_000.0

# --- Скрининг (Q3, B4, B13) ---
TOP_VOLATILE_INSTRUMENTS_COUNT = 10
VOLATILITY_PERIOD_DAYS = 30
MIN_DAILY_TURNOVER_RUB = 10_000_000
ATR_PERIOD_DAILY = 14

# --- Риск (из config.py) ---
RISK_PER_TRADE = 0.01
MIN_STOP_LOSS_PERCENT = 0.005
STOP_LOSS_PERCENT = 0.012
TAKE_PROFIT_RATIO = 2.0
ATR_STOP_MULTIPLIER = 1.5
ATR_PERIOD_INTRADAY = 20
MAX_ATR_STOP_PERCENT = 0.03
MAX_POSITION_SHARE_PER_INSTRUMENT = 0.2
MAX_TOTAL_EXPOSURE = 0.6
MAX_TRADES_PER_INSTRUMENT_PER_DAY = 5

# --- Комиссия и проскальзывание ---
COMMISSION_MODE = "TRADER"
COMMISSION_PER_SIDE = 0.003 if COMMISSION_MODE == "INVESTOR" else 0.0005
SLIPPAGE_PERCENT = 0.0002

# --- Стратегия (из config.py, CONSERVATIVE) ---
PROFILE = "CONSERVATIVE"
MA_FAST_PERIOD = 9
MA_SLOW_PERIOD = 21
TREND_FILTER_MA_PERIOD = 100
BB_PERIOD = 20
BB_STD_DEV = 2
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MIN_CANDLES_FOR_SIGNAL = 60
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25
ADX_HYSTERESIS_CANDLES = 2
VOLUME_SPIKE_FACTOR = 1.5
VOLUME_CONFIRMATION_WINDOW = 20

# --- Окно свечей (Q2) ---
CANDLES_LOOKBACK_DAYS = 2

# --- Периоды (Q4) ---
# Границы задаются в run_historical_lab.py (даты передаются аргументами).
DISCOVERY_MONTHS = 6
VALIDATION_MONTHS = 3
OOS_MONTHS = 3

# --- Стресс-сценарии издержек (B8) ---
STRESS_SCENARIOS = {
    "base": 0.0,
    "stress_0.10": 0.0010,
    "stress_0.20": 0.0020,
    "stress_0.40": 0.0040,
}