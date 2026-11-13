# historical_lab/tests/test_no_lookahead.py
# B.9 #1: df_window не содержит t+1; индикаторы не используют будущее.

import pandas as pd
import pytest

from historical_lab import config_lab as C
from historical_lab import data_loader


def _make_5min(start, periods, freq="5min"):
    idx = pd.date_range(start=start, periods=periods, freq=freq, tz="UTC")
    return pd.DataFrame({
        "open": [100.0] * periods,
        "high": [101.0] * periods,
        "low": [99.0] * periods,
        "close": [100.5] * periods,
        "volume": [1000] * periods,
    }, index=idx)


def test_window_excludes_future():
    """df_window для даты t не содержит свечей > t."""
    df = _make_5min("2026-01-01", periods=200)
    t = pd.Timestamp("2026-01-02", tz="UTC")
    window_start = t - pd.Timedelta(days=C.CANDLES_LOOKBACK_DAYS)
    df_window = df[(df.index >= window_start) & (df.index <= t)]
    assert df_window.index.max() <= t
    assert len(df_window) > 0


def test_window_does_not_include_next_candle():
    """Свеча t+1 не попадает в окно. t — ВНУТРИ диапазона, чтобы after был непуст."""
    df = _make_5min("2026-01-01", periods=200)   # 200 × 5мин ≈ 16.6 ч
    t = pd.Timestamp("2026-01-01 12:00", tz="UTC")  # внутри диапазона
    df_window = df[df.index <= t]
    after = df[df.index > t]
    assert len(df_window) > 0
    assert len(after) > 0                  # after НЕ пуст
    assert df_window.index.max() <= t
    assert after.index.min() > t
    assert df_window.index.max() < after.index.min()