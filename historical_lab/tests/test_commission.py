# historical_lab/tests/test_commission.py
# B.9 #3: total = entry + exit; не 2×.

import pytest

from historical_lab import config_lab as C
from historical_lab import cost_model as CM


def test_commission_total_is_sum():
    c = CM.calc_commission(100.0, 105.0, shares=10)
    assert c["total_commission_rub"] == pytest.approx(
        c["entry_commission_rub"] + c["exit_commission_rub"]
    )


def test_commission_not_doubled():
    """total не 2× от суммы (проверка отсутствия двойного учёта)."""
    c = CM.calc_commission(100.0, 100.0, shares=10)
    expected = 2 * C.COMMISSION_PER_SIDE * 100.0 * 10
    assert c["total_commission_rub"] == pytest.approx(expected)
    assert c["total_commission_rub"] != pytest.approx(2 * expected)


def test_commission_proportional_to_shares():
    c1 = CM.calc_commission(100.0, 105.0, shares=10)
    c2 = CM.calc_commission(100.0, 105.0, shares=20)
    assert c2["total_commission_rub"] == pytest.approx(2 * c1["total_commission_rub"])