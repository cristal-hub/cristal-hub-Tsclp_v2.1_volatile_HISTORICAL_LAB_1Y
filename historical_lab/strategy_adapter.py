# historical_lab/strategy_adapter.py
# Tsclp_v2.1_volatile — ЭТАП C. Адаптер StrategyManager.
#
# ВАРИАНТ A: get_signal(figi, candles_df, last_price, drop_incomplete)
#            — figi для изолированного режима, Shared игнорирует.

import logging
from typing import Optional, Tuple

import pandas as pd

from . import _config_shim
_config_shim.install()

from strategy import StrategyManager

from . import config_lab as C

log = logging.getLogger(__name__)


class SharedStrategyAdapter:
    """Q1=A: ОДИН StrategyManager на весь прогон."""

    def __init__(self):
        self._sm = StrategyManager()

    def get_signal(self, figi, candles_df, last_price, drop_incomplete=True):
        return self._sm.get_signal(candles_df, last_price, drop_incomplete=drop_incomplete)

    def reset(self):
        self._sm = StrategyManager()

    @property
    def strategy_manager(self):
        return self._sm


class IsolatedStrategyAdapter:
    """Q1 доп.: ОТДЕЛЬНЫЙ StrategyManager на КАЖДЫЙ инструмент."""

    def __init__(self):
        self._by_figi = {}

    def get_signal(self, figi, candles_df, last_price, drop_incomplete=True):
        sm = self._by_figi.get(figi)
        if sm is None:
            sm = StrategyManager()
            self._by_figi[figi] = sm
        return sm.get_signal(candles_df, last_price, drop_incomplete=drop_incomplete)

    def reset(self):
        self._by_figi = {}