# historical_lab/reporting.py
# Tsclp_v2.1_volatile — ЭТАП C. Экспорт отчётов (B.7, п.7 ТЗ).
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.
#
# ВАЖНО: ниже — существующий код (v1). Не изменять.
# В конец файла добавлены функции для v2 (export_equity_curve_csv).
# v1 export_* — без изменений.

import csv
import json
import logging
from pathlib import Path
from typing import List

from . import config_lab as C
from .portfolio import ClosedTrade

log = logging.getLogger(__name__)

# B.7: TRADE_FIELDS — спецификация формата (не импорт logger.py).
TRADE_FIELDS_BASE = [
    "trade_id", "ticker", "figi", "lot_size",
    "side", "signal_reason", "signal_time",
    "price_before_order", "order_send_time", "order_id",
    "execution_status", "requested_lots", "executed_lots",
    "execution_price", "exit_reason", "exit_price", "exit_time",
    "commission_rub", "commission_source", "actual_commission_rub",
    "entry_commission_rub", "exit_commission_rub",
    "slippage_rub", "slippage_percent",
    "gross_pnl_rub", "net_pnl_rub", "cumulative_net_pnl_rub",
    "error_note",
]

# Дополнительные поля backtest (B.7 — задокументированы).
TRADE_FIELDS_LAB = [
    "entry_time", "entry_trigger", "exit_trigger",
    "entry_slippage_rub", "exit_slippage_rub", "total_slippage_rub",
    "total_commission_rub",
    "scenario", "period", "holding_seconds",
]


def _trade_to_row(t: ClosedTrade, cumulative: float) -> dict:
    shares = t.shares
    turnover = (t.entry_price + t.exit_price) * shares
    slip_pct = (t.total_slippage_rub / turnover * 100.0) if turnover > 0 else 0.0
    return {
        "trade_id": t.trade_id, "ticker": t.ticker, "figi": t.figi,
        "lot_size": t.lot_size, "side": "BUY",
        "signal_reason": "", "signal_time": "",
        "price_before_order": "", "order_send_time": "", "order_id": "",
        "execution_status": "FILL", "requested_lots": t.quantity,
        "executed_lots": t.quantity,
        "execution_price": f"{t.entry_price:.4f}",
        "exit_reason": t.exit_reason, "exit_price": f"{t.exit_price:.4f}",
        "exit_time": t.exit_time,
        "commission_rub": f"{t.total_commission_rub:.2f}",
        "commission_source": "model",
        "actual_commission_rub": "",
        "entry_commission_rub": f"{t.entry_commission_rub:.2f}",
        "exit_commission_rub": f"{t.exit_commission_rub:.2f}",
        "slippage_rub": f"{t.total_slippage_rub:+.2f}",
        "slippage_percent": f"{slip_pct:+.3f}",
        "gross_pnl_rub": f"{t.gross_pnl_rub:.2f}",
        "net_pnl_rub": f"{t.net_pnl_rub:.2f}",
        "cumulative_net_pnl_rub": f"{cumulative:.2f}",
        "error_note": "",
        "entry_time": t.entry_time, "entry_trigger": t.entry_trigger,
        "exit_trigger": t.exit_trigger,
        "entry_slippage_rub": f"{t.entry_slippage_rub:.2f}",
        "exit_slippage_rub": f"{t.exit_slippage_rub:.2f}",
        "total_slippage_rub": f"{t.total_slippage_rub:.2f}",
        "total_commission_rub": f"{t.total_commission_rub:.2f}",
        "scenario": t.scenario, "period": t.period,
        "holding_seconds": f"{t.holding_seconds:.0f}",
    }


def _all_fields() -> list:
    seen = set()
    out = []
    for f in TRADE_FIELDS_BASE + TRADE_FIELDS_LAB:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def export_trades_csv(trades: List[ClosedTrade], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = _all_fields()
    cum = 0.0
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for t in trades:
            cum += t.net_pnl_rub
            w.writerow(_trade_to_row(t, cum))
    log.info(f"[reporting] trades.csv: {path} ({len(trades)} сделок)")


def export_signals_csv(signals: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp", "ticker", "figi", "signal", "reason", "regime", "adx", "price", "candles_count"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for s in signals:
            w.writerow({k: s.get(k, "") for k in fields})
    log.info(f"[reporting] signals.csv: {path} ({len(signals)} сигналов)")


def export_skipped_csv(skipped: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["date", "figi", "reason"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for s in skipped:
            date_, figi, reason = s
            w.writerow({"date": date_, "figi": figi, "reason": reason})
    log.info(f"[reporting] skipped_signals.csv: {path} ({len(skipped)} пропущено)")


def export_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"[reporting] JSON: {path}")


def export_scenario_outputs(scenario: str, result: dict, metrics: dict, by_inst: dict, by_period: dict):
    """Экспорт всех отчётов для одного сценария (v1). Не менять."""
    out = C.OUTPUT_DIR / scenario
    export_trades_csv(result["closed_trades"], out / "trades.csv")
    export_skipped_csv(result["skipped"], out / "skipped_signals.csv")
    export_json(metrics, out / "metrics_portfolio.json")
    export_json(by_inst, out / "metrics_by_instrument.json")
    export_json(by_period, out / "metrics_by_period.json")


# ============================================================
# v2: ДОПОЛНЕНИЯ (не влияют на v1)
# ============================================================

def export_equity_curve_csv(equity_curve: List[tuple], path: Path):
    """
    equity_curve.csv — все точки (START + каждая G(ts)).
    equity_curve: [("START", 1000000.0), (ts_str, eq), ...].
    Формат: timestamp;equity.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["timestamp", "equity"])
        for ts_label, eq in equity_curve:
            w.writerow([ts_label, f"{float(eq):.2f}"])
    log.info(f"[reporting] equity_curve.csv: {path} ({len(equity_curve)} точек)")