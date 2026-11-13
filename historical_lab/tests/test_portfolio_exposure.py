# historical_lab/tests/test_portfolio_exposure.py
# B.9 #12: current_exposure без friction, без закрытых.

import pytest

from historical_lab.portfolio import Portfolio, Position


def test_exposure_only_open_positions():
    p = Portfolio(starting_balance=1_000_000.0)
    pos = Position(
        figi="FIGI", ticker="T", entry_time="2026-01-01T10:00:00+00:00",
        entry_price=100.0, quantity=10, lot_size=1,
        sl_price=95.0, tp_price=110.0,
        entry_trigger="open", entry_slippage_rub=0.0,
        entry_commission_rub=0.5, trade_id="t1",
    )
    p.open_position(pos)
    prices = {"FIGI": 110.0}
    assert p.get_current_exposure(prices) == pytest.approx(10 * 1 * 110.0)


def test_exposure_empty():
    p = Portfolio(starting_balance=1_000_000.0)
    assert p.get_current_exposure({}) == 0.0


def test_equity():
    p = Portfolio(starting_balance=1_000_000.0)
    pos = Position(
        figi="FIGI", ticker="T", entry_time="2026-01-01T10:00:00+00:00",
        entry_price=100.0, quantity=10, lot_size=1,
        sl_price=95.0, tp_price=110.0,
        entry_trigger="open", entry_slippage_rub=0.0,
        entry_commission_rub=0.5, trade_id="t1",
    )
    p.open_position(pos)
    prices = {"FIGI": 110.0}
    expected_cash = 1_000_000.0 - (100.0 * 10 + 0.5)
    assert p.get_equity(prices) == pytest.approx(expected_cash + 10 * 110.0)