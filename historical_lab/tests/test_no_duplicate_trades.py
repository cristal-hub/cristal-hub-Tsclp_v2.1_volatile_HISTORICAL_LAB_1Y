# historical_lab/tests/test_no_duplicate_trades.py
# B.9 #11: один сигнал → одна сделка; повтор → skipped.

import pytest

from historical_lab.portfolio import Portfolio, Position


def test_open_position_twice_raises():
    p = Portfolio(starting_balance=1_000_000.0)
    pos = Position(
        figi="FIGI", ticker="T", entry_time="2026-01-01T10:00:00+00:00",
        entry_price=100.0, quantity=10, lot_size=1,
        sl_price=95.0, tp_price=110.0,
        entry_trigger="open", entry_slippage_rub=0.0,
        entry_commission_rub=0.5, trade_id="t1",
    )
    p.open_position(pos)
    with pytest.raises(RuntimeError):
        p.open_position(pos)


def test_has_position():
    p = Portfolio(starting_balance=1_000_000.0)
    assert not p.has_position("FIGI")
    pos = Position(
        figi="FIGI", ticker="T", entry_time="2026-01-01T10:00:00+00:00",
        entry_price=100.0, quantity=10, lot_size=1,
        sl_price=95.0, tp_price=110.0,
        entry_trigger="open", entry_slippage_rub=0.0,
        entry_commission_rub=0.5, trade_id="t1",
    )
    p.open_position(pos)
    assert p.has_position("FIGI")