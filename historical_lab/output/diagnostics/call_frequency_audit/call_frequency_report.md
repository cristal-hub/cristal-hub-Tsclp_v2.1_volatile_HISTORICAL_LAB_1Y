# Call Frequency Audit — Tsclp_v2.1_volatile historical lab

## Установлено (факты)

| Параметр | Значение |
|---|---|
| FIGI в TOP-10 за год | 60 |
| Торговых дат (rolling TOP-10) | 169 |
| Вызовов `StrategyManager.get_signal` | **1685** |
| Вызовов на (дата, FIGI) | **1** |
| Calls per date | 8–10 (число FIGI в TOP-10 на дату) |

**Пример (SMLT / BBG00F6NKQX3, 2026-03-02):**
- Доступных 5M-свечей в окне `[t-2д, t]`: **464**
- Вызовов `get_signal`: **1** (на последней свече дня)

## Причина

Внешний цикл `backtest_engine.py` проходит по **торговым датам**
(`for date_str in dates`), не по **5M-свечам**. `get_signal` вызывается
**1 раз на (дата, FIGI)** — на **последней** 5M-свече дня `t`.

## Следствие

Текущий historical backtest **не воспроизводит внутридневную частоту
проверки** production `main.py`.

## C.2. Production frequency — NOT MEASURED

- Лог production **не сохранён** (`main.py` пишет в консоль, не в файл).
- **Фактическая частота `get_signal` в production не измерена.**
- `TRADING_CYCLE_SECONDS=30` → **~2880 циклов/сутки** — **оценка по коду**,
  **не** подтверждённое количество вызовов стратегии.
- **288× — предварительная оценка**, **не** доказанный коэффициент.
- Для точного измерения требуется лог за 1 день
  (`python main.py *> main_YYYYMMDD.log`).

## Вывод

- **7 сделок за год** — не сопоставимы с production **по частоте проверок**.
- **CONSERVATIVE** — не единственная причина (частота — тоже).
- Для корректного сравнения — нужен `backtest_engine_v2` (события = 5M-свечи).

STRATEGY LOGIC: UNCHANGED. RESEARCH ONLY. NO LIVE ORDERS.