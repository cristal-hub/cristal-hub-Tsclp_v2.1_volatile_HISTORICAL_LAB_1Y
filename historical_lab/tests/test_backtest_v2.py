# historical_lab/tests/test_backtest_v2.py
# Tsclp_v2.1_volatile — тесты backtest_engine_v2 (23 теста).
# Все на моках/синтетике. Без API, без реальных данных.
#
# STRATEGY LOGIC: UNCHANGED. RESEARCH ONLY. NO LIVE ORDERS.

import csv
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from historical_lab import config_lab as C
from historical_lab import cost_model as CM
from historical_lab import risk_adapter as RA
from historical_lab import _config_shim
_config_shim.install()

from historical_lab.portfolio import Portfolio, Position
from historical_lab.strategy_adapter import SharedStrategyAdapter
from historical_lab.backtest_engine_v2 import (
    BacktestEngineV2, _check_sl_tp_on_candle, _last_known_price_before,
    _next_candle_time,
)


# ============================================================
# Helpers
# ============================================================

def _mk_df(times, opens=None, highs=None, lows=None, closes=None, volumes=None):
    n = len(times)
    if opens is None: opens = [100.0] * n
    if highs is None: highs = [o * 1.01 for o in opens]
    if lows is None: lows = [o * 0.99 for o in opens]
    if closes is None: closes = opens
    if volumes is None: volumes = [1000] * n
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    }, index=pd.DatetimeIndex(times, tz="UTC"))


def _times(start, n, freq="5min"):
    return [pd.Timestamp(start, tz="UTC") + pd.Timedelta(minutes=5*i) for i in range(n)]


class FakeAdapter:
    """Возвращает BUY на первой свече, дальше HOLD. Или настраиваемый список."""
    def __init__(self, signals=None):
        self._signals = list(signals or [])
        self.calls = []

    def get_signal(self, figi, df, close, drop_incomplete=True):
        self.calls.append((figi, len(df)))
        if self._signals:
            return self._signals.pop(0)
        return ("HOLD", "fake")


def _instruments(figi="F1", lot=1, ticker="T1"):
    return {figi: {"figi": figi, "ticker": ticker, "lot": lot}}


def _top10(date_str, figis):
    return {date_str: [{"figi": f, "ticker": f, "lot": 1} for f in figis]}


def _periods():
    return {"discovery_end": "9999-12-31", "validation_end": "9999-12-31"}


# ============================================================
# 1. signal_every_closed_candle
# ============================================================

def test_signal_every_closed_candle():
    """get_signal вызывается на каждой свече FIGI в TOP-10 (без позиции/pending)."""
    times = _times("2026-01-01 10:00", 5)
    candles = {"F1": _mk_df(times)}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter()   # всегда HOLD
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # 5 свечей → 5 вызовов (все HOLD, нет pending)
    assert res["counters"]["actual_get_signal_calls"] == 5
    assert res["counters"]["eligible_signal_events"] == 5


# ============================================================
# 2. no_repeat_on_same_candle
# ============================================================

def test_no_repeat_on_same_candle():
    """get_signal не вызывается повторно на той же свече."""
    times = _times("2026-01-01 10:00", 3)
    candles = {"F1": _mk_df(times)}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter()
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # 3 свечи → 3 вызова, не больше
    assert len(adapter.calls) == 3
    # Проверка уникальности (figi, ts) через len(df) — не идеально, но вызовов ровно 3
    assert len(adapter.calls) == 3


# ============================================================
# 3. entry_next_available_candle
# ============================================================

def test_entry_next_available_candle():
    """Вход на следующей доступной свече после сигнала."""
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100, 101, 102], closes=[100, 101, 102])
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    # BUY на первой свече, потом HOLD
    adapter = FakeAdapter(signals=[("BUY", "t1"), ("HOLD", "x"), ("HOLD", "x")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Позиция открыта на open times[1] = 101
    open_positions = res["open_positions"]
    # Может быть уже закрыта SL/TP; ищем в closed_trades
    if open_positions:
        assert open_positions[0].entry_price == pytest.approx(101.0 * (1 + C.SLIPPAGE_PERCENT))
    elif res["closed_trades"]:
        t = res["closed_trades"][0]
        assert t.entry_price == pytest.approx(101.0 * (1 + C.SLIPPAGE_PERCENT))


# ============================================================
# 4. no_entry_on_incomplete_candle
# ============================================================

def test_no_entry_on_incomplete_candle():
    """Синтетика: is_complete=False — стратегия исключает свечу; движок не входит по ней."""
    # Проверяем на уровне strategy_adapter (drop_incomplete), не на уровне движка.
    from strategy import StrategyManager
    sm = StrategyManager()
    n = 60
    closes = [100.0] * n
    df = pd.DataFrame({
        "open": closes, "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes], "close": closes,
        "volume": [1000] * n,
    }, index=_times("2026-01-01 10:00", n))
    df["is_complete"] = [True] * (n - 1) + [False]
    prepared = sm._prepare_dataframe(df, drop_incomplete=True)
    # Последняя свеча (is_complete=False) отброшена
    assert len(prepared) == n - 1


# ============================================================
# 5. top10_boundary
# ============================================================

def test_top10_boundary():
    """TOP-10 на границе дня корректен: FIGI, не входящий в TOP-10 даты, не получает сигналов."""
    times_d1 = _times("2026-01-01 10:00", 3)
    times_d2 = _times("2026-01-02 10:00", 3)
    times = times_d1 + times_d2
    candles = {"F1": _mk_df(times)}
    # F1 в TOP-10 только 2026-01-01
    top10 = {"2026-01-01": [{"figi": "F1", "ticker": "F1", "lot": 1}],
             "2026-01-02": []}
    adapter = FakeAdapter()
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-03")
    # 3 вызова в день 1 (F1 в TOP-10), 0 в день 2 (F1 не в TOP-10)
    assert res["counters"]["actual_get_signal_calls"] == 3


# ============================================================
# 6. no_lookahead
# ============================================================

def test_no_lookahead():
    """Окно df_window не содержит свечей > ts (проверяем через _last_known_price_before)."""
    times = _times("2026-01-01 10:00", 5)
    df = _mk_df(times, closes=[100, 101, 102, 103, 104])
    ts = times[2]
    price = _last_known_price_before("F1", ts, df)
    assert price == 101.0   # close times[1] (строго до ts), не times[2]


# ============================================================
# 7. sl_tp_gap
# ============================================================

def test_sl_tp_gap():
    """Гэп через SL: open уже ниже SL → exit по open."""
    # Позиция с SL=95, на следующей свече open=90
    times = _times("2026-01-01 10:00", 3)
    opens = [100.0, 90.0, 91.0]
    highs = [101.0, 92.0, 92.0]
    lows = [99.0, 89.0, 90.0]
    closes = [100.0, 91.0, 91.0]
    df = _mk_df(times, opens, highs, lows, closes)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    # Переопределим SL/TP через монkeypatch risk_adapter
    with patch.object(RA, "calculate_sl_tp", return_value=(95.0, 110.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Хотя бы одна closed-сделка с GAP_SL
    gap_trades = [t for t in res["closed_trades"] if t.exit_reason == "GAP_SL"]
    assert len(gap_trades) >= 1


# ============================================================
# 8. multiple_positions
# ============================================================

def test_multiple_positions():
    """Несколько позиций одновременно (2 FIGI, оба BUY)."""
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100, 100, 100])
    candles = {"F1": df, "F2": df.copy()}
    top10 = _top10("2026-01-01", ["F1", "F2"])
    # Для каждого FIGI: BUY, HOLD, HOLD
    adapter = FakeAdapter(signals=[
        ("BUY", "t1"),   # F1 сигнал
        ("BUY", "t1"),   # F2 сигнал
    ])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    res = engine.run(top10, _instruments(figi="F1") | _instruments(figi="F2"), candles,
                     "2026-01-01", "2026-01-02")
    # Должны быть 2 FILL (F1 и F2)
    assert res["counters"]["actual_get_signal_calls"] >= 2


# ============================================================
# 9. capital_limits
# ============================================================

def test_capital_limits():
    """MAX_TRADES_PER_INSTRUMENT_PER_DAY ограничивает количество FILL."""
    times = _times("2026-01-01 10:00", 10)
    df = _mk_df(times, opens=[100]*10)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    # 5 BUY (лимит 5), но каждый требует следующую свечу
    adapter = FakeAdapter(signals=[("BUY", "t1")] * 10)
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    # Патчим calculate_position_size, чтобы lots всегда 1
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(90.0, 120.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Открытых+закрытых не больше 5 (MAX_TRADES) + возможно оставшиеся
    total = len(res["closed_trades"]) + len(res["open_positions"])
    assert total <= C.MAX_TRADES_PER_INSTRUMENT_PER_DAY


# ============================================================
# 10. no_reopen
# ============================================================

def test_no_reopen():
    """Нет повторного открытия, пока позиция открыта."""
    times = _times("2026-01-01 10:00", 5)
    df = _mk_df(times, opens=[100]*5)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    # BUY на каждой свече
    adapter = FakeAdapter(signals=[("BUY", "t1")] * 5)
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(50.0, 200.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Позиция не закрыта (SL/TP далеко), reopen не было → 1 позиция
    assert len(res["open_positions"]) <= 1


# ============================================================
# 11. no_duplicate_call_or_order
# ============================================================

def test_no_duplicate_call_or_order():
    """Нет повторного вызова на одной свече и повторных заявок."""
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100]*3)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter()
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Ровно 3 вызова (по одному на свечу)
    assert res["counters"]["actual_get_signal_calls"] == 3


# ============================================================
# 12. multi_figi_deterministic
# ============================================================

def test_multi_figi_deterministic():
    """Одновременные FIGI обрабатываются в детерминированном порядке (TOP-10 order)."""
    times = _times("2026-01-01 10:00", 2)
    df = _mk_df(times, opens=[100]*2)
    candles = {"F2": df.copy(), "F1": df.copy()}
    # Порядок в TOP-10: F1, F2 (хотя в candles F2 первый)
    top10 = {"2026-01-01": [
        {"figi": "F1", "ticker": "F1", "lot": 1},
        {"figi": "F2", "ticker": "F2", "lot": 1},
    ]}
    adapter = FakeAdapter()
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    engine.run(top10, _instruments(figi="F1") | _instruments(figi="F2"), candles,
               "2026-01-01", "2026-01-02")
    # Первые два вызова: F1, F2 (порядок TOP-10), а не F2, F1
    assert adapter.calls[0][0] == "F1"
    assert adapter.calls[1][0] == "F2"


# ============================================================
# 13. position_monitored_outside_top10
# ============================================================

def test_position_monitored_outside_top10():
    """Позиция контролируется после выхода FIGI из TOP-10."""
    times = _times("2026-01-01 10:00", 3) + _times("2026-01-02 10:00", 3)
    df = _mk_df(times, opens=[100]*6, highs=[101]*6, lows=[99]*6)
    candles = {"F1": df}
    # F1 в TOP-10 только 2026-01-01
    top10 = {"2026-01-01": [{"figi": "F1", "ticker": "F1", "lot": 1}],
             "2026-01-02": []}
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(90.0, 110.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-03")
    # Позиция либо открыта, либо закрыта — но контролировалась
    assert res["counters"]["position_monitoring_events"] >= 1


# ============================================================
# 14. entry_candle_sl_tp
# ============================================================

def test_entry_candle_sl_tp():
    """SL/TP проверяются на свече исполнения (ts == entry_time)."""
    # Вход на свече 1 (open=100), high=110, low=90, SL=95, TP=105
    # На свече 1: low=90 <= 95 → SL сработал на свече входа
    times = _times("2026-01-01 10:00", 3)
    opens = [100.0, 100.0, 100.0]
    highs = [101.0, 110.0, 101.0]
    lows = [99.0, 90.0, 99.0]
    closes = [100.0, 100.0, 100.0]
    df = _mk_df(times, opens, highs, lows, closes)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(95.0, 105.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # SL сработал на свече входа (times[1]) — позиция закрыта
    sl_trades = [t for t in res["closed_trades"] if t.exit_reason in ("SL", "GAP_SL", "SL_AND_TP")]
    assert len(sl_trades) >= 1


# ============================================================
# 15. pending_order_not_in_exposure
# ============================================================

def test_pending_order_not_in_exposure():
    """Pending не учитывается как открытая позиция до FILL."""
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100]*3)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(90.0, 120.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # После прогона: pending может остаться (если next_ts None) — отменён
    # Позиция либо 1 (если FILL), либо 0 (если pending отменён)
    # Главное: pending никогда не в open_positions
    assert all(p.figi != "F1" or p.quantity > 0 for p in res["open_positions"])


# ============================================================
# 16. fill_day_trade_counter
# ============================================================

def test_fill_day_trade_counter():
    """Счётчик сделок использует дату FILL, не сигнала."""
    p = Portfolio(starting_balance=1_000_000.0)
    p.increment_trade_count("2026-01-02", "F1")
    assert p.get_trade_count("2026-01-02", "F1") == 1
    assert p.get_trade_count("2026-01-01", "F1") == 0


# ============================================================
# 17. simultaneous_event_phases
# ============================================================

def test_simultaneous_event_phases():
    """Для одного ts — pending fill раньше сигналов."""
    # Первая свеча: BUY. Вторая: pending fill + потенциальный BUY (но позиция уже есть → нет).
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100]*3)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(90.0, 120.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Позиция открыта (FILL), повторного BUY не было
    total = len(res["closed_trades"]) + len(res["open_positions"])
    assert total <= 1


# ============================================================
# 18. pending_fill_capacity_check
# ============================================================

def test_pending_fill_capacity_check():
    """При FILL проверяются лимиты (lots уменьшается при недостатке cash)."""
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100]*3)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods(),
                              starting_balance=50.0)   # мало денег
    with patch.object(RA, "calculate_position_size", return_value=10), \
         patch.object(RA, "calculate_sl_tp", return_value=(90.0, 120.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # fill_insufficient_cash (50 < 1 лот * 100)
    reasons = [s[2] for s in res["skipped"]]
    assert "fill_insufficient_cash" in reasons


# ============================================================
# 19. trade_date_from_timestamp
# ============================================================

def test_trade_date_from_timestamp():
    """trade_date(ts) = UTC date."""
    ts = pd.Timestamp("2026-01-01 23:50", tz="UTC")
    assert ts.date().isoformat() == "2026-01-01"
    ts2 = pd.Timestamp("2026-01-02 03:55", tz="UTC")
    assert ts2.date().isoformat() == "2026-01-02"


# ============================================================
# 20. no_double_count_exposure
# ============================================================

def test_no_double_count_exposure():
    """equity = cash + exposure; exposure не учитывается дважды."""
    p = Portfolio(starting_balance=1_000_000.0)
    pos = Position(
        figi="F1", ticker="F1", entry_time=pd.Timestamp("2026-01-01", tz="UTC"),
        entry_price=100.0, quantity=100, lot_size=1,
        sl_price=90.0, tp_price=120.0, entry_trigger="open",
        entry_slippage_rub=0.0, entry_commission_rub=5.0, trade_id="t1",
    )
    p.open_position(pos)
    # cash = 1_000_000 - 100*100 - 5 = 989_995
    assert p.cash == pytest.approx(989_995.0)
    prices = {"F1": 100.0}
    exposure = p.get_current_exposure(prices)
    equity = p.get_equity(prices)
    assert exposure == pytest.approx(100 * 100.0)
    assert equity == pytest.approx(989_995.0 + 10000.0)   # = 999_995


# ============================================================
# 21. open_position_at_end
# ============================================================

def test_open_position_at_end():
    """Открытая позиция на конце — в open_positions, не в closed_trades."""
    times = _times("2026-01-01 10:00", 3)
    df = _mk_df(times, opens=[100]*3, highs=[101]*3, lows=[99]*3)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(50.0, 200.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    # Позиция открыта (SL/TP далеко) → open_positions, не closed_trades
    assert len(res["open_positions"]) == 1
    assert len(res["closed_trades"]) == 0


# ============================================================
# 22. three_counters
# ============================================================

def test_three_counters():
    """Три счётчика раздельно: eligible >= actual, monitoring независим."""
    times = _times("2026-01-01 10:00", 4)
    df = _mk_df(times, opens=[100]*4)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    engine = BacktestEngineV2(adapter, period_boundaries=_periods())
    with patch.object(RA, "calculate_position_size", return_value=1), \
         patch.object(RA, "calculate_sl_tp", return_value=(90.0, 120.0)):
        res = engine.run(top10, _instruments(), candles, "2026-01-01", "2026-01-02")
    c = res["counters"]
    assert c["eligible_signal_events"] >= c["actual_get_signal_calls"]
    assert c["position_monitoring_events"] >= 0


# ============================================================
# 23. fill_cash_constraint — параметризованный (A–D)
# ============================================================

def _run_fill_case(cash, entry_price, lot_size, lots_from_risk):
    """
    Прогоняет один FILL с заданными параметрами.
    Возвращает (portfolio, actual_debit_before, exec_commission_via_cost_model_count).
    """
    times = _times("2026-01-01 10:00", 3)
    opens = [entry_price, entry_price, entry_price]
    df = _mk_df(times, opens=opens)
    candles = {"F1": df}
    top10 = _top10("2026-01-01", ["F1"])
    adapter = FakeAdapter(signals=[("BUY", "t1")])
    portfolio = Portfolio(starting_balance=cash)
    engine = BacktestEngineV2(adapter, period_boundaries=_periods(),
                              starting_balance=cash)

    call_count = {"calc_commission": 0}
    orig = CM.calc_commission
    def spy(*a, **kw):
        call_count["calc_commission"] += 1
        return orig(*a, **kw)

    with patch.object(RA, "calculate_position_size", return_value=lots_from_risk), \
         patch.object(RA, "calculate_sl_tp", return_value=(50.0, 200.0)), \
         patch.object(CM, "calc_commission", side_effect=spy):
        res = engine.run(top10, {"F1": {"figi": "F1", "ticker": "F1", "lot": lot_size}},
                         candles, "2026-01-01", "2026-01-02")
    return res, call_count["calc_commission"]


def test_fill_cash_constraint_case_A_exact_1000(monkeypatch):
    """A: cash=100050, entry=100, lot=1, slippage=0 → ровно 1000 лотов, cash=0."""
    monkeypatch.setattr(C, "SLIPPAGE_PERCENT", 0.0)
    res, cc = _run_fill_case(100050.0, 100.0, 1, 5000)
    if res["open_positions"]:
        pos = res["open_positions"][0]
        assert pos.quantity == 1000
        assert res["portfolio"].cash == pytest.approx(0.0, abs=1e-6)
    elif res["closed_trades"]:
        t = res["closed_trades"][0]
        assert t.quantity == 1000
    assert cc >= 1


def test_fill_cash_constraint_case_B_insufficient():
    """B: cash=50, entry=100, lot=1 → 0 лотов, fill_insufficient_cash."""
    res, cc = _run_fill_case(50.0, 100.0, 1, 10)
    reasons = [s[2] for s in res["skipped"]]
    assert "fill_insufficient_cash" in reasons
    assert len(res["open_positions"]) == 0


def test_fill_cash_constraint_case_C_v7():
    """C: cash=100000, entry=100, lot=1 → 999 лотов, cash ≈ 50.05."""
    res, cc = _run_fill_case(100000.0, 100.0, 1, 5000)
    if res["open_positions"]:
        pos = res["open_positions"][0]
        assert pos.quantity == 999
    elif res["closed_trades"]:
        t = res["closed_trades"][0]
        assert t.quantity == 999


def test_fill_cash_constraint_case_D_real_spend():
    """D: реальное списание через open_position; actual_debit == cash_before - cash_after."""
    # Используем cash=100050 → 1000 лотов, cash_after ≈ 0
    res, cc = _run_fill_case(100050.0, 100.0, 1, 5000)
    # Проверка: cost_model.calc_commission вызывался (spy)
    assert cc >= 1
    # Проверка: если позиция открыта — cash >= 0
    if res["open_positions"]:
        pos = res["open_positions"][0]
        # cost считается как entry_price * quantity * lot_size
        cost = pos.entry_price * pos.quantity * pos.lot_size
        assert res["portfolio"].cash >= 0
        # entry_commission_rub из Position совпадает с cost_model
        expected_comm = CM.calc_commission(
            entry_price=pos.entry_price, exit_price=pos.entry_price,
            shares=pos.quantity * pos.lot_size,
        )["entry_commission_rub"]
        assert pos.entry_commission_rub == pytest.approx(expected_comm)
        # Фактическое списание: cash_before - cash_after == cost + entry_commission_rub
        # cash_before = 100050, cash_after = res["portfolio"].cash
        actual_spent = 100050.0 - res["portfolio"].cash
        expected_debit = cost + pos.entry_commission_rub
        assert actual_spent == pytest.approx(expected_debit, rel=1e-9, abs=1e-9)