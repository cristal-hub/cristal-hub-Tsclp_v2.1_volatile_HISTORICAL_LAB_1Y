# historical_lab/tests/test_download_market_data.py
# Tsclp_v2.1_volatile — тесты загрузчика (моки, без API).

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from historical_lab.tools import download_market_data as D


class FakeQuotation:
    def __init__(self, units, nano=0):
        self.units = units
        self.nano = nano


class FakeCandle:
    def __init__(self, time, o, h, l, c, v, is_complete=True):
        self.time = time
        self.open = FakeQuotation(int(o), int((o % 1) * 1e9))
        self.high = FakeQuotation(int(h), int((h % 1) * 1e9))
        self.low = FakeQuotation(int(l), int((l % 1) * 1e9))
        self.close = FakeQuotation(int(c), int((c % 1) * 1e9))
        self.volume = v
        self.is_complete = is_complete


def test_candles_to_rows_skips_incomplete():
    candles = [
        FakeCandle(datetime(2026, 1, 1, tzinfo=timezone.utc), 100, 101, 99, 100.5, 1000, True),
        FakeCandle(datetime(2026, 1, 2, tzinfo=timezone.utc), 100, 101, 99, 100.5, 1000, False),
        FakeCandle(datetime(2026, 1, 3, tzinfo=timezone.utc), 100, 101, 99, 100.5, 1000, True),
    ]
    rows, received, skipped, saved = D.candles_to_rows(candles)
    assert received == 3
    assert skipped == 1
    assert saved == 2
    assert len(rows) == 2


def test_candles_to_rows_utc():
    candles = [FakeCandle(datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc), 100, 101, 99, 100, 10, True)]
    rows, *_ = D.candles_to_rows(candles)
    assert "2026-01-01" in rows[0]["date"]
    assert "+00:00" in rows[0]["date"]


def test_save_csv_atomic(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DAILY_DIR", tmp_path)
    rows = [{"date": "2026-01-01T00:00:00+00:00", "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.5, "volume": 1000}]
    p = tmp_path / "FIGI.csv"
    D.save_csv_atomic(rows, p, ["date", "open", "high", "low", "close", "volume"])
    assert p.is_file()
    with open(p, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 1
    assert reader[0]["close"] == "100.5"


def test_no_token_raises(monkeypatch):
    monkeypatch.delenv("TINKOFF_READONLY_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        D._get_token()


def test_token_from_env(monkeypatch):
    monkeypatch.setenv("TINKOFF_READONLY_TOKEN", "fake-token")
    assert D._get_token() == "fake-token"


def test_no_trading_imports():
    import subprocess
    code = (
        "import sys; "
        "sys.path.insert(0, r'C:\\Users\\Cristal\\Desktop\\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y'); "
        "from historical_lab.tools import download_market_data; "
        "print('|'.join(m for m in ['main','execution','tinkoff_client','telegram_bot'] if m in sys.modules))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""


def test_is_loaded_ok(tmp_path, monkeypatch):
    """Достаточно строк (>= 200) и покрытие диапазона."""
    monkeypatch.setattr(D, "DAILY_DIR", tmp_path)
    p = tmp_path / "FIGI.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
        w.writeheader()
        for i in range(250):
            from datetime import timedelta
            d = datetime(2025, 11, 10, tzinfo=timezone.utc) + timedelta(days=i)
            w.writerow({"date": d.isoformat(), "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000})
    start = datetime(2025, 11, 10, tzinfo=timezone.utc)
    end = datetime(2025, 11, 10, tzinfo=timezone.utc) + __import__("datetime").timedelta(days=249)
    assert D._is_loaded_ok("FIGI", start, end) is True


def test_is_loaded_ok_too_few_rows(tmp_path, monkeypatch):
    """< 200 строк → False."""
    monkeypatch.setattr(D, "DAILY_DIR", tmp_path)
    p = tmp_path / "FIGI.csv"
    p.write_text("date,open,high,low,close,volume\n"
                 "2025-11-10T00:00:00+00:00,100,101,99,100.5,1000\n"
                 "2026-11-10T00:00:00+00:00,100,101,99,100.5,1000\n", encoding="utf-8")
    start = datetime(2025, 11, 10, tzinfo=timezone.utc)
    end = datetime(2026, 11, 10, tzinfo=timezone.utc)
    assert D._is_loaded_ok("FIGI", start, end) is False


def test_get_top10_figis(tmp_path, monkeypatch):
    """Объединение FIGI из top10_rolling.json."""
    top10 = {
        "2026-01-01": [{"figi": "F1", "ticker": "T1"}, {"figi": "F2", "ticker": "T2"}],
        "2026-01-02": [{"figi": "F2", "ticker": "T2"}, {"figi": "F3", "ticker": "T3"}],
    }
    import json
    p = tmp_path / "top10.json"
    p.write_text(json.dumps(top10), encoding="utf-8")
    monkeypatch.setattr(D, "TOP10_FILE", p)
    figis = D._get_top10_figis()
    assert set(figis) == {"F1", "F2", "F3"}