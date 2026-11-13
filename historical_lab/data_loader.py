# historical_lab/data_loader.py
# Tsclp_v2.1_volatile — ЭТАП C. Загрузка данных ТОЛЬКО из локального кэша.
#
# ВАРИАНТ C (B10–B11): нет API, нет .env, нет tinkoff_client.
# Если данных нет — сообщает, какие FIGI и даты нужны.
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from . import config_lab as C

log = logging.getLogger(__name__)


class DataMissingError(RuntimeError):
    pass


def _read_table(path: Path) -> Optional[pd.DataFrame]:
    """Читает parquet или CSV. Возвращает None, если файла нет."""
    if path.suffix == ".parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            raise DataMissingError(
                f"Для parquet нужен pyarrow: pip install pyarrow. Файл: {path}"
            )
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise DataMissingError(f"Неподдерживаемый формат: {path}")


def _find_file(figi: str, directory: Path) -> Optional[Path]:
    for ext in (".parquet", ".csv"):
        p = directory / f"{figi}{ext}"
        if p.is_file():
            return p
    return None


def load_instruments() -> list:
    """Список инструментов (figi, ticker, lot, ...)."""
    if not C.INSTRUMENTS_FILE.is_file():
        raise DataMissingError(
            f"Нет {C.INSTRUMENTS_FILE}. Нужен JSON-список инструментов: "
            f'[{{"figi": "...", "ticker": "...", "lot": 1, "real_exchange": 1, "currency": "rub"}}, ...]'
        )
    with open(C.INSTRUMENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise DataMissingError(f"{C.INSTRUMENTS_FILE} пуст или не список.")
    return data


def load_5min(figi: str) -> pd.DataFrame:
    """
    5-мин свечи. Колонки: time (index, UTC), open, high, low, close, volume.
    Если файла нет — DataMissingError с указанием, что нужно.
    """
    p = _find_file(figi, C.CANDLES_DIR)
    if p is None:
        raise DataMissingError(
            f"Нет 5-мин свечей для {figi}. "
            f"Нужен файл: {C.CANDLES_DIR / (figi + '.parquet')} (или .csv). "
            f"Колонки: time, open, high, low, close, volume."
        )
    df = _read_table(p)
    if df is None or df.empty:
        raise DataMissingError(f"Файл {p} пуст.")
    if "time" not in df.columns:
        raise DataMissingError(f"{p}: нет колонки 'time'.")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            raise DataMissingError(f"{p}: нет колонки '{col}'.")
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["high", "low", "close"])
    return df


def load_daily(figi: str) -> pd.DataFrame:
    """
    Дневные свечи (для скринера). Колонки: date (index), open, high, low, close, volume.
    Если файла нет — DataMissingError.
    """
    p = _find_file(figi, C.DAILY_DIR)
    if p is None:
        raise DataMissingError(
            f"Нет дневных свечей для {figi}. "
            f"Нужен файл: {C.DAILY_DIR / (figi + '.parquet')} (или .csv). "
            f"Колонки: date, open, high, low, close, volume."
        )
    df = _read_table(p)
    if df is None or df.empty:
        raise DataMissingError(f"Файл {p} пуст.")
    date_col = "date" if "date" in df.columns else "time"
    if date_col not in df.columns:
        raise DataMissingError(f"{p}: нет колонки 'date' (или 'time').")
    df[date_col] = pd.to_datetime(df[date_col], utc=True).dt.normalize()
    df = df.set_index(date_col).sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            raise DataMissingError(f"{p}: нет колонки '{col}'.")
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["high", "low", "close"])
    return df


def require_files(figis: list, kind: str = "5min") -> list:
    """
    Проверяет наличие файлов для всех FIGI. Возвращает список отсутствующих.
    kind = "5min" | "daily".
    """
    directory = C.CANDLES_DIR if kind == "5min" else C.DAILY_DIR
    missing = []
    for figi in figis:
        if _find_file(figi, directory) is None:
            missing.append(figi)
    return missing


def coverage_report(figis: list) -> dict:
    """
    Отчёт о покрытии (B12): для каждого FIGI — наличие, диапазон дат, len.
    НЕ сокращает период. Только сообщает.
    """
    report = {"5min": {}, "daily": {}, "missing": []}
    for figi in figis:
        p5 = _find_file(figi, C.CANDLES_DIR)
        pd_ = _find_file(figi, C.DAILY_DIR)
        if p5 is None and pd_ is None:
            report["missing"].append(figi)
            continue
        if p5 is not None:
            df = load_5min(figi)
            report["5min"][figi] = {
                "path": str(p5),
                "len": int(len(df)),
                "first": str(df.index.min()),
                "last": str(df.index.max()),
            }
        if pd_ is not None:
            df = load_daily(figi)
            report["daily"][figi] = {
                "path": str(pd_),
                "len": int(len(df)),
                "first": str(df.index.min()),
                "last": str(df.index.max()),
            }
    return report