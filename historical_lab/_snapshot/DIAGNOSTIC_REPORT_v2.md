# DIAGNOSTIC REPORT v2 — ЭТАП A

**Сгенерирован:** 2026-11-10T16:15:17.422243+00:00
**Источник:** `C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile`
**Лаборатория:** `C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y`

## SHA256 и сверка с предыдущим отчётом

| Файл | SHA256 | Изменён? |
|---|---|---|
| `config.py` | `d4ce8d21146aa00ac03de469f54f5ee01995f674f1d2415cadda5943781fad18` | нет |
| `strategy.py` | `43906866a226aabae0fff266dde77d88345ae27f87b0948689929aa37171537f` | нет |
| `risk_manager.py` | `6e3206cb8a1b735313708b3a84227272fb208a5d16ea5beaa7d4ba0ad12eacca` | нет |
| `screener.py` | `abd710dd1f6f424d883c8ac655837a221cef6780ea2e064c37e979eba8bf0058` | нет |
| `main.py` | `38f71e1e003cc94d17995fdc383b2ea33c9b0154377b8b6a93c7d9d9819f294d` | нет |
| `logger.py` | `3b2e5b00afbf18f0d38ae183e3559891eb39333b9c1a80669e7858eca7eb83c5` | нет |
| `execution.py` | `126ecd51fb203b159420a948eeabe69ece6ab82d6ef7d2802ff390340ef0d29f` | нет |
| `tinkoff_client.py` | `b29383338663e2cb63b9af8803524c4a697dad879fddb661e438ae53c70bbdfc` | нет |
| `requirements.txt` | `636df79532095437a0f13903280ee3141377b09e1b6ad37002fa33716d200cd0` | нет |

## config.py — параметры

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

## strategy.py — сигнатуры (включая методы классов)

| Тип | Метод? | Имя | Аргументы |
|---|---|---|---|
| sync | да | `__init__` | `self` |
| sync | да | `get_market_regime` | `self, candles_df: pd.DataFrame` |
| sync | да | `get_signal` | `self, candles_df: pd.DataFrame, last_price: float, drop_incomplete: bool = False,` |
| sync | да | `_trend_filter_ok` | `self, candles_df: pd.DataFrame, signal: str,` |
| sync | да | `_ma_crossover_signal` | `self, candles_df: pd.DataFrame,` |
| sync | да | `_bb_rsi_signal` | `self, candles_df: pd.DataFrame,` |
| sync | да | `_prepare_dataframe` | `self, candles_df: pd.DataFrame, drop_incomplete: bool = False,` |
| sync | да | `_volume_confirmation` | `self, candles_df: pd.DataFrame,` |

## risk_manager.py — сигнатуры (включая методы классов)

| Тип | Метод? | Имя | Аргументы |
|---|---|---|---|
| sync | да | `__init__` | `self, tinkoff_client` |
| sync | да | `reset_daily_counts` | `self` |
| sync | да | `_maybe_reset_by_date` | `self` |
| async | да | `calculate_position_size` | `self, figi: str, last_price: float, candles_df: Optional[pd.DataFrame] = None` |
| sync | да | `_calculate_volatility_risk` | `self, candles_df: Optional[pd.DataFrame]` |
| sync | да | `calculate_sl_tp` | `self, entry_price: float, direction: str, candles_df: Optional[pd.DataFrame] = None` |
| sync | да | `record_trade` | `self, figi: str` |

## screener.py — сигнатуры (включая методы классов)

| Тип | Метод? | Имя | Аргументы |
|---|---|---|---|
| sync | да | `__init__` | `self` |
| sync | да | `_cache_valid` | `self` |
| async | да | `select_top_volatile` | `self, force: bool = False` |
| async | да | `_do_scan` | `self` |

## main.py — сигнатуры (включая методы классов)

| Тип | Метод? | Имя | Аргументы |
|---|---|---|---|
| sync | да | `is_trading_enabled` | `` |
| sync | да | `start_trading` | `` |
| sync | да | `stop_trading` | `` |
| sync | да | `get_status` | `` |
| async | да | `notify` | `text: str` |
| async | да | `_stop_telegram_bot` | `` |
| async | да | `_try_create_telegram_bot` | `` |
| async | да | `_telegram_watchdog` | `` |
| sync | да | `_trade_id_already_logged` | `trade_id: str` |
| sync | да | `_timestamp_for_log` | `value` |
| sync | да | `_log_strategy_diagnostic` | `event_type: str, ticker: str, figi: str, signal: str, reason: str, sm: StrategyManager, df: pd.DataFrame, price: float,` |
| async | да | `reconcile` | `client: TinkoffClient, monitor: ExecutionMonitor` |
| async | да | `close_position` | `client: TinkoffClient, pos, price: float` |
| async | да | `process_closing` | `client: TinkoffClient, monitor: ExecutionMonitor` |
| async | да | `trading_cycle` | `client: TinkoffClient, rm: RiskManager, sm: StrategyManager, monitor: ExecutionMonitor` |
| async | да | `main` | `` |

## tinkoff_client.py — сигнатуры (включая методы классов)

| Тип | Метод? | Имя | Аргументы |
|---|---|---|---|
| sync | да | `__init__` | `self, token: str, use_sandbox: bool = True` |
| async | да | `__aenter__` | `self` |
| async | да | `__aexit__` | `self, exc_type, exc_val, exc_tb` |
| async | да | `_ensure_account` | `self` |
| async | да | `get_all_tradable_shares` | `self` |
| async | да | `get_historical_candles` | `self, figi, days, interval=CandleInterval.CANDLE_INTERVAL_5_MIN` |
| async | да | `get_last_prices` | `self, figi_list` |
| async | да | `get_instrument_info` | `self, figi` |
| async | да | `get_account_balance` | `self` |
| async | да | `get_positions` | `self` |
| async | да | `get_positions_debug` | `self` |
| async | да | `post_market_order` | `self, figi, quantity, direction` |
| async | да | `get_sandbox_order_state` | `self, order_id: str` |
| sync | да | `is_uncertain` | `self` |

## PositionState — ВСЕ состояния (ИСПРАВЛЕНО)

| Имя | Значение |
|---|---|
| `OPEN` | `OPEN` |
| `CLOSING` | `CLOSING` |
| `CLOSED` | `CLOSED` |
| `UNCERTAIN` | `UNCERTAIN` |

## TrackedPosition — поля

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

## logger.py — TRADE_FIELDS

```
trade_id, timestamp_utc, ticker, figi, lot_size, side, signal_reason, signal_time, price_before_order, order_send_time, order_id, execution_status, requested_lots, executed_lots, execution_price, exit_reason, exit_price, exit_time, commission_rub, commission_source, actual_commission_rub, entry_commission_rub, exit_commission_rub, slippage_rub, slippage_percent, gross_pnl_rub, net_pnl_rub, cumulative_net_pnl_rub, error_note
```

## ⚠️ КЛЮЧЕВОЕ: от какой цены считаются SL/TP

### Тело `calculate_sl_tp` в risk_manager.py

```python
    def calculate_sl_tp(self, entry_price: float, direction: str,
                        candles_df: Optional[pd.DataFrame] = None) -> Tuple[Optional[float], Optional[float]]:
        if entry_price <= 0:
            return None, None
        base_stop_distance = entry_price * max(config.STOP_LOSS_PERCENT, config.MIN_STOP_LOSS_PERCENT)
        atr_risk = self._calculate_volatility_risk(candles_df)
        if atr_risk is not None:
            atr_cap = entry_price * config.MAX_ATR_STOP_PERCENT
            atr_risk = min(atr_risk, atr_cap)
            base_stop_distance = max(base_stop_distance, atr_risk)
        take_profit_distance = base_stop_distance * config.TAKE_PROFIT_RATIO
        if direction == "BUY":
            sl = entry_price - base_stop_distance
            tp = entry_price + take_profit_distance
            if sl >= entry_price:
                return None, None
        elif direction == "SELL":
            sl = entry_price + base_stop_distance
            tp = entry_price - take_profit_distance
            if sl <= entry_price:
                return None, None
        else:
            return None, None
        if sl <= 0 or tp <= 0:
            return None, None
        return sl, tp

```

### Вызовы `rm.calculate_sl_tp(...)` в main.py

- `rm.calculate_sl_tp(exec_price, signal, df)`
  - args: `exec_price, signal, df`
  - context: `['0)) / 1e9', '                        exec_price = total / le if le > 0 else total', '                    sl_price, tp_price =']`
- `rm.calculate_sl_tp(exec_price, signal, df)`
  - args: `exec_price, signal, df`
  - context: `['', '        rm.record_trade(figi)', '        sl_price, tp_price =']`

### Базис SL/TP (от какой цены)

```json
{
  "calls": [
    {
      "call": "rm.calculate_sl_tp(exec_price, signal, df)",
      "args": "exec_price, signal, df",
      "context_before": [
        "0)) / 1e9",
        "                        exec_price = total / le if le > 0 else total",
        "                    sl_price, tp_price ="
      ]
    },
    {
      "call": "rm.calculate_sl_tp(exec_price, signal, df)",
      "args": "exec_price, signal, df",
      "context_before": [
        "",
        "        rm.record_trade(figi)",
        "        sl_price, tp_price ="
      ]
    }
  ],
  "basis": [
    {
      "arg": "exec_price",
      "basis": "execution_price (фактическая)"
    },
    {
      "arg": "exec_price",
      "basis": "execution_price (фактическая)"
    }
  ]
}
```

## Тело `calculate_position_size` (фрагменты)

```python
    async def calculate_position_size(self, figi: str, last_price: float,
                                      candles_df: Optional[pd.DataFrame] = None) -> int:
        self._maybe_reset_by_date()

        if self.daily_trade_counts.get(figi, 0) >= config.MAX_TRADES_PER_INSTRUMENT_PER_DAY:
            return 0

        try:
            account_balance = await self.tinkoff_client.get_account_balance()
            if account_balance <= 0:
                return 0

            risk_amount = account_balance * config.RISK_PER_TRADE
            if risk_amount <= 0:
                return 0

            instrument_info = await self.tinkoff_client.get_instrument_info(figi)
            if not instrument_info:
                return 0

            lot_size = instrument_info['lot']
            if not lot_size or lot_size <= 0:
                return 0

            lot_cost = last_price * lot_size
            if lot_cost <= 0:
                return 0

            base_risk = last_price * max(config.STOP_LOSS_PERCENT, config.MIN_STOP_LOSS_PERCENT)
            friction = last_price * (config.COMMISSION_PER_SIDE * 2 + config.SLIPPAGE_PERCENT)
            per_share_risk = base_risk + friction

            atr_risk = self._calculate_volatility_risk(candles_df)
            if atr_risk is not None:
                atr_cap = last_price * config.MAX_ATR_STOP_PERCENT
                atr_risk = min(atr_risk, atr_cap)
                per_share_risk = max(per_share_risk, atr_risk + friction)

            if per_share_risk <= 0:
                return 0

            position_size_by_risk = int(risk_amount / (per_share_risk * lot_size))
            if position_size_by_risk <= 0:
                return 0

            max_position_value = account_balance * config.MAX_POSITION_SHARE_PER_INSTRUMENT
            position_size_by_capital = int(max_position_value / lot_cost)
            if position_size_by_capital <= 0:
                return 0

            positions = await self.tinkoff_client.get_positions()
            current_exposure = 0.0
            for f, qty in positions.items():
                # ИСПРАВЛЕНО: рубли/доллары/евро — это кэш, а не экспозиция.
                # Без этого рублёвый остаток (RUB000UTSTOM) считался как
                # экспозиция и блокировал новые входы по MAX_TOTAL_EXPOSURE.
                if f.startswith(("RUB", "USD", "EUR")):
                    continue
                info = await self.tinkoff_client.get_instrument_info(f)
                prices = await self.tinkoff_client.get_last_prices([f])
                p = prices.get(f, 0)
                if not info or not p:
                    continue
                # Явная семантика: см. config.POSITION_QUANTITY_IS_LOTS
                if config.POSITION_QUANTITY_IS_LOTS:
                    shares = qty * info['lot']  # qty в ЛОТАХ → умножаем на lot для штук
                else:
                    shares = qty                # qty в ШТУКАХ → уже штуки
                current_exposure += shares * p

            max_total = account_balance * config.MAX_TOTAL_EXPOSURE
            if current_exposure + lot_cost * position_size_by_capital > max_total:
                allowed_value = max(0.0, max_total - current_exposure)
                position_size_by_capital = int(allowed_value / lot_cost)

            position_size = min(position_size_by_risk, position_size_by_capital)
            return position_size if position_size > 0 else 0
        except Exception as e:
            logging.error(f"Ошибка расчёта позиции {figi}: {e}")
            return 0

```

## Формулы комиссии и проскальзывания

### main.py
```python
entry_slippage = (pos.entry_price - pos.price_before_order) * shares
exit_slippage = (pos.close_price_before_order - exit_price) * shares
total_slippage = entry_slippage + exit_slippage
turnover = (exit_price + pos.entry_price) * shares
model_total_commission = abs(turnover * config.COMMISSION_PER_SIDE)
exit_commission = pos.actual_commission
exit_commission = model_total_commission / 2.0
entry_commission = pos.entry_actual_commission
entry_commission = model_total_commission / 2.0
total_commission = entry_commission + exit_commission
entry_actual = pos.entry_actual_commission is not None
exit_actual = pos.actual_commission is not None
commission_source = "actual"
commission_source = "mixed"
commission_source = "model"
net_pnl = gross_pnl - total_commission
slippage_percent = (total_slippage / turnover * 100.0) if turnover > 0 else 0.0
f"comm_in=-{entry_commission:.2f}₽ comm_out=-{exit_commission:.2f}₽ ({commission_source}) "
f"slippage={total_slippage:+.2f}₽ ({slippage_percent:+.3f}%) "
pos.entry_actual_commission = ExecutionMonitor._extract_commission(state)
entry_commission = None
entry_commission = ExecutionMonitor._extract_commission(state)
pos.entry_actual_commission = entry_commission
f"entry_comm={entry_commission if entry_commission is not None else 'model'} "
```

### risk_manager.py
```python
risk_amount = account_balance * config.RISK_PER_TRADE
if risk_amount <= 0:
friction = last_price * (config.COMMISSION_PER_SIDE * 2 + config.SLIPPAGE_PERCENT)
per_share_risk = base_risk + friction
per_share_risk = max(per_share_risk, atr_risk + friction)
if per_share_risk <= 0:
position_size_by_risk = int(risk_amount / (per_share_risk * lot_size))
```

## Последовательность вызовов в trading_cycle (main.py)

```
1. logging.warning
2. close_position
3. process_closing
4. logging.warning
5. reconcile
6. logging.warning
7. logging.info
8. logging.warning
9. logging.error
10. logging.info
11. logging.info
12. logging.info
13. logging.info
14. _log_strategy_diagnostic
15. logging.info
16. _log_strategy_diagnostic
17. logging.info
18. research_logger.log_event
19. logging.error
20. logging.error
21. research_logger.log_event
22. logging.warning
23. logging.warning
24. rm.record_trade
25. logging.error
26. logging.info
27. research_logger.log_event
```

## screener — проверки

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

## ADX-гистерезис

```json
{
  "instantiations_count": 1,
  "stateful_fields_in_strategy": [
    "_last_regime",
    "_regime_streak",
    "_last_regime_candidate",
    "_last_regime_candidate"
  ],
  "risk": "WARNING: один StrategyManager на процесс → ADX-гистерезис перетекает между тикерами. Воспроизводить как есть (Q1=A), задокументировать; дополнительно — диагностическое сравнение с изолированным StrategyManager (Q1 доп.)."
}
```

## drop_incomplete / CANDLES_LOOKBACK_DAYS

```json
{
  "drop_incomplete": {
    "values_found": [
      "True"
    ]
  },
  "candles_lookback": {
    "uses_in_main": 1,
    "config_value": "2"
  }
}
```

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
