# historical_lab/tests/test_no_duplicate_slippage.py
# B.9 #9: slippage не вычитается из net_pnl повторно.

import pytest

from historical_lab import cost_model as CM


def test_slippage_not_subtracted_twice():
    entry = CM.apply_entry_slippage(100.0, shares=10)
    exit_ = CM.apply_exit_slippage(105.0, shares=10)
    comm = CM.calc_commission(entry.exec_price, exit_.exec_price, shares=10)
    pnl = CM.calc_pnl(entry.exec_price, exit_.exec_price, shares=10, commission=comm)
    # net = gross - total_commission (slippage уже в ценах)
    expected_gross = (exit_.exec_price - entry.exec_price) * 10
    expected_net = expected_gross - comm["total_commission_rub"]
    assert pnl["gross_pnl_rub"] == pytest.approx(expected_gross)
    assert pnl["net_pnl_rub"] == pytest.approx(expected_net)
    # Проверка: net НЕ равен gross - commission - slippage
    wrong = expected_gross - comm["total_commission_rub"] - entry.slippage_rub - exit_.slippage_rub
    assert pnl["net_pnl_rub"] != pytest.approx(wrong)