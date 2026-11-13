# historical_lab/metrics.py
# Tsclp_v2.1_volatile — ЭТАП C. Статистика (п.7 ТЗ, B.7).
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.
#
# ВАЖНО: ниже — существующий код (v1). Не изменять.
# В конец файла добавлены функции для v2 (drawdown_equity, equity_curve_daily).
# max_drawdown (v1) — семантика НЕ изменена.

import logging
from collections import defaultdict
from typing import List

from .portfolio import ClosedTrade

log = logging.getLogger(__name__)


def _empty_metrics() -> dict:
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_profit": 0.0,
        "profit_factor": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "expectancy": 0.0,
        "max_drawdown": 0.0,
        "max_losing_streak": 0,
        "avg_holding_seconds": 0.0,
        "max_holding_seconds": 0.0,
        "total_commission": 0.0,
        "total_slippage": 0.0,
        "net_before_cost": 0.0,
        "net_after_cost": 0.0,
        "trades_by_day": {},
        "trades_by_instrument": {},
    }


def compute_metrics(trades: List[ClosedTrade]) -> dict:
    """Метрики по списку закрытых сделок. max_drawdown — по реализованному P&L (v1)."""
    if not trades:
        return _empty_metrics()

    m = _empty_metrics()
    m["trades"] = len(trades)
    wins = [t for t in trades if t.net_pnl_rub > 0]
    losses = [t for t in trades if t.net_pnl_rub <= 0]
    m["wins"] = len(wins)
    m["losses"] = len(losses)
    m["win_rate"] = len(wins) / len(trades) * 100.0

    m["gross_profit"] = sum(t.net_pnl_rub for t in wins)
    m["gross_loss"] = abs(sum(t.net_pnl_rub for t in losses))
    m["net_profit"] = sum(t.net_pnl_rub for t in trades)
    m["profit_factor"] = (m["gross_profit"] / m["gross_loss"]) if m["gross_loss"] > 0 else float("inf")
    m["avg_win"] = (m["gross_profit"] / len(wins)) if wins else 0.0
    m["avg_loss"] = (-m["gross_loss"] / len(losses)) if losses else 0.0
    m["expectancy"] = m["net_profit"] / len(trades)
    m["total_commission"] = sum(t.total_commission_rub for t in trades)
    m["total_slippage"] = sum(t.total_slippage_rub for t in trades)
    m["net_before_cost"] = sum(t.gross_pnl_rub for t in trades)
    m["net_after_cost"] = m["net_profit"]

    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cum += t.net_pnl_rub
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    m["max_drawdown"] = max_dd

    streak = 0
    max_streak = 0
    for t in trades:
        if t.net_pnl_rub <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    m["max_losing_streak"] = max_streak

    holds = [t.holding_seconds for t in trades]
    m["avg_holding_seconds"] = sum(holds) / len(holds)
    m["max_holding_seconds"] = max(holds)

    by_day = defaultdict(int)
    by_inst = defaultdict(int)
    for t in trades:
        day = t.exit_time[:10]
        by_day[day] += 1
        by_inst[t.ticker] += 1
    m["trades_by_day"] = dict(by_day)
    m["trades_by_instrument"] = dict(by_inst)
    return m


def metrics_by_instrument(trades: List[ClosedTrade]) -> dict:
    groups = defaultdict(list)
    for t in trades:
        groups[t.ticker].append(t)
    return {k: compute_metrics(v) for k, v in groups.items()}


def metrics_by_period(trades: List[ClosedTrade]) -> dict:
    groups = defaultdict(list)
    for t in trades:
        groups[t.period].append(t)
    return {k: compute_metrics(v) for k, v in groups.items()}


def portfolio_metrics(trades: List[ClosedTrade]) -> dict:
    return compute_metrics(trades)


# ============================================================
# v2: ДОПОЛНЕНИЯ (не влияют на v1)
# ============================================================

def compute_drawdown_equity(equity_curve: List[tuple]) -> dict:
    """
    max_drawdown_equity по полной equity_curve.
    equity_curve: [("START", 1000000.0), (ts_str, eq), ...].
    Возвращает {"max_drawdown_equity": float, "max_drawdown_equity_ts": str|None}.
    Начальная точка участвует в peak.
    """
    if not equity_curve:
        return {"max_drawdown_equity": 0.0, "max_drawdown_equity_ts": None}
    peak = 0.0
    max_dd = 0.0
    dd_ts = None
    for ts_label, eq in equity_curve:
        eq_f = float(eq)
        if eq_f > peak:
            peak = eq_f
        dd = peak - eq_f
        if dd > max_dd:
            max_dd = dd
            dd_ts = ts_label
    return {"max_drawdown_equity": max_dd, "max_drawdown_equity_ts": dd_ts}


def equity_curve_daily(equity_curve: List[tuple]) -> List[dict]:
    """
    Конвертирует полную equity_curve в daily (последняя точка каждого UTC-дня).
    Пропускает "START". Возвращает [{"date": "...", "equity": ...}, ...].
    """
    import pandas as pd
    by_date = {}
    for ts_label, eq in equity_curve:
        if ts_label == "START":
            continue
        try:
            d = str(pd.Timestamp(ts_label).date())
        except Exception:
            continue
        by_date[d] = float(eq)
    return [{"date": d, "equity": eq} for d, eq in sorted(by_date.items())]