# historical_lab/tests/test_execution_after_close.py
# B.9 #2: entry_time > signal_time.

import pandas as pd

from historical_lab.backtest_engine import _find_first_open_after


def test_entry_after_signal():
    idx = pd.date_range("2026-01-01 10:00", periods=10, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": [100.0] * 10}, index=idx)
    signal_time = idx[3]
    entry_ts = _find_first_open_after(df, signal_time)
    assert entry_ts is not None
    assert entry_ts > signal_time
    assert entry_ts == idx[4]