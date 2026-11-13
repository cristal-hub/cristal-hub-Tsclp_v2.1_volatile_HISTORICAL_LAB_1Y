# historical_lab/tests/test_entry_open_then_subsequent.py
# B.9 #8: вход на open_{t+1}, проверка high/low только t+1.

import pandas as pd

from historical_lab.backtest_engine import _check_sl_tp_on_candle


def test_check_only_subsequent_candles():
    idx = pd.date_range("2026-01-01 10:00", periods=5, freq="5min", tz="UTC")
    df = pd.DataFrame({
        "open": [100.0, 100.0, 100.0, 100.0, 100.0],
        "high": [101.0, 101.0, 110.0, 101.0, 101.0],  # TP только на свече idx[2]
        "low":  [99.0, 99.0, 99.0, 99.0, 99.0],
        "close": [100.0, 100.0, 100.0, 100.0, 100.0],
    }, index=idx)
    entry_ts = idx[1]
    subsequent = df[df.index > entry_ts]
    hits = []
    for ts, candle in subsequent.iterrows():
        r = _check_sl_tp_on_candle(candle, sl=95.0, tp=105.0)
        if r:
            hits.append((ts, r))
    assert len(hits) == 1
    assert hits[0][0] == idx[2]
    assert hits[0][1] == "TP"