# historical_lab/tests/test_timestamps_sessions.py
# B.9 #10: торговые сессии, границы дня.

import pandas as pd

from historical_lab.portfolio import Portfolio


def test_trade_count_resets_by_date():
    p = Portfolio(starting_balance=1_000_000.0)
    p.increment_trade_count("2026-01-01", "FIGI1")
    p.increment_trade_count("2026-01-01", "FIGI1")
    p.increment_trade_count("2026-01-02", "FIGI1")
    assert p.get_trade_count("2026-01-01", "FIGI1") == 2
    assert p.get_trade_count("2026-01-02", "FIGI1") == 1
    assert p.get_trade_count("2026-01-03", "FIGI1") == 0


def test_date_key_from_iso():
    p = Portfolio()
    assert p._date_key("2026-01-01T10:00:00+00:00") == "2026-01-01"