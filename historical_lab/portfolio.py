# historical_lab/portfolio.py
# Tsclp_v2.1_volatile — ЭТАП C. Виртуальный портфель (B.6, Q5, Q6, Q7, Q10).
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import config_lab as C

log = logging.getLogger(__name__)


@dataclass
class Position:
    figi: str
    ticker: str
    entry_time: str          # ISO
    entry_price: float
    quantity: int            # ЛОТЫ (в песочнице lot=1; в данных — lot из instruments.json)
    lot_size: int
    sl_price: float
    tp_price: float
    entry_trigger: str       # "open" (B.3.1)
    entry_slippage_rub: float
    entry_commission_rub: float
    trade_id: str


@dataclass
class ClosedTrade:
    trade_id: str
    figi: str
    ticker: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    quantity: int            # ЛОТЫ
    lot_size: int
    shares: int              # quantity × lot_size
    exit_reason: str         # "SL" | "TP" | "GAP_SL" | "GAP_TP"
    exit_trigger: str        # "SL" | "TP" | "gap_open"
    entry_trigger: str
    entry_slippage_rub: float
    exit_slippage_rub: float
    total_slippage_rub: float
    entry_commission_rub: float
    exit_commission_rub: float
    total_commission_rub: float
    gross_pnl_rub: float
    net_pnl_rub: float
    scenario: str            # "base" | "stress_0.10" | ...
    period: str              # "DISCOVERY" | "VALIDATION" | "OOS"
    holding_seconds: float


class Portfolio:
    def __init__(self, starting_balance: float = None):
        self.initial_balance = starting_balance if starting_balance is not None else C.STARTING_BALANCE
        self.cash = self.initial_balance
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.trade_count_by_date: Dict[str, Dict[str, int]] = {}

    def _date_key(self, iso_ts: str) -> str:
        """Торговая дата (YYYY-MM-DD) из ISO (Q7)."""
        return iso_ts[:10]

    def get_trade_count(self, date_key: str, figi: str) -> int:
        """Счётчик FILL для (дата, figi) — Q10."""
        return self.trade_count_by_date.get(date_key, {}).get(figi, 0)

    def increment_trade_count(self, date_key: str, figi: str):
        """+1 после подтверждённого виртуального FILL (Q10)."""
        self.trade_count_by_date.setdefault(date_key, {})
        self.trade_count_by_date[date_key][figi] = self.trade_count_by_date[date_key].get(figi, 0) + 1

    def get_current_exposure(self, current_prices: Dict[str, float]) -> float:
        """
        B.6: экспозиция = Σ(shares × current_price) по открытым позициям.
        Валюта (RUB/USD/EUR) — НЕ позиция (как в risk_manager.py).
        Двойной учёт исключён: каждая позиция — один раз.
        """
        total = 0.0
        for figi, pos in self.open_positions.items():
            price = current_prices.get(figi, pos.entry_price)
            total += pos.quantity * pos.lot_size * price
        return total

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """equity = cash + Σ(shares × current_price) по открытым."""
        return self.cash + self.get_current_exposure(current_prices)

    def has_position(self, figi: str) -> bool:
        return figi in self.open_positions

    def open_position(self, position: Position):
        """Открывает позицию. Повторное открытие по тому же figi — запрещено."""
        if position.figi in self.open_positions:
            raise RuntimeError(f"Позиция уже открыта: {position.figi}")
        cost = position.entry_price * position.quantity * position.lot_size
        if cost + position.entry_commission_rub > self.cash:
            raise RuntimeError(
                f"Недостаточно cash: {self.cash:.2f} < {cost + position.entry_commission_rub:.2f}"
            )
        self.cash -= (cost + position.entry_commission_rub)
        self.open_positions[position.figi] = position

    def close_position(self, figi: str, closed_trade: ClosedTrade):
        """Закрывает позицию, добавляет в closed_trades, возвращает cash."""
        if figi not in self.open_positions:
            raise RuntimeError(f"Позиция не открыта: {figi}")
        proceeds = closed_trade.exit_price * closed_trade.quantity * closed_trade.lot_size
        self.cash += (proceeds - closed_trade.exit_commission_rub)
        del self.open_positions[figi]
        self.closed_trades.append(closed_trade)

    def summary(self, current_prices: Dict[str, float]) -> dict:
        """Краткая сводка портфеля."""
        return {
            "initial_balance": self.initial_balance,
            "cash": self.cash,
            "equity": self.get_equity(current_prices),
            "open_positions": len(self.open_positions),
            "closed_trades": len(self.closed_trades),
        }