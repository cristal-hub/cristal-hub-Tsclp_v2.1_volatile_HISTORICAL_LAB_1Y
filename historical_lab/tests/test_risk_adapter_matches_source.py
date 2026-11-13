# historical_lab/tests/test_risk_adapter_matches_source.py
# B.9 #14: risk_adapter == risk_manager на моках (без API).

import pandas as pd
import pytest

from historical_lab import risk_adapter as RA
from historical_lab import _config_shim
_config_shim.install()

# Импорт RiskManager — но с мок-клиентом (без API).
from risk_manager import RiskManager


class MockClient:
    def __init__(self, balance=1_000_000.0, positions=None, prices=None, info=None):
        self.balance = balance
        self.positions = positions or {}
        self.prices = prices or {}
        self.info = info or {"lot": 1}

    async def get_account_balance(self):
        return self.balance

    async def get_instrument_info(self, figi):
        return self.info

    async def get_positions(self):
        return self.positions

    async def get_last_prices(self, figis):
        return {f: self.prices.get(f, 100.0) for f in figis}


def _make_df(closes):
    n = len(closes)
    return pd.DataFrame({
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1000] * n,
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"))


@pytest.mark.asyncio
async def test_sl_tp_matches():
    mock = MockClient()
    rm = RiskManager(mock)
    df = _make_df([100.0] * 50)
    sl_src, tp_src = rm.calculate_sl_tp(100.0, "BUY", df)
    sl_lab, tp_lab = RA.calculate_sl_tp(100.0, "BUY", df)
    assert sl_lab == pytest.approx(sl_src, abs=1e-9)
    assert tp_lab == pytest.approx(tp_src, abs=1e-9)


@pytest.mark.asyncio
async def test_position_size_matches():
    mock = MockClient(balance=1_000_000.0, positions={}, prices={}, info={"lot": 1})
    rm = RiskManager(mock)
    df = _make_df([100.0] * 50)
    lots_src = await rm.calculate_position_size("FIGI", 100.0, df)
    lots_lab = RA.calculate_position_size(
        figi="FIGI", last_price=100.0, candles_df=df,
        account_balance=1_000_000.0, lot_size=1,
        current_exposure=0.0, daily_trade_count=0,
    )
    assert lots_lab == lots_src