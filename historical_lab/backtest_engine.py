# historical_lab/backtest_engine.py
# Tsclp_v2.1_volatile — ЭТАП C. Историческое исполнение (B.2, B.3, Q1, Q2, Q4, Q10).
#
# RESEARCH ONLY. NO API CALLS. NO LIVE ORDERS.

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pandas as pd

from . import config_lab as C
from . import cost_model as CM
from . import data_loader
from . import risk_adapter as RA
from . import strategy_adapter as SA
from .portfolio import Portfolio, Position, ClosedTrade

log = logging.getLogger(__name__)


def _iso(ts) -> str:
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _period_for(date_str: str, boundaries: dict) -> str:
    """DISCOVERY / VALIDATION / OOS по границам (Q4)."""
    d = date_str
    if d <= boundaries["discovery_end"]:
        return "DISCOVERY"
    if d <= boundaries["validation_end"]:
        return "VALIDATION"
    return "OOS"


def _find_first_open_after(df_5min: pd.DataFrame, ts: pd.Timestamp) -> Optional[pd.Timestamp]:
    """Первая 5-мин свеча с time > ts (для входа на open_{t+1}, B.3.1)."""
    after = df_5min.index[df_5min.index > ts]
    if len(after) == 0:
        return None
    return after[0]


def _check_sl_tp_on_candle(
    candle: pd.Series,
    sl: float,
    tp: float,
) -> Optional[str]:
    """
    Проверка SL/TP на ОДНОЙ свече.
    Возвращает "SL" / "TP" / "SL_AND_TP" (SL первым, B.3.4) / None.
    """
    high = float(candle["high"])
    low = float(candle["low"])
    hit_sl = low <= sl
    hit_tp = high >= tp
    if hit_sl and hit_tp:
        return "SL_AND_TP"   # SL первым (B.3.4)
    if hit_sl:
        return "SL"
    if hit_tp:
        return "TP"
    return None


class BacktestEngine:
    def __init__(
        self,
        strategy_adapter,            # SharedStrategyAdapter (Q1=A)
        scenario: str = "base",
        extra_slippage: float = 0.0,
        period_boundaries: Optional[dict] = None,
    ):
        self.sa = strategy_adapter
        self.scenario = scenario
        self.extra_slippage = extra_slippage
        self.period_boundaries = period_boundaries or {
            "discovery_end": "9999-12-31",
            "validation_end": "9999-12-31",
        }

    def run(
        self,
        top10: dict,
        instruments_by_figi: dict,
        candles_by_figi: dict,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        Прогон по top10 (rolling). Возвращает dict с closed_trades и portfolio.
        candles_by_figi — {figi: DataFrame 5min}.
        instruments_by_figi — {figi: {"ticker", "lot", ...}}.
        """
        portfolio = Portfolio()
        dates = sorted(top10.keys())
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]

        skipped = []

        for date_str in dates:
            t_date = pd.Timestamp(date_str, tz="UTC").normalize()
            t_after = t_date + pd.Timedelta(days=1)

            # (1) Проверяем уже открытые позиции на СЕГОДНЯШНИХ свечах.
            self._update_open_positions(portfolio, candles_by_figi, t_date, date_str)

            # (2) Новые сигналы (если нет открытой позиции по figi).
            for item in top10[date_str]:
                figi = item["figi"]
                if portfolio.has_position(figi):
                    continue
                if figi not in candles_by_figi or figi not in instruments_by_figi:
                    continue

                df = candles_by_figi[figi]
                # Окно Q2=A: 2 КАЛЕНДАРНЫХ дня до t_date (включительно).
                window_start = t_date - pd.Timedelta(days=C.CANDLES_LOOKBACK_DAYS)
                df_window = df[(df.index >= window_start) & (df.index <= t_date)]
                if df_window.empty:
                    skipped.append((date_str, figi, "no_window"))
                    continue

                # Сигнальная свеча — последняя доступная на t_date (close).
                last_close = float(df_window["close"].iloc[-1])
                last_time = df_window.index[-1]

                # Сигнал (drop_incomplete=True — как в main.py).
                signal, reason = self.sa.get_signal(figi, df_window, last_close, drop_incomplete=True)
                if signal != "BUY":
                    if signal == "SELL":
                        skipped.append((date_str, figi, f"SELL_ignored({reason})"))
                    continue

                # Вход на первой 5-мин свече t+1 (B.3.1).
                entry_ts = _find_first_open_after(df, last_time)
                if entry_ts is None:
                    skipped.append((date_str, figi, "no_next_candle"))
                    continue

                open_price = float(df.loc[entry_ts, "open"])
                lot = int(instruments_by_figi[figi].get("lot", 1))
                if lot <= 0:
                    skipped.append((date_str, figi, f"bad_lot({lot})"))
                    continue

                # Размер позиции (Q8: friction только для размера, не в P&L).
                date_key = date_str
                trade_count = portfolio.get_trade_count(date_key, figi)
                current_prices = self._current_prices(candles_by_figi, entry_ts)
                current_exposure = portfolio.get_current_exposure(current_prices)

                # entry_price ещё НЕ применён (размер считается от last_close, как в проде).
                lots = RA.calculate_position_size(
                    figi=figi,
                    last_price=last_close,
                    candles_df=df_window,
                    account_balance=portfolio.get_equity(current_prices),
                    lot_size=lot,
                    current_exposure=current_exposure,
                    daily_trade_count=trade_count,
                )
                if lots <= 0:
                    skipped.append((date_str, figi, f"lots=0"))
                    continue

                shares = lots * lot
                entry = CM.apply_entry_slippage(open_price, shares, self.extra_slippage)

                sl, tp = RA.calculate_sl_tp(entry.exec_price, "BUY", df_window)
                if sl is None or tp is None:
                    skipped.append((date_str, figi, "sl_tp_none"))
                    continue

                comm = CM.calc_commission(entry.exec_price, entry.exec_price, shares)  # для входа
                pos = Position(
                    figi=figi, ticker=instruments_by_figi[figi].get("ticker", figi),
                    entry_time=_iso(entry_ts), entry_price=entry.exec_price,
                    quantity=lots, lot_size=lot, sl_price=sl, tp_price=tp,
                    entry_trigger="open", entry_slippage_rub=entry.slippage_rub,
                    entry_commission_rub=comm["entry_commission_rub"],
                    trade_id=uuid.uuid4().hex[:12],
                )
                portfolio.open_position(pos)
                portfolio.increment_trade_count(date_key, figi)   # Q10: только после FILL

                log.info(
                    f"[BUY] {pos.ticker} lots={lots} @ {pos.entry_price:.4f} "
                    f"SL={sl:.4f} TP={tp:.4f} ({date_str})"
                )

        # Конец: закрываем оставшиеся позиции по последней цене (конец периода).
        self._force_close_at_end(portfolio, candles_by_figi, dates[-1] if dates else None)

        return {
            "scenario": self.scenario,
            "portfolio": portfolio,
            "closed_trades": portfolio.closed_trades,
            "skipped": skipped,
        }

    def _current_prices(self, candles_by_figi: dict, ts: pd.Timestamp) -> dict:
        """Цены на момент ts (close последней свечи ≤ ts) по каждому figi."""
        prices = {}
        for figi, df in candles_by_figi.items():
            upto = df[df.index <= ts]
            if not upto.empty:
                prices[figi] = float(upto["close"].iloc[-1])
        return prices

    def _update_open_positions(self, portfolio: Portfolio, candles_by_figi: dict,
                               t_date: pd.Timestamp, date_str: str):
        """Проверка SL/TP на свечах сегодняшнего дня для открытых позиций."""
        for figi in list(portfolio.open_positions.keys()):
            pos = portfolio.open_positions[figi]
            df = candles_by_figi.get(figi)
            if df is None:
                continue
            entry_ts = pd.Timestamp(pos.entry_time)
            # Свечи строго ПОСЛЕ входа (B.3.5: проверка только последующего движения).
            today_candles = df[
                (df.index > entry_ts) & (df.index >= t_date) & (df.index < t_date + pd.Timedelta(days=1))
            ]
            for ts, candle in today_candles.iterrows():
                result = _check_sl_tp_on_candle(candle, pos.sl_price, pos.tp_price)
                if result is None:
                    continue
                self._close_position(portfolio, pos, ts, candle, result, date_str)
                break

    def _close_position(self, portfolio: Portfolio, pos: Position, ts: pd.Timestamp,
                        candle: pd.Series, result: str, date_str: str):
        """Закрытие позиции по SL/TP (B.3.2–B.3.4)."""
        open_price = float(candle["open"])
        # Гэп: если open уже за SL/TP — trigger = open (B.3.3).
        if result in ("SL", "SL_AND_TP"):
            trigger = pos.sl_price
            if open_price < pos.sl_price:   # гэп через SL
                trigger = open_price
                exit_reason = "GAP_SL"
                exit_trigger = "gap_open"
            else:
                exit_reason = "SL"
                exit_trigger = "SL"
        else:  # TP
            trigger = pos.tp_price
            if open_price > pos.tp_price:   # гэп через TP
                trigger = open_price
                exit_reason = "GAP_TP"
                exit_trigger = "gap_open"
            else:
                exit_reason = "TP"
                exit_trigger = "TP"

        exit = CM.apply_exit_slippage(trigger, pos.quantity * pos.lot_size, self.extra_slippage)
        comm_exit = CM.calc_commission(pos.entry_price, exit.exec_price, pos.quantity * pos.lot_size)
        comm_total = {
            "entry_commission_rub": pos.entry_commission_rub,
            "exit_commission_rub": comm_exit["exit_commission_rub"],
            "total_commission_rub": pos.entry_commission_rub + comm_exit["exit_commission_rub"],
        }
        pnl = CM.calc_pnl(pos.entry_price, exit.exec_price, pos.quantity * pos.lot_size, comm_total)

        holding_sec = (ts - pd.Timestamp(pos.entry_time)).total_seconds()
        trade = ClosedTrade(
            trade_id=pos.trade_id, figi=pos.figi, ticker=pos.ticker,
            entry_time=pos.entry_time, entry_price=pos.entry_price,
            exit_time=_iso(ts), exit_price=exit.exec_price,
            quantity=pos.quantity, lot_size=pos.lot_size,
            shares=pos.quantity * pos.lot_size,
            exit_reason=exit_reason, exit_trigger=exit_trigger,
            entry_trigger=pos.entry_trigger,
            entry_slippage_rub=pos.entry_slippage_rub,
            exit_slippage_rub=exit.slippage_rub,
            total_slippage_rub=pos.entry_slippage_rub + exit.slippage_rub,
            entry_commission_rub=comm_total["entry_commission_rub"],
            exit_commission_rub=comm_total["exit_commission_rub"],
            total_commission_rub=comm_total["total_commission_rub"],
            gross_pnl_rub=pnl["gross_pnl_rub"],
            net_pnl_rub=pnl["net_pnl_rub"],
            scenario=self.scenario,
            period=_period_for(date_str, self.period_boundaries),
            holding_seconds=holding_sec,
        )
        portfolio.close_position(pos.figi, trade)
        log.info(
            f"[CLOSE] {pos.ticker} {exit_reason} @ {exit.exec_price:.4f} "
            f"gross={pnl['gross_pnl_rub']:+.2f} net={pnl['net_pnl_rub']:+.2f}"
        )

    def _force_close_at_end(self, portfolio: Portfolio, candles_by_figi: dict, last_date: Optional[str]):
        """Принудительное закрытие в конце периода (по последней цене)."""
        if last_date is None:
            return
        for figi in list(portfolio.open_positions.keys()):
            pos = portfolio.open_positions[figi]
            df = candles_by_figi.get(figi)
            if df is None or df.empty:
                continue
            last_ts = df.index[-1]
            last_close = float(df["close"].iloc[-1])
            candle = df.iloc[-1]
            # Принудительное закрытие — по close, без SL/TP.
            exit = CM.apply_exit_slippage(last_close, pos.quantity * pos.lot_size, self.extra_slippage)
            comm_exit = CM.calc_commission(pos.entry_price, exit.exec_price, pos.quantity * pos.lot_size)
            comm_total = {
                "entry_commission_rub": pos.entry_commission_rub,
                "exit_commission_rub": comm_exit["exit_commission_rub"],
                "total_commission_rub": pos.entry_commission_rub + comm_exit["exit_commission_rub"],
            }
            pnl = CM.calc_pnl(pos.entry_price, exit.exec_price, pos.quantity * pos.lot_size, comm_total)
            trade = ClosedTrade(
                trade_id=pos.trade_id, figi=pos.figi, ticker=pos.ticker,
                entry_time=pos.entry_time, entry_price=pos.entry_price,
                exit_time=_iso(last_ts), exit_price=exit.exec_price,
                quantity=pos.quantity, lot_size=pos.lot_size,
                shares=pos.quantity * pos.lot_size,
                exit_reason="FORCED_END", exit_trigger="close",
                entry_trigger=pos.entry_trigger,
                entry_slippage_rub=pos.entry_slippage_rub,
                exit_slippage_rub=exit.slippage_rub,
                total_slippage_rub=pos.entry_slippage_rub + exit.slippage_rub,
                entry_commission_rub=comm_total["entry_commission_rub"],
                exit_commission_rub=comm_total["exit_commission_rub"],
                total_commission_rub=comm_total["total_commission_rub"],
                gross_pnl_rub=pnl["gross_pnl_rub"],
                net_pnl_rub=pnl["net_pnl_rub"],
                scenario=self.scenario,
                period=_period_for(last_date, self.period_boundaries),
                holding_seconds=(last_ts - pd.Timestamp(pos.entry_time)).total_seconds(),
            )
            portfolio.close_position(pos.figi, trade)
            log.info(f"[FORCED_END] {pos.ticker} @ {exit.exec_price:.4f} net={pnl['net_pnl_rub']:+.2f}")