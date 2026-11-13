# historical_lab/tests/test_no_trading_imports.py
# B.9 #13: нет импорта main, execution, tinkoff_client, telegram_bot.

import sys
import subprocess


FORBIDDEN = ["tinkoff_client", "telegram_bot", "main", "execution", "dotenv", "t_tech"]


def test_no_trading_modules_imported():
    code = (
        "import sys; "
        "from historical_lab import config_lab, data_loader, data_validator, "
        "universe_selector, strategy_adapter, risk_adapter, cost_model, portfolio, "
        "backtest_engine, metrics, reporting; "
        "print('|'.join(m for m in ['tinkoff_client','telegram_bot','main','execution','dotenv','t_tech'] if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
    )
    assert result.returncode == 0, result.stderr
    forbidden_found = [x for x in result.stdout.strip().split("|") if x]
    assert forbidden_found == [], f"Запрещённые модули импортированы: {forbidden_found}"