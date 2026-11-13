# historical_lab/run_historical_lab.py
# Tsclp_v2.1_volatile — ЭТАП C. Главный скрипт лаборатории.
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS. NO REAL MONEY.

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config_lab as C
from . import data_loader
from . import data_validator
from . import universe_selector as US
from . import strategy_adapter as SA
from . import metrics as M
from . import reporting as R
from .backtest_engine import BacktestEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


def _parse_date(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC").normalize()


def _period_boundaries(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """
    Q4: DISCOVERY — первые 6 мес, VALIDATION — след. 3 мес, OOS — последние 3 мес.
    Границы — от start (не от end). Если доступный диапазон < 12 мес —
    сообщаем, но НЕ сокращаем молча (B12).
    """
    total_days = (end - start).days
    disc_end = start + pd.Timedelta(days=182)
    val_end = disc_end + pd.Timedelta(days=91)
    if val_end >= end:
        log.warning(
            f"[periods] Доступно {total_days} дней — меньше 12 мес. "
            f"OOS может быть короче. Границы: DISCOVERY_end={disc_end.date()}, "
            f"VALIDATION_end={val_end.date()}, end={end.date()}"
        )
    return {
        "discovery_end": str(disc_end.date()),
        "validation_end": str(val_end.date()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD (начало)")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD (конец)")
    parser.add_argument("--scenarios", default="base", help="base,stress_0.10,stress_0.20,stress_0.40")
    parser.add_argument("--diagnostic-isolated", action="store_true",
                        help="Доп.: изолированный StrategyManager (Q1 доп.)")
    args = parser.parse_args()

    start_ts = _parse_date(args.start)
    end_ts = _parse_date(args.end)
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip() in C.STRESS_SCENARIOS]

    log.info(f"[lab] Старт: {start_ts.date()} → {end_ts.date()}, сценарии={scenarios}")

    # 1. Инструменты
    try:
        instruments = data_loader.load_instruments()
    except data_loader.DataMissingError as e:
        log.error(str(e))
        sys.exit(1)
    figis = [i["figi"] for i in instruments]
    instruments_by_figi = {i["figi"]: i for i in instruments}

    # 2. Покрытие (B12)
    coverage = data_loader.coverage_report(figis)
    R.export_json(coverage, C.OUTPUT_DIR / "coverage_report.json")
    if coverage["missing"]:
        log.warning(f"[lab] Нет данных для: {coverage['missing']}")

    # 3. 5-мин свечи (кэш)
    candles_5min = {}
    for figi in figis:
        try:
            candles_5min[figi] = data_loader.load_5min(figi)
        except data_loader.DataMissingError:
            log.warning(f"[lab] Нет 5min для {figi}")

    # 4. Дневные — для скринера
    daily_cache = {}
    for figi in figis:
        try:
            daily_cache[figi] = data_loader.load_daily(figi)
        except data_loader.DataMissingError:
            pass

    # 5. Rolling TOP-10
    log.info("[lab] Строим rolling TOP-10...")
    top10 = US.build_rolling_top10(start_ts, end_ts, instruments, trading_days=None)
    cov = US.report_top10_coverage(top10)
    R.export_json(cov, C.OUTPUT_DIR / "top10_coverage.json")
    log.info(f"[lab] TOP-10: {cov['dates']} дат, {cov['first']} → {cov['last']}")

    boundaries = _period_boundaries(start_ts, end_ts)

    # 6. Прогоны
    for scenario in scenarios:
        extra = C.STRESS_SCENARIOS[scenario]
        log.info(f"[lab] Сценарий: {scenario} (extra_slippage={extra})")
        # Q1=A: ОДИН StrategyManager на прогон.
        sa = SA.SharedStrategyAdapter()
        engine = BacktestEngine(
            strategy_adapter=sa, scenario=scenario,
            extra_slippage=extra, period_boundaries=boundaries,
        )
        result = engine.run(top10, instruments_by_figi, candles_5min)
        trades = result["closed_trades"]
        m = M.portfolio_metrics(trades)
        by_inst = M.metrics_by_instrument(trades)
        by_period = M.metrics_by_period(trades)
        R.export_scenario_outputs(scenario, result, m, by_inst, by_period)
        log.info(f"[lab] {scenario}: сделок={m['trades']} net={m['net_profit']:.2f}₽ "
                 f"win_rate={m['win_rate']:.1f}%")

    # 7. Диагностическое сравнение (Q1 доп.)
    if args.diagnostic_isolated:
        log.info("[lab] Диагностический режим: изолированный StrategyManager")
        sa_iso = SA.IsolatedStrategyAdapter()
        engine = BacktestEngine(
            strategy_adapter=sa_iso, scenario="base",
            extra_slippage=0.0, period_boundaries=boundaries,
        )
        result = engine.run(top10, instruments_by_figi, candles_5min)
        trades = result["closed_trades"]
        m = M.portfolio_metrics(trades)
        R.export_json(m, C.OUTPUT_DIR / "diagnostic_isolated" / "metrics_portfolio.json")
        log.info(f"[lab] diagnostic_isolated: сделок={m['trades']} net={m['net_profit']:.2f}₽")

    # 8. Manifest
    R.export_json({
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "start": str(start_ts.date()),
        "end": str(end_ts.date()),
        "scenarios": scenarios,
        "starting_balance": C.STARTING_BALANCE,
        "profile": C.PROFILE,
        "period_boundaries": boundaries,
    }, C.OUTPUT_DIR / "run_manifest.json")
    log.info("[lab] Готово.")


if __name__ == "__main__":
    main()