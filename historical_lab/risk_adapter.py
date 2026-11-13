# historical_lab/risk_adapter.py
# Tsclp_v2.1_volatile — ЭТАП C. Адаптер RiskManager (автономная копия формул).
#
# B5: копируем calculate_position_size, calculate_sl_tp, _calculate_volatility_risk
#     БЕЗ импорта RiskManager (чтобы не тянуть tinkoff_client).
#     Формулы НЕ упрощены, НЕ оптимизированы.
#     Тест test_risk_adapter_matches_source.py сравнивает с исходником на моках.
#
# STRATEGY LOGIC: UNCHANGED. RISK LOGIC: UNCHANGED.
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import logging
from typing import Optional, Tuple

import pandas as pd
import pandas_ta_classic as ta

from . import config_lab as C

log = logging.getLogger(__name__)


def _calculate_volatility_risk(candles_df: Optional[pd.DataFrame]) -> Optional[float]:
    """
    КОПИЯ RiskManager._calculate_volatility_risk.
    ATR(ATR_PERIOD_INTRADAY=20) * ATR_STOP_MULTIPLIER=1.5.
    """
    if candles_df is None or candles_df.empty:
        return None
    if not {"high", "low", "close"}.issubset(candles_df.columns):
        return None
    period = C.ATR_PERIOD_INTRADAY
    if len(candles_df) < period:
        return None
    try:
        atr_series = ta.atr(
            high=candles_df["high"], low=candles_df["low"],
            close=candles_df["close"], length=period,
        )
        if atr_series is None or atr_series.empty:
            return None
        atr_val = atr_series.iloc[-1]
        if pd.isna(atr_val) or atr_val <= 0:
            return None
        return float(atr_val) * C.ATR_STOP_MULTIPLIER
    except Exception as e:
        log.error(f"ATR risk error: {e}")
        return None


def calculate_sl_tp(
    entry_price: float,
    direction: str,
    candles_df: Optional[pd.DataFrame] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    КОПИЯ RiskManager.calculate_sl_tp.
    SL/TP — от entry_price (фактическая цена исполнения, A.7).
    """
    if entry_price <= 0:
        return None, None
    base_stop_distance = entry_price * max(C.STOP_LOSS_PERCENT, C.MIN_STOP_LOSS_PERCENT)
    atr_risk = _calculate_volatility_risk(candles_df)
    if atr_risk is not None:
        atr_cap = entry_price * C.MAX_ATR_STOP_PERCENT
        atr_risk = min(atr_risk, atr_cap)
        base_stop_distance = max(base_stop_distance, atr_risk)
    take_profit_distance = base_stop_distance * C.TAKE_PROFIT_RATIO
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


def calculate_position_size(
    figi: str,
    last_price: float,
    candles_df: Optional[pd.DataFrame],
    account_balance: float,
    lot_size: int,
    current_exposure: float,
    daily_trade_count: int,
) -> int:
    """
    КОПИЯ RiskManager.calculate_position_size (sync-версия для backtest).
    Входные данные — из виртуального портфеля (B6), НЕ из API.

    Формула (A.7.2) — БЕЗ изменений:
      risk_amount = account_balance * RISK_PER_TRADE
      lot_cost = last_price * lot_size
      base_risk = last_price * max(STOP_LOSS_PERCENT, MIN_STOP_LOSS_PERCENT)
      friction = last_price * (COMMISSION_PER_SIDE * 2 + SLIPPAGE_PERCENT)
      per_share_risk = base_risk + friction
      atr_risk = _calculate_volatility_risk(candles_df)  # cap = last_price * 3%
      per_share_risk = max(per_share_risk, atr_risk + friction)
      position_size_by_risk = int(risk_amount / (per_share_risk * lot_size))
      max_position_value = account_balance * MAX_POSITION_SHARE_PER_INSTRUMENT
      position_size_by_capital = int(max_position_value / lot_cost)
      if current_exposure + lot_cost * position_size_by_capital > account_balance * MAX_TOTAL_EXPOSURE:
          allowed = max(0.0, max_total - current_exposure)
          position_size_by_capital = int(allowed / lot_cost)
      position_size = min(position_size_by_risk, position_size_by_capital)
    """
    # Аналог self._maybe_reset_by_date() — сброс дневного счётчика
    # выполняется в portfolio.py (Q7: по торговой дате).
    if daily_trade_count >= C.MAX_TRADES_PER_INSTRUMENT_PER_DAY:
        return 0

    try:
        if account_balance <= 0:
            return 0
        risk_amount = account_balance * C.RISK_PER_TRADE
        if risk_amount <= 0:
            return 0
        if not lot_size or lot_size <= 0:
            return 0
        lot_cost = last_price * lot_size
        if lot_cost <= 0:
            return 0

        base_risk = last_price * max(C.STOP_LOSS_PERCENT, C.MIN_STOP_LOSS_PERCENT)
        friction = last_price * (C.COMMISSION_PER_SIDE * 2 + C.SLIPPAGE_PERCENT)
        per_share_risk = base_risk + friction

        atr_risk = _calculate_volatility_risk(candles_df)
        if atr_risk is not None:
            atr_cap = last_price * C.MAX_ATR_STOP_PERCENT
            atr_risk = min(atr_risk, atr_cap)
            per_share_risk = max(per_share_risk, atr_risk + friction)

        if per_share_risk <= 0:
            return 0
        position_size_by_risk = int(risk_amount / (per_share_risk * lot_size))
        if position_size_by_risk <= 0:
            return 0

        max_position_value = account_balance * C.MAX_POSITION_SHARE_PER_INSTRUMENT
        position_size_by_capital = int(max_position_value / lot_cost)
        if position_size_by_capital <= 0:
            return 0

        max_total = account_balance * C.MAX_TOTAL_EXPOSURE
        if current_exposure + lot_cost * position_size_by_capital > max_total:
            allowed_value = max(0.0, max_total - current_exposure)
            position_size_by_capital = int(allowed_value / lot_cost)

        position_size = min(position_size_by_risk, position_size_by_capital)
        return position_size if position_size > 0 else 0
    except Exception as e:
        log.error(f"Ошибка расчёта позиции {figi}: {e}")
        return 0