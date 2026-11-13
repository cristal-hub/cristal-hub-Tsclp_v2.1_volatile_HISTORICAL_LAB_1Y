# historical_lab/universe_selector.py
# Tsclp_v2.1_volatile — ЭТАП C. Rolling TOP-10 (воспроизводит screener._do_scan).
#
# B4, B13: воспроизводим ИСХОДНУЮ логику screener.py БЕЗ изменений:
#   - from_ = t - timedelta(days=VOLATILITY_PERIOD_DAYS=30)
#   - interval = DAY
#   - len(candles) < 29 -> пропуск
#   - ATR(14)
#   - avg_turnover = mean(volume[-20:]) * mean(close[-20:])
#   - avg_turnover < MIN_DAILY_TURNOVER_RUB -> пропуск
#   - volatility = (atr / last_close) * 100
#   - sort desc, first TOP_VOLATILE_INSTRUMENTS_COUNT=10
#
# Только локальные дневные свечи (data/daily). НЕ API. НЕ .env.
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import pandas_ta_classic as ta

from . import config_lab as C
from . import data_loader

log = logging.getLogger(__name__)


def _normalize_date(dt) -> pd.Timestamp:
    """Приводит дату к UTC-нормализованному Timestamp (00:00:00)."""
    ts = pd.Timestamp(dt)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.normalize()


def _select_top10_for_date(
    t: pd.Timestamp,
    instruments: list,
    daily_cache: dict,
) -> list:
    """
    Воспроизводит screener._do_scan для даты t.
    Возвращает список словарей: [{figi, ticker, name, volatility, avg_turnover_rub}, ...]
    (отсортировано по volatility desc, первые 10).
    """
    from_dt = t - pd.Timedelta(days=C.VOLATILITY_PERIOD_DAYS)  # 30 календарных дней
    volatility_data = []

    for inst in instruments:
        figi = inst["figi"]
        ticker = inst.get("ticker", figi)
        name = inst.get("name", ticker)

        df_daily = daily_cache.get(figi)
        if df_daily is None or df_daily.empty:
            continue

        # Свечи в окне [from_dt, t] (только данные до t включительно).
        window = df_daily[(df_daily.index >= from_dt) & (df_daily.index <= t)]
        candles = window
        # Воспроизводим len(candles) < 29 (B13: при len=29 -> False -> НЕ пропуск).
        if len(candles) < C.VOLATILITY_PERIOD_DAYS - 1:
            continue

        try:
            atr_series = ta.atr(
                high=candles["high"], low=candles["low"], close=candles["close"],
                length=C.ATR_PERIOD_DAILY,
            )
            if atr_series is None or atr_series.dropna().empty:
                continue
            atr = float(atr_series.dropna().iloc[-1])
            last_close = float(candles["close"].iloc[-1])
            if last_close <= 0 or atr <= 0:
                continue
            # B4.2: воспроизводим mean(volume) * mean(close), НЕ mean(volume*close).
            avg_turnover = (
                float(candles["volume"].tail(20).mean())
                * float(candles["close"].tail(20).mean())
            )
            if avg_turnover < C.MIN_DAILY_TURNOVER_RUB:
                continue
            volatility_data.append({
                "figi": figi,
                "ticker": ticker,
                "name": name,
                "volatility": (atr / last_close) * 100,
                "avg_turnover_rub": avg_turnover,
            })
        except Exception as e:
            log.warning(f"[universe] {ticker}: {e}")
            continue

    if not volatility_data:
        return []
    volatility_data.sort(key=lambda x: x["volatility"], reverse=True)
    return volatility_data[:C.TOP_VOLATILE_INSTRUMENTS_COUNT]


def build_rolling_top10(
    start_date,
    end_date,
    instruments: Optional[list] = None,
    trading_days: Optional[list] = None,
) -> dict:
    """
    Строит rolling TOP-10 для каждой торговой даты в [start_date, end_date].

    Параметры:
      start_date, end_date — границы (строки или Timestamp).
      instruments — список инструментов (по умолчанию из instruments.json).
      trading_days — список дат (по умолчанию — все даты, для которых есть 5-мин свечи
                     хотя бы у одного инструмента; проще — все будние дни).

    Возвращает: { "YYYY-MM-DD": [{figi, ticker, name, volatility, avg_turnover_rub}, ...], ... }
    Сохраняет в data/top10_rolling.json.

    ВАЖНО (B12): если для каких-то дат данных недостаточно — эти даты пропускаются.
    Отчёт о покрытии — в coverage_report.
    """
    if instruments is None:
        instruments = data_loader.load_instruments()

    start_ts = _normalize_date(start_date)
    end_ts = _normalize_date(end_date)
    if end_ts < start_ts:
        raise ValueError(f"end_date ({end_ts}) < start_date ({start_ts})")

    # Загружаем дневные свечи один раз (кэш).
    daily_cache = {}
    missing_daily = []
    for inst in instruments:
        figi = inst["figi"]
        try:
            daily_cache[figi] = data_loader.load_daily(figi)
        except data_loader.DataMissingError:
            missing_daily.append(figi)
            log.warning(f"[universe] Нет дневных свечей: {figi}")
    if missing_daily:
        log.warning(f"[universe] Пропущены (нет daily): {', '.join(missing_daily)}")

    # Определяем торговые дни.
    if trading_days is None:
        # По умолчанию — все будние дни в [start_ts, end_ts].
        all_days = pd.date_range(start=start_ts, end=end_ts, freq="B", tz="UTC")
        # Фильтр: только дни, для которых есть данные (хотя бы у одного инструмента).
        valid_days = []
        for d in all_days:
            has_data = any(
                (not df.empty) and (df.index.min() <= d <= df.index.max())
                for df in daily_cache.values()
            )
            if has_data:
                valid_days.append(d)
        trading_days = valid_days

    result = {}
    skipped_dates = []
    for t in trading_days:
        t_norm = _normalize_date(t)
        top10 = _select_top10_for_date(t_norm, instruments, daily_cache)
        if not top10:
            skipped_dates.append(str(t_norm.date()))
            continue
        result[str(t_norm.date())] = top10

    # Сохраняем.
    C.TOP10_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(C.TOP10_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"[universe] TOP-10 сохранён: {C.TOP10_FILE} "
             f"({len(result)} дат, пропущено {len(skipped_dates)})")
    if skipped_dates:
        log.warning(f"[universe] Даты без TOP-10 (недостаточно данных): {skipped_dates[:10]}...")
    return result


def load_top10_rolling() -> dict:
    """Загружает ранее сохранённый top10_rolling.json."""
    if not C.TOP10_FILE.is_file():
        raise data_loader.DataMissingError(
            f"Нет {C.TOP10_FILE}. Сначала запустите build_rolling_top10()."
        )
    with open(C.TOP10_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def report_top10_coverage(top10: dict) -> dict:
    """Отчёт о покрытии rolling TOP-10 (B12). НЕ сокращает период."""
    if not top10:
        return {"dates": 0, "first": None, "last": None, "tickers": set()}
    dates = sorted(top10.keys())
    tickers = set()
    for lst in top10.values():
        for item in lst:
            tickers.add(item["ticker"])
    return {
        "dates": len(dates),
        "first": dates[0],
        "last": dates[-1],
        "tickers": sorted(tickers),
        "avg_instruments_per_date": round(
            sum(len(v) for v in top10.values()) / len(dates), 2
        ),
    }