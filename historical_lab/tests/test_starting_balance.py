# historical_lab/tests/test_starting_balance.py
# B.9 #17: STARTING_BALANCE = 1_000_000; .env не читается.

from historical_lab import config_lab as C
from historical_lab.portfolio import Portfolio


def test_starting_balance_value():
    assert C.STARTING_BALANCE == 1_000_000.0


def test_portfolio_initial_balance():
    p = Portfolio()
    assert p.initial_balance == 1_000_000.0
    assert p.cash == 1_000_000.0


def test_no_dotenv_imported():
    import sys
    from historical_lab import config_lab  # noqa: F401
    assert "dotenv" not in sys.modules