# historical_lab — Tsclp_v2.1_volatile

Историческая исследовательская лаборатория для стратегии `Tsclp_v2.1_volatile`
(профиль `CONSERVATIVE`, TOP-10 MOEX, 5-мин свечи, ~1 год).

**RESEARCH ONLY. ONLY T-INVEST SANDBOX. NO LIVE ORDERS. NO REAL MONEY.**

---

## 1. Что это

Лаборатория воспроизводит логику `main.py` / `strategy.py` / `risk_manager.py` /
`screener.py` на исторических данных, без обращения к T-Invest API,
без отправки заявок, без чтения `.env` и токенов.

**STRATEGY LOGIC: UNCHANGED.**

---

## 2. Структура

- `data/candles/{figi}.parquet|.csv` — 5-мин свечи (пользователь)
- `data/daily/{figi}.parquet|.csv` — дневные свечи (пользователь)
- `data/instruments.json` — список инструментов (пользователь)
- `data/top10_rolling.json` — генерируется `universe_selector`
- `output/base/` — базовый сценарий
- `output/stress_0.10/`, `output/stress_0.20/`, `output/stress_0.40/` — стресс-сценарии
- `output/diagnostic_isolated/` — Q1 доп.
- `output/coverage_report.json` — отчёт о покрытии (B12)
- `output/top10_coverage.json` — отчёт о rolling TOP-10
- `output/run_manifest.json` — версия, параметры, границы периодов

Модули:

- `config_lab.py` — константы (без `.env`)
- `_config_shim.py` — подмена `config` для `strategy.py`
- `data_loader.py` — только локальный кэш
- `data_validator.py` — проверка OHLCV
- `universe_selector.py` — rolling TOP-10
- `strategy_adapter.py` — `SharedStrategyAdapter` (Q1=A)
- `risk_adapter.py` — копия формул `RiskManager` (B5)
- `cost_model.py` — комиссия + slippage (B.3)
- `portfolio.py` — виртуальный портфель (B.6)
- `backtest_engine.py` — ядро (B.2, B.3)
- `metrics.py` — статистика
- `reporting.py` — CSV/JSON
- `run_historical_lab.py` — главный скрипт
- `tests/` — 38 тестов

---

## 3. Формат входных данных

### 3.1. `data/instruments.json`

JSON-массив:

```json
[
  {"figi": "BBG004730N88", "ticker": "SBER", "name": "Сбербанк", "lot": 1, "real_exchange": 1, "currency": "rub"},
  {"figi": "TCS00A106YF0", "ticker": "VKCO", "name": "VK", "lot": 1, "real_exchange": 1, "currency": "rub"}
]