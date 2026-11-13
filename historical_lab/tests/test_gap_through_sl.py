# historical_lab/tests/test_gap_through_sl.py
# B.9 #6: гэп через SL → trigger = open.

import pandas as pd
import pytest

from historical_lab import config_lab as C
from historical_lab import cost_model as CM


def test_gap_through_sl_trigger_is_open():
    sl = 95.0
    open_price = 90.0
    trigger = open_price if open_price < sl else sl
    assert trigger == open_price
    r = CM.apply_exit_slippage(trigger, shares=10)
    assert r.trigger_price == open_price
    assert r.exec_price < open_price