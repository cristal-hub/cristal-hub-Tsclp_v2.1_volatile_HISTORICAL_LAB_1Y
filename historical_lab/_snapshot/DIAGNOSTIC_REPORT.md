# DIAGNOSTIC REPORT — ЭТАП A

**Сгенерирован:** 2026-11-10T16:10:33.932858+00:00
**Источник (только чтение):** `C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile`
**Лаборатория (запись):** `C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y`

## SHA256 исходных файлов

| Файл | SHA256 |
|---|---|
| `config.py` | `d4ce8d21146aa00ac03de469f54f5ee01995f674f1d2415cadda5943781fad18` |
| `strategy.py` | `43906866a226aabae0fff266dde77d88345ae27f87b0948689929aa37171537f` |
| `risk_manager.py` | `6e3206cb8a1b735313708b3a84227272fb208a5d16ea5beaa7d4ba0ad12eacca` |
| `screener.py` | `abd710dd1f6f424d883c8ac655837a221cef6780ea2e064c37e979eba8bf0058` |
| `main.py` | `38f71e1e003cc94d17995fdc383b2ea33c9b0154377b8b6a93c7d9d9819f294d` |
| `logger.py` | `3b2e5b00afbf18f0d38ae183e3559891eb39333b9c1a80669e7858eca7eb83c5` |
| `execution.py` | `126ecd51fb203b159420a948eeabe69ece6ab82d6ef7d2802ff390340ef0d29f` |
| `tinkoff_client.py` | `b29383338663e2cb63b9af8803524c4a697dad879fddb661e438ae53c70bbdfc` |
| `requirements.txt` | `636df79532095437a0f13903280ee3141377b09e1b6ad37002fa33716d200cd0` |

## config.py — верхнеуровневые параметры

```
TINKOFF_API_TOKEN = os.getenv("TINKOFF_API_TOKEN")
TINKOFF_READONLY_TOKEN = os.getenv("TINKOFF_READONLY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TINKOFF_ACCOUNT_ID = os.getenv("TINKOFF_ACCOUNT_ID")
TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
USE_SANDBOX = True
ENABLE_TELEGRAM = True
TOP_VOLATILE_INSTRUMENTS_COUNT = 10
VOLATILITY_PERIOD_DAYS = 30
VOLATILITY_REFRESH_HOURS = 24
MIN_DAILY_TURNOVER_RUB = 10_000_000
RISK_PER_TRADE = 0.01
MIN_STOP_LOSS_PERCENT = 0.005
STOP_LOSS_PERCENT = 0.012
TAKE_PROFIT_RATIO = 2.0
ATR_STOP_MULTIPLIER = 1.5
ATR_PERIOD_INTRADAY = 20
ATR_PERIOD = 14
MAX_ATR_STOP_PERCENT = 0.03
MAX_POSITION_SHARE_PER_INSTRUMENT = 0.2
MAX_TOTAL_EXPOSURE = 0.6
MAX_TRADES_PER_INSTRUMENT_PER_DAY = 5
POSITION_QUANTITY_IS_LOTS = True
COMMISSION_MODE = "TRADER"
COMMISSION_PER_SIDE = 0.003 if COMMISSION_MODE == "INVESTOR" else 0.0005
SLIPPAGE_PERCENT = 0.0002
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
PROFILE = "CONSERVATIVE"
VOLUME_CONFIRMATION_WINDOW = 20
API_RETRY_COUNT = 3
API_RETRY_DELAY_SECONDS = 5
API_REQUEST_TIMEOUT_SECONDS = 10
API_CALL_DELAY_SECONDS = 0.03
TRADING_CYCLE_SECONDS = 30
CANDLES_LOOKBACK_DAYS = 2
STARTING_BALANCE = os.getenv("STARTING_BALANCE")
```

## strategy.py — сигнатуры и классы

**Классы:** StrategyManager

| Тип | Имя | Аргументы |
|---|---|---|

**Импорты:**
```
import logging
from typing import Optional, Tuple
import pandas as pd
import pandas_ta_classic as ta
import config
```

## risk_manager.py — сигнатуры

| Тип | Имя | Аргументы |
|---|---|---|

## screener.py — сигнатуры и проверки

| Тип | Имя | Аргументы |
|---|---|---|

**Проверки:**
```json
{
  "REAL_EXCHANGE_MOEX": true,
  "uses_INSTRUMENT_STATUS_ALL": true,
  "volatility_formula_present": true,
  "atr_period_used": true,
  "min_turnover_used": true,
  "volatility_period_days_used": true
}
```

## main.py — сигнатуры и проверки

| Тип | Имя | Аргументы |
|---|---|---|
| sync | `is_trading_enabled` | `` |
| sync | `start_trading` | `` |
| sync | `stop_trading` | `` |
| sync | `get_status` | `` |
| async | `notify` | `text: str` |
| async | `_stop_telegram_bot` | `` |
| async | `_try_create_telegram_bot` | `` |
| async | `_telegram_watchdog` | `` |
| sync | `_trade_id_already_logged` | `trade_id: str` |
| sync | `_timestamp_for_log` | `value` |
| sync | `_log_strategy_diagnostic` | `event_type: str, ticker: str, figi: str, signal: str, reason: str, sm: StrategyManager, df: pd.DataFrame, price: float,` |
| async | `reconcile` | `client: TinkoffClient, monitor: ExecutionMonitor` |
| async | `close_position` | `client: TinkoffClient, pos, price: float` |
| async | `process_closing` | `client: TinkoffClient, monitor: ExecutionMonitor` |
| async | `trading_cycle` | `client: TinkoffClient, rm: RiskManager, sm: StrategyManager, monitor: ExecutionMonitor` |
| async | `main` | `` |

### Проверка ADX-гистерезиса (потенциальная утечка)

```json
{
  "instantiations_count": 1,
  "instantiations": [
    "ent:         main_client = client         rm = RiskManager(client)         sm = StrategyManager()         monitor = E"
  ],
  "stateful_fields_in_strategy": [
    "_last_regime",
    "_regime_streak",
    "_last_regime_candidate",
    "_last_regime_candle_time"
  ],
  "risk": "WARNING: StrategyManager создаётся один раз (или несколько), но _last_regime / _regime_streak — атрибуты экземпляра. Если экземпляр ОДИН на все инструменты, ADX-гистерезис перетекает между тикерами. Это воспроизводить как есть (STRATEGY LOGIC: UNCHANGED), но задокументировать."
}
```

### Проверка drop_incomplete

```json
{
  "values_found": [
    "True"
  ]
}
```

### Проверка CANDLES_LOOKBACK_DAYS

```json
{
  "uses_in_main": 1,
  "config_value": "2"
}
```

## logger.py — TRADE_FIELDS

```
trade_id, timestamp_utc, ticker, figi, lot_size, side, signal_reason, signal_time, price_before_order, order_send_time, order_id, execution_status, requested_lots, executed_lots, execution_price, exit_reason, exit_price, exit_time, commission_rub, commission_source, actual_commission_rub, entry_commission_rub, exit_commission_rub, slippage_rub, slippage_percent, gross_pnl_rub, net_pnl_rub, cumulative_net_pnl_rub, error_note
```

## execution.py — PositionState

```
CLOSING = CLOSING
CLOSED = CLOSED
UNCERTAIN = UNCERTAIN
```

### TrackedPosition — поля

| Поле | Тип | По умолчанию |
|---|---|---|
| `figi` | `str` | `` |
| `ticker` | `str` | `` |
| `direction` | `str` | `` |
| `entry_price` | `float` | `` |
| `quantity` | `int` | `` |
| `sl_price` | `float` | `` |
| `tp_price` | `float` | `` |
| `lot_size` | `int` | `1` |
| `state` | `PositionState` | `PositionState.OPEN` |
| `close_reason` | `Optional[str]` | `None` |
| `close_order_id` | `Optional[str]` | `None` |
| `close_requested_at` | `Optional[str]` | `None` |
| `close_price_before_order` | `float` | `0.0` |
| `executed_lots` | `int` | `0` |
| `execution_price` | `Optional[float]` | `None` |
| `trade_id` | `str` | `""` |
| `signal_reason` | `str` | `""` |
| `signal_time` | `str` | `""` |
| `price_before_order` | `float` | `0.0` |
| `order_send_time` | `str` | `""` |
| `partial` | `bool` | `False` |
| `logged` | `bool` | `False` |
| `actual_commission` | `Optional[float]` | `None` |
| `entry_actual_commission` | `Optional[float]` | `None` |
| `entry_order_id` | `Optional[str]` | `None  # ID исходной заявки на покупку` |

## tinkoff_client.py — сигнатуры

| Тип | Имя | Аргументы |
|---|---|---|

## requirements.txt

```
t-tech-investments==1.51.0
pandas>=2.0
pandas-ta-classic>=0.3.14b
python-telegram-bot>=20.0,<22.0
python-dotenv>=1.0
pytest>=7.0
pytest-asyncio>=0.23
```
