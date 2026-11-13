# historical_lab/tests/test_data_loader.py
# Tsclp_v2.1_volatile — ЭТАП A: тесты data_loader (только кэш, без API).

from pathlib import Path

import pytest

from historical_lab import config_lab as C
from historical_lab import data_loader


def test_missing_instruments(monkeypatch, tmp_path):
    """Если instruments.json нет — DataMissingError."""
    monkeypatch.setattr(C, "INSTRUMENTS_FILE", tmp_path / "no_such_instruments.json")
    with pytest.raises(data_loader.DataMissingError):
        data_loader.load_instruments()


def test_missing_5min():
    with pytest.raises(data_loader.DataMissingError):
        data_loader.load_5min("NO_SUCH_FIGI")


def test_missing_daily():
    with pytest.raises(data_loader.DataMissingError):
        data_loader.load_daily("NO_SUCH_FIGI")


def test_require_files():
    missing = data_loader.require_files(["NO_SUCH_FIGI"], kind="5min")
    assert "NO_SUCH_FIGI" in missing