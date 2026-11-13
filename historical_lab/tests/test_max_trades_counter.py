# historical_lab/tests/test_max_trades_counter.py
# B.9 #16: MAX_TRADES считает FILL, не сигналы.

from historical_lab import config_lab as C
from historical_lab.portfolio import Portfolio


def test_counter_increments_only_on_fill():
    p = Portfolio(starting_balance=1_000_000.0)
    assert p.get_trade_count("2026-01-01", "FIGI") == 0
    # "сигналы" не увеличивают
    assert p.get_trade_count("2026-01-01", "FIGI") == 0
    # FILL
    p.increment_trade_count("2026-01-01", "FIGI")
    assert p.get_trade_count("2026-01-01", "FIGI") == 1


def test_max_trades_limit_constant():
    assert C.MAX_TRADES_PER_INSTRUMENT_PER_DAY == 5