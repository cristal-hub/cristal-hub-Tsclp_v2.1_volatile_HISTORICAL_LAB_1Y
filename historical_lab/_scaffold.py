# historical_lab/_scaffold.py
# Tsclp_v2.1_volatile — ЭТАП C. Каркас файлов лаборатории.
#
# Создаёт ПУСТЫЕ файлы (если нет). Существующие НЕ перезаписывает.
# Не трогает Tsclp_v2.1_volatile. Только historical_lab.
#
# Запуск:
#   cd C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y
#   C:\Users\Cristal\AppData\Local\Programs\Python\Python314\python.exe historical_lab\_scaffold.py
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import os
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent

DIRS = [
    LAB_ROOT / "data" / "candles",
    LAB_ROOT / "data" / "daily",
    LAB_ROOT / "output",
    LAB_ROOT / "tests",
    LAB_ROOT / "_snapshot",
]

FILES = [
    LAB_ROOT / "__init__.py",
    LAB_ROOT / "config_lab.py",
    LAB_ROOT / "_config_shim.py",
    LAB_ROOT / "data_loader.py",
    LAB_ROOT / "data_validator.py",
    LAB_ROOT / "universe_selector.py",
    LAB_ROOT / "strategy_adapter.py",
    LAB_ROOT / "risk_adapter.py",
    LAB_ROOT / "cost_model.py",
    LAB_ROOT / "portfolio.py",
    LAB_ROOT / "backtest_engine.py",
    LAB_ROOT / "metrics.py",
    LAB_ROOT / "reporting.py",
    LAB_ROOT / "run_historical_lab.py",
    LAB_ROOT / "README.md",
    LAB_ROOT / "tests" / "__init__.py",
    LAB_ROOT / "tests" / "test_no_lookahead.py",
    LAB_ROOT / "tests" / "test_execution_after_close.py",
    LAB_ROOT / "tests" / "test_commission.py",
    LAB_ROOT / "tests" / "test_slippage.py",
    LAB_ROOT / "tests" / "test_sl_tp_same_candle.py",
    LAB_ROOT / "tests" / "test_gap_through_sl.py",
    LAB_ROOT / "tests" / "test_gap_through_tp.py",
    LAB_ROOT / "tests" / "test_entry_open_then_subsequent.py",
    LAB_ROOT / "tests" / "test_no_duplicate_slippage.py",
    LAB_ROOT / "tests" / "test_timestamps_sessions.py",
    LAB_ROOT / "tests" / "test_no_duplicate_trades.py",
    LAB_ROOT / "tests" / "test_portfolio_exposure.py",
    LAB_ROOT / "tests" / "test_no_trading_imports.py",
    LAB_ROOT / "tests" / "test_risk_adapter_matches_source.py",
    LAB_ROOT / "tests" / "test_universe_no_lookahead.py",
    LAB_ROOT / "tests" / "test_max_trades_counter.py",
    LAB_ROOT / "tests" / "test_starting_balance.py",
    LAB_ROOT / "tests" / "test_data_loader.py",
]


def main():
    print("=" * 70)
    print("Tsclp_v2.1_volatile — каркас laboratory")
    print("=" * 70)
    created = 0
    skipped = 0
    for d in DIRS:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            print(f"[DIR ] + {d}")
    for f in FILES:
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("", encoding="utf-8")
            print(f"[FILE] + {f}")
            created += 1
        else:
            print(f"[FILE] = {f} (уже есть, не трогаю)")
            skipped += 1
    print()
    print(f"Создано: {created}, пропущено (уже есть): {skipped}")
    print()
    print("Дальше: вставьте код в каждый файл. Существующие не перезаписываются.")


if __name__ == "__main__":
    main()