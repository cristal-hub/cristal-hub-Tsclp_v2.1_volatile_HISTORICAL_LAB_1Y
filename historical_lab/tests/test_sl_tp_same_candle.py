# historical_lab/tests/test_sl_tp_same_candle.py
# B.9 #5: SL и TP в одной свече → SL первым.

import pandas as pd

from historical_lab.backtest_engine import _check_sl_tp_on_candle


def test_sl_and_tp_same_candle_sl_first():
    candle = pd.Series({"high": 110.0, "low": 90.0, "open": 100.0, "close": 100.0})
    result = _check_sl_tp_on_candle(candle, sl=95.0, tp=105.0)
    assert result == "SL_AND_TP"


def test_only_sl():
    candle = pd.Series({"high": 100.0, "low": 90.0, "open": 100.0, "close": 100.0})
    assert _check_sl_tp_on_candle(candle, sl=95.0, tp=105.0) == "SL"


def test_only_tp():
    candle = pd.Series({"high": 110.0, "low": 100.0, "open": 100.0, "close": 100.0})
    assert _check_sl_tp_on_candle(candle, sl=95.0, tp=105.0) == "TP"


def test_none():
    candle = pd.Series({"high": 102.0, "low": 98.0, "open": 100.0, "close": 100.0})
    assert _check_sl_tp_on_candle(candle, sl=95.0, tp=105.0) is None