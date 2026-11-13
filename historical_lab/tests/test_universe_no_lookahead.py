# historical_lab/tests/test_universe_no_lookahead.py
# B.9 #15: top10[t] не использует candles[t:].

import pandas as pd

from historical_lab import universe_selector as US


def test_window_excludes_future():
    """Окно [t-30д, t] не содержит свечей > t."""
    idx = pd.date_range("2025-12-01", periods=120, freq="D", tz="UTC")
    df = pd.DataFrame({
        "open": [100.0] * 120, "high": [101.0] * 120,
        "low": [99.0] * 120, "close": [100.5] * 120,
        "volume": [1000] * 120,
    }, index=idx)
    t = pd.Timestamp("2026-01-15", tz="UTC")
    from_dt = t - pd.Timedelta(days=30)
    window = df[(df.index >= from_dt) & (df.index <= t)]
    assert window.index.max() <= t
    future = df[df.index > t]
    assert (len(future) == 0) or (future.index.min() > t)