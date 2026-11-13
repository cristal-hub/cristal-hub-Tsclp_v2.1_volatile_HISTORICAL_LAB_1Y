# historical_lab/tests/test_slippage.py
# B.9 #4: знак (положительное = неблагоприятное).

import pytest

from historical_lab import cost_model as CM


def test_entry_slippage_positive():
    r = CM.apply_entry_slippage(100.0, shares=10)
    assert r.exec_price > 100.0
    assert r.slippage_rub > 0


def test_exit_slippage_positive():
    r = CM.apply_exit_slippage(105.0, shares=10)
    assert r.exec_price < 105.0
    assert r.slippage_rub > 0


def test_entry_slippage_value():
    r = CM.apply_entry_slippage(100.0, shares=10)
    assert r.exec_price == pytest.approx(100.0 * 1.0002)
    assert r.slippage_rub == pytest.approx(0.02 * 10)


def test_exit_slippage_value():
    r = CM.apply_exit_slippage(105.0, shares=10)
    assert r.exec_price == pytest.approx(105.0 * 0.9998)
    assert r.slippage_rub == pytest.approx(0.021 * 10)