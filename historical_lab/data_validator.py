# historical_lab/data_validator.py
# Tsclp_v2.1_volatile — ЭТАП C. Валидация исторических данных.
#
# Проверяет: дубликаты, пропуски, OHLCV-аномалии, порядок.
# НЕ меняет данные. Только отчёт.
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import logging
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)


def validate_5min(df: pd.DataFrame, figi: str = "?") -> dict:
    """
    Проверяет 5-мин свечи. Возвращает отчёт (dict). Данные не меняет.
    """
    report = {
        "figi": figi,
        "len": int(len(df)),
        "first": None,
        "last": None,
        "duplicates": 0,
        "nan_ohlc": 0,
        "zero_or_negative": 0,
        "high_lt_low": 0,
        "close_outside_hl": 0,
        "gaps": [],
        "warnings": [],
    }
    if df is None or df.empty:
        report["warnings"].append("empty DataFrame")
        return report

    report["first"] = str(df.index.min())
    report["last"] = str(df.index.max())

    dup_mask = df.index.duplicated(keep=False)
    report["duplicates"] = int(dup_mask.sum())

    nan_mask = df[["open", "high", "low", "close"]].isna().any(axis=1)
    report["nan_ohlc"] = int(nan_mask.sum())

    bad_price = ((df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0))
    report["zero_or_negative"] = int(bad_price.sum())

    hl_bad = df["high"] < df["low"]
    report["high_lt_low"] = int(hl_bad.sum())

    close_bad = (df["close"] > df["high"]) | (df["close"] < df["low"])
    report["close_outside_hl"] = int(close_bad.sum())

    # Пропуски: разница между соседними свечами > 2 * медианного интервала
    if len(df) > 2:
        diffs = df.index.to_series().diff().dropna()
        median_diff = diffs.median()
        if median_diff.total_seconds() > 0:
            gap_mask = diffs > median_diff * 2
            for ts, diff in diffs[gap_mask].items():
                report["gaps"].append({
                    "at": str(ts),
                    "gap_seconds": float(diff.total_seconds()),
                    "median_seconds": float(median_diff.total_seconds()),
                })

    for key in ("duplicates", "nan_ohlc", "zero_or_negative", "high_lt_low", "close_outside_hl"):
        if report[key] > 0:
            report["warnings"].append(f"{key}={report[key]}")

    if len(report["gaps"]) > 10:
        report["warnings"].append(f"gaps>10 ({len(report['gaps'])})")

    return report


def validate_daily(df: pd.DataFrame, figi: str = "?") -> dict:
    """Проверяет дневные свечи. Аналогично validate_5min."""
    return validate_5min(df, figi=figi)