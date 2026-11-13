# historical_lab/run_historical_lab_v2.py
# Tsclp_v2.1_volatile — отдельный runner v2 (не трогает v1).
#
# Пишет в output/v2/{scenario}/. v1 (output/base/) не перезаписывается.
#
# RESEARCH ONLY. NO LIVE ORDERS. OOS SEALED.
# STRATEGY LOGIC: UNCHANGED.

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
from . import metrics as M
from . import reporting as R
from . import universe_selector as US
from . import strategy_adapter as SA
from .backtest_engine_v2 import BacktestEngineV2

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

OUTPUT_V2 = C.OUTPUT_DIR / "v2"
DIAG_ISOLATED = OUTPUT_V2 / "diagnostic_isolated"


def _parse_date(s):
    return pd.Timestamp(s, tz="UTC").normalize()


def _period_boundaries(start, end):
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


def _export_equity_curve_csv(equity_curve, path: Path):
    """equity_curve.csv — все точки. Первая точка: START,<balance>."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv as _csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f, delimiter=";")
        w.writerow(["timestamp", "equity"])
        for ts_label, eq in equity_curve:
            w.writerow([ts_label, f"{eq:.2f}"])
    log.info(f"[v2] equity_curve.csv: {path} ({len(equity_curve)} точек)")


def _equity_curve_daily(equity_curve):
    """equity_curve_daily — конец каждого торгового дня (последний ts дня)."""
    by_date = {}
    for ts_label, eq in equity_curve:
        if ts_label == "START":
            continue
        try:
            d = str(pd.Timestamp(ts_label).date())
        except Exception:
            continue
        # Последняя точка за день — перезаписываем
        by_date[d] = eq
    return [{"date": d, "equity": float(eq)} for d, eq in sorted(by_date.items())]


def _scenario_dir(scenario: str) -> Path:
    return OUTPUT_V2 / scenario


def _export_result(scenario: str, res: dict):
    """Экспорт trades.csv, skipped_signals.csv, metrics_*.json, equity_curve.csv."""
    out = _scenario_dir(scenario)
    out.mkdir(parents=True, exist_ok=True)

    # trades.csv — формат v1 (через reporting)
    R.export_trades_csv(res["closed_trades"], out / "trades.csv")
    # skipped_signals.csv
    R.export_skipped_csv(res["skipped"], out / "skipped_signals.csv")

    # metrics
    trades = res["closed_trades"]
    m = M.compute_metrics(trades)
    # Доп. поля v2
    m["max_drawdown_equity"] = float(res["max_drawdown_equity"])
    m["max_drawdown_equity_ts"] = res["max_drawdown_equity_ts"]
    m["equity_curve_daily"] = _equity_curve_daily(res["equity_curve"])
    m["open_positions_count"] = len(res["open_positions"])
    m["open_positions"] = [
        {
            "figi": p.figi, "ticker": p.ticker, "entry_time": str(p.entry_time),
            "entry_price": p.entry_price, "quantity": p.quantity,
            "lot_size": p.lot_size, "sl_price": p.sl_price, "tp_price": p.tp_price,
        }
        for p in res["open_positions"]
    ]
    m["counters"] = res["counters"]

    (out / "metrics_portfolio.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    by_inst = M.metrics_by_instrument(trades)
    (out / "metrics_by_instrument.json").write_text(
        json.dumps(by_inst, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    by_period = M.metrics_by_period(trades)
    (out / "metrics_by_period.json").write_text(
        json.dumps(by_period, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    _export_equity_curve_csv(res["equity_curve"], out / "equity_curve.csv")

    log.info(
        f"[v2] {scenario}: trades={m['trades']} net={m['net_profit']:.2f} "
        f"win_rate={m['win_rate']:.1f}% max_dd_eq={m['max_drawdown_equity']:.2f} "
        f"open={len(res['open_positions'])} "
        f"eligible={m['counters']['eligible_signal_events']} "
        f"actual_calls={m['counters']['actual_get_signal_calls']} "
        f"monitoring={m['counters']['position_monitoring_events']}"
    )


def _export_run_manifest(args, instruments_count, top10_coverage, boundaries):
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "v2",
        "requested_start": args.start,
        "requested_end": args.end,
        "scenarios": args.scenarios,
        "starting_balance": C.STARTING_BALANCE,
        "profile": C.PROFILE,
        "period_boundaries": boundaries,
        "instruments_count": instruments_count,
        "top10_coverage": top10_coverage,
        "diagnostic_isolated": args.diagnostic_isolated,
        "sdk_version": "1.51.0",
        "notes": [
            "STRATEGY LOGIC: UNCHANGED",
            "v1 output (output/base/) не перезаписывается",
            "equity_curve.csv содержит все точки (START + каждая G(ts))",
            "max_drawdown_equity — по equity_curve, max_drawdown (v1) — по realized",
        ],
    }
    OUTPUT_V2.mkdir(parents=True, exist_ok=True)
    (OUTPUT_V2 / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    log.info(f"[v2] manifest: {OUTPUT_V2 / 'run_manifest.json'}")


def main():
    parser = argparse.ArgumentParser(description="Tsclp_v2.1_volatile — historical lab v2")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--scenarios", default="base",
                        help="base,stress_0.10,stress_0.20,stress_0.40")
    parser.add_argument("--diagnostic-isolated", action="store_true",
                        help="Доп.: изолированный StrategyManager на FIGI")
    args = parser.parse_args()

    start_ts = _parse_date(args.start)
    end_ts = _parse_date(args.end)
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip() in C.STRESS_SCENARIOS]
    if not scenarios:
        log.error("Нет валидных сценариев")
        sys.exit(1)

    log.info(f"[v2] Старт: {start_ts.date()} → {end_ts.date()}, сценарии={scenarios}")

    # Инструменты
    try:
        instruments = data_loader.load_instruments()
    except data_loader.DataMissingError as e:
        log.error(str(e))
        sys.exit(1)
    instruments_by_figi = {i["figi"]: i for i in instruments}
    figis = list(instruments_by_figi.keys())

    # TOP-10 (переиспользуем существующий; если нет — строим)
    if not C.TOP10_FILE.is_file():
        log.warning("[v2] top10_rolling.json отсутствует — строим")
        top10 = US.build_rolling_top10(start_ts, end_ts, instruments)
    else:
        top10 = json.loads(C.TOP10_FILE.read_text(encoding="utf-8"))
        log.info(f"[v2] top10_rolling.json: {len(top10)} дат")

    # 5M-свечи
    figis_in_top10 = set()
    for lst in top10.values():
        for item in lst:
            figis_in_top10.add(item["figi"])
    candles_by_figi = {}
    missing_5m = []
    for figi in figis_in_top10:
        try:
            candles_by_figi[figi] = data_loader.load_5min(figi)
        except data_loader.DataMissingError:
            missing_5m.append(figi)
    if missing_5m:
        log.warning(f"[v2] нет 5M для {len(missing_5m)} FIGI: {missing_5m[:5]}...")

    boundaries = _period_boundaries(start_ts, end_ts)

    # Прогоны по сценариям
    for scenario in scenarios:
        extra = C.STRESS_SCENARIOS[scenario]
        log.info(f"[v2] Сценарий: {scenario} (extra_slippage={extra})")
        sa = SA.SharedStrategyAdapter()
        engine = BacktestEngineV2(
            strategy_adapter=sa, scenario=scenario,
            extra_slippage=extra, period_boundaries=boundaries,
        )
        res = engine.run(top10, instruments_by_figi, candles_by_figi,
                         args.start, args.end)
        _export_result(scenario, res)

    # Диагностический режим
    if args.diagnostic_isolated:
        log.info("[v2] Диагностический режим: изолированный StrategyManager")
        sa_iso = SA.IsolatedStrategyAdapter()
        engine_iso = BacktestEngineV2(
            strategy_adapter=sa_iso, scenario="base",
            extra_slippage=0.0, period_boundaries=boundaries,
        )
        res_iso = engine_iso.run(top10, instruments_by_figi, candles_by_figi,
                                 args.start, args.end)
        _export_result("diagnostic_isolated", res_iso)
        log.info("[v2] diagnostic_isolated готов")

    # manifest
    top10_coverage = US.report_top10_coverage(top10)
    _export_run_manifest(args, len(instruments), top10_coverage, boundaries)
    log.info("[v2] Готово.")


if __name__ == "__main__":
    main()