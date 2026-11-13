# historical_lab/tests/test_gap_through_tp.py
# B.9 #7: гэп через TP → trigger = open.

import pytest

from historical_lab import cost_model as CM


def test_gap_through_tp_trigger_is_open():
    tp = 105.0
    open_price = 110.0
    trigger = open_price if open_price > tp else tp
    assert trigger == open_price
    r = CM.apply_exit_slippage(trigger, shares=10)
    assert r.trigger_price == open_price
    assert r.exec_price < open_price