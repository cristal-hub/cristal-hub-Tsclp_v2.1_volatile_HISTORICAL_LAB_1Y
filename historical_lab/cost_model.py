# historical_lab/cost_model.py
# Tsclp_v2.1_volatile — ЭТАП C. Модель издержек (B.3, B.8, Q4, Q8).
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import logging
from dataclasses import dataclass

from . import config_lab as C

log = logging.getLogger(__name__)


@dataclass
class ExecutionPrices:
    """Результат применения slippage к триггеру."""
    trigger_price: float      # SL/TP/open (до slippage)
    exec_price: float         # фактическая цена исполнения (после slippage)
    slippage_rub: float       # (trigger − exec) × shares (диагностика)


def apply_entry_slippage(open_price: float, shares: int, extra_slippage: float = 0.0) -> ExecutionPrices:
    """
    Вход BUY: entry_price = open × (1 + slippage).
    slippage_rub = (entry_price − open) × shares  (положительное = неблагоприятное).
    extra_slippage — дополнительный стресс (B8), сверх C.SLIPPAGE_PERCENT.
    """
    total_slip = C.SLIPPAGE_PERCENT + extra_slippage
    entry_price = open_price * (1.0 + total_slip)
    slip_rub = (entry_price - open_price) * shares
    return ExecutionPrices(
        trigger_price=open_price,
        exec_price=entry_price,
        slippage_rub=slip_rub,
    )


def apply_exit_slippage(trigger_price: float, shares: int, extra_slippage: float = 0.0) -> ExecutionPrices:
    """
    Выход SELL: exit_price = trigger × (1 − slippage).
    slippage_rub = (trigger − exit_price) × shares  (положительное = неблагоприятное).
    trigger — SL/TP (внутри свечи) или open_{t_exit+1} (при гэпе, B.3.3).
    """
    total_slip = C.SLIPPAGE_PERCENT + extra_slippage
    exit_price = trigger_price * (1.0 - total_slip)
    slip_rub = (trigger_price - exit_price) * shares
    return ExecutionPrices(
        trigger_price=trigger_price,
        exec_price=exit_price,
        slippage_rub=slip_rub,
    )


def calc_commission(entry_price: float, exit_price: float, shares: int) -> dict:
    """
    Комиссия (Q8): отдельно на входе и выходе.
    entry_commission = COMMISSION_PER_SIDE × entry_price × shares
    exit_commission  = COMMISSION_PER_SIDE × exit_price × shares
    total_commission = entry_commission + exit_commission
    """
    entry_comm = abs(C.COMMISSION_PER_SIDE * entry_price * shares)
    exit_comm = abs(C.COMMISSION_PER_SIDE * exit_price * shares)
    return {
        "entry_commission_rub": entry_comm,
        "exit_commission_rub": exit_comm,
        "total_commission_rub": entry_comm + exit_comm,
    }


def calc_pnl(entry_price: float, exit_price: float, shares: int, commission: dict) -> dict:
    """
    P&L: gross = (exit − entry) × shares; net = gross − total_commission.
    Slippage НЕ вычитается повторно (уже в ценах, B.3.7).
    """
    gross = (exit_price - entry_price) * shares
    net = gross - commission["total_commission_rub"]
    return {
        "gross_pnl_rub": gross,
        "net_pnl_rub": net,
    }