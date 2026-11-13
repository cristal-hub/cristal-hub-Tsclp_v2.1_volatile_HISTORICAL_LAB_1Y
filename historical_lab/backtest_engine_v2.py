# historical_lab/backtest_engine_v2.py
# Tsclp_v2.1_volatile — ЭТАП C.3 v13. Исторический движок v2.
#
# Обработка — по глобальным группам G(ts): все свечи с одинаковым timestamp.
# Порядок фаз внутри группы: pending fill → SL/TP → close → signal → pending create → counters.
#
# RESEARCH ONLY. NO LIVE ORDERS. OOS SEALED.
# STRATEGY LOGIC: UNCHANGED.

import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from . import config_lab as C
from . import cost_model as CM
from . import risk_adapter as RA
from .portfolio import Portfolio, Position, ClosedTrade
from .strategy_adapter import SharedStrategyAdapter

log = logging.getLogger(__name__)


@dataclass
class PendingEntry:
    figi: str
    signal_ts: pd.Timestamp
    signal_price: float
    entry_target_ts: Optional[pd.Timestamp]
    df_window: pd.DataFrame
    signal_reason: str
    quantity: int = 0


@dataclass
class EventGroup:
    ts: pd.Timestamp
    candles: Dict[str, pd.Series] = field(default_factory=dict)


def _period_for(date_str: str, boundaries: dict) -> str:
    if date_str <= boundaries.get("discovery_end", "9999-12-31"):
        return "DISCOVERY"
    if date_str <= boundaries.get("validation_end", "9999-12-31"):
        return "VALIDATION"
    return "OOS"


def _last_known_price_before(figi: str, ts: pd.Timestamp, candles: pd.DataFrame) -> Optional[float]:
    """Последняя известная цена (close) строго до ts."""
    if candles is None or candles.empty:
        return None
    upto = candles[candles.index < ts]
    if upto.empty:
        return None
    return float(upto["close"].iloc[-1])


def _next_candle_time(candles: pd.DataFrame, ts: pd.Timestamp) -> Optional[pd.Timestamp]:
    """Следующая доступная свеча после ts."""
    if candles is None or candles.empty:
        return None
    after = candles.index[candles.index > ts]
    if len(after) == 0:
        return None
    return after[0]


def _check_sl_tp_on_candle(candle: pd.Series, sl: float, tp: float) -> Optional[str]:
    """Проверка SL/TP на одной свече. SL первым при обоих."""
    high = float(candle["high"])
    low = float(candle["low"])
    hit_sl = low <= sl
    hit_tp = high >= tp
    if hit_sl and hit_tp:
        return "SL_AND_TP"
    if hit_sl:
        return "SL"
    if hit_tp:
        return "TP"
    return None


class BacktestEngineV2:
    def __init__(
        self,
        strategy_adapter: SharedStrategyAdapter,
        scenario: str = "base",
        extra_slippage: float = 0.0,
        period_boundaries: Optional[dict] = None,
        starting_balance: Optional[float] = None,
    ):
        self.sa = strategy_adapter
        self.scenario = scenario
        self.extra_slippage = extra_slippage
        self.period_boundaries = period_boundaries or {
            "discovery_end": "9999-12-31",
            "validation_end": "9999-12-31",
        }
        self.starting_balance = starting_balance if starting_balance is not None else C.STARTING_BALANCE

    # ---- Вспомогательные ----

    def _entry_price(self, open_price: float) -> float:
        return open_price * (1.0 + C.SLIPPAGE_PERCENT + self.extra_slippage)

    def _exit_price(self, trigger: float) -> float:
        return trigger * (1.0 - (C.SLIPPAGE_PERCENT + self.extra_slippage))

    def _current_prices_at_ts(
        self,
        ts: pd.Timestamp,
        group: Dict[str, pd.Series],
        candles_by_figi: Dict[str, pd.DataFrame],
        open_positions: Dict[str, Position],
    ) -> Dict[str, float]:
        """open текущей свечи для FIGI в G(ts); последняя известная — для остальных."""
        prices: Dict[str, float] = {}
        for figi in open_positions:
            if figi in group:
                prices[figi] = float(group[figi]["open"])
            else:
                last = _last_known_price_before(figi, ts, candles_by_figi.get(figi))
                if last is not None:
                    prices[figi] = last
        return prices

    def _build_groups(
        self,
        top10: dict,
        candles_by_figi: Dict[str, pd.DataFrame],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[EventGroup]:
        """
        Формирует группы событий G(ts) — все FIGI, у которых есть свеча в ts.
        Для каждой свечи проверяем: FIGI в TOP-10 на дату свечи ЛИБО FIGI
        может иметь открытую позицию/pending — берём все свечи по всем FIGI
        из TOP-10 union FIGI с позициями. Проще: берём все свечи FIGI,
        которые хотя бы раз в TOP-10 (figis_in_top10). Позиции вне TOP-10
        у нас быть не может: позиция открывается только для FIGI в TOP-10,
        а контроль продолжается по свечам этого FIGI.
        """
        figis_in_top10 = set()
        for date_str, lst in top10.items():
            for item in lst:
                figis_in_top10.add(item["figi"])

        # Собираем потоки итераторов
        streams = []
        for figi in figis_in_top10:
            df = candles_by_figi.get(figi)
            if df is None or df.empty:
                continue
            if start_date:
                df = df[df.index >= pd.Timestamp(start_date, tz="UTC")]
            if end_date:
                df = df[df.index <= pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)]
            if df.empty:
                continue
            # Итератор по свечам
            for ts, row in df.iterrows():
                streams.append((ts, figi, row))

        streams.sort(key=lambda x: (x[0], x[1]))

        groups: List[EventGroup] = []
        current: Optional[EventGroup] = None
        for ts, figi, row in streams:
            if current is None or ts != current.ts:
                if current is not None:
                    groups.append(current)
                current = EventGroup(ts=ts)
            current.candles[figi] = row
        if current is not None:
            groups.append(current)
        return groups

    # ---- Основной прогон ----

    def run(
        self,
        top10: dict,
        instruments_by_figi: dict,
        candles_by_figi: Dict[str, pd.DataFrame],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        portfolio = Portfolio(starting_balance=self.starting_balance)
        pending_entries: Dict[str, PendingEntry] = {}
        skipped: List[Tuple[str, str, str]] = []

        # Счётчики
        counters = {
            "eligible_signal_events": 0,
            "actual_get_signal_calls": 0,
            "position_monitoring_events": 0,
        }

        # equity_curve
        equity_curve: List[Tuple[str, float]] = [("START", float(self.starting_balance))]

        # TOP-10 FIGI по датам
        top10_figis_by_date: Dict[str, List[str]] = {}
        for date_str, lst in top10.items():
            top10_figis_by_date[date_str] = [item["figi"] for item in lst]

        groups = self._build_groups(top10, candles_by_figi, start_date, end_date)
        log.info(f"[v2] Групп событий: {len(groups)}")

        for group in groups:
            ts = group.ts
            date_str = ts.date().isoformat()
            top10_today = set(top10_figis_by_date.get(date_str, []))

            # Текущие цены для оценки портфеля на момент ts
            prices_at_ts = self._current_prices_at_ts(
                ts, group.candles, candles_by_figi, portfolio.open_positions
            )

            # === Фаза 1: Pending fill ===
            # Обрабатываем pending, у которых entry_target_ts == ts
            fill_order = [
                figi for figi in pending_entries
                if pending_entries[figi].entry_target_ts == ts
            ]
            # Порядок: TOP-10 order_idx, иначе по figi
            def _order_key(f):
                lst = top10_figis_by_date.get(date_str, [])
                return (0, lst.index(f)) if f in lst else (1, f)
            fill_order.sort(key=_order_key)

            for figi in fill_order:
                pending = pending_entries.pop(figi)
                if figi not in group.candles:
                    skipped.append((date_str, figi, "pending_no_candle"))
                    continue
                candle = group.candles[figi]
                open_price = float(candle["open"])
                entry_price = self._entry_price(open_price)
                df_window = pending.df_window

                # Размер позиции
                lot = int(instruments_by_figi.get(figi, {}).get("lot", 1))
                if lot <= 0:
                    skipped.append((date_str, figi, "bad_lot"))
                    continue
                equity = portfolio.get_equity(prices_at_ts)
                exposure = portfolio.get_current_exposure(prices_at_ts)
                trade_count = portfolio.get_trade_count(date_str, figi)
                lots = RA.calculate_position_size(
                    figi=figi, last_price=entry_price, candles_df=df_window,
                    account_balance=equity, lot_size=lot,
                    current_exposure=exposure, daily_trade_count=trade_count,
                )
                if lots <= 0:
                    skipped.append((date_str, figi, "fill_lots_0"))
                    continue

                sl, tp = RA.calculate_sl_tp(entry_price, "BUY", df_window)
                if sl is None or tp is None:
                    skipped.append((date_str, figi, "fill_sl_tp_none"))
                    continue

                # Подбор quantity с учётом фактического cash
                quantity = lots
                while quantity > 0:
                    shares = quantity * lot
                    commission_data = CM.calc_commission(
                        entry_price=entry_price, exit_price=entry_price, shares=shares,
                    )
                    entry_commission_rub = commission_data["entry_commission_rub"]
                    # Порядок операций как в portfolio.open_position
                    cost = entry_price * quantity * lot
                    actual_debit = cost + entry_commission_rub
                    if actual_debit <= portfolio.cash:
                        break
                    quantity -= 1
                if quantity <= 0:
                    skipped.append((date_str, figi, "fill_insufficient_cash"))
                    continue

                pos = Position(
                    figi=figi, ticker=instruments_by_figi[figi].get("ticker", figi),
                    entry_time=ts, entry_price=entry_price,
                    quantity=quantity, lot_size=lot,
                    sl_price=sl, tp_price=tp,
                    entry_trigger="open",
                    entry_slippage_rub=0.0,
                    entry_commission_rub=entry_commission_rub,
                    trade_id=f"v2-{figi}-{ts.isoformat()}",
                )
                portfolio.open_position(pos)
                portfolio.increment_trade_count(date_str, figi)
                log.info(f"[FILL] {pos.ticker} qty={quantity} @ {entry_price:.4f} "
                         f"SL={sl:.4f} TP={tp:.4f}")

            # === Фаза 2: SL/TP check + Фаза 3: close ===
            pos_order = list(portfolio.open_positions.keys())
            def _pos_order_key(f):
                lst = top10_figis_by_date.get(date_str, [])
                return (0, lst.index(f)) if f in lst else (1, f)
            pos_order.sort(key=_pos_order_key)
            for figi in pos_order:
                if figi not in group.candles:
                    continue
                pos = portfolio.open_positions.get(figi)
                if pos is None:
                    continue
                counters["position_monitoring_events"] += 1
                candle = group.candles[figi]
                # Проверка на свече входа тоже (entry_time == ts → проверяем)
                result = _check_sl_tp_on_candle(candle, pos.sl_price, pos.tp_price)
                if result is None:
                    continue
                # Гэп: если open уже за SL/TP
                open_price = float(candle["open"])
                if result in ("SL", "SL_AND_TP"):
                    trigger = pos.sl_price
                    if open_price < pos.sl_price:
                        trigger = open_price
                        exit_reason = "GAP_SL"
                        exit_trigger = "gap_open"
                    else:
                        exit_reason = "SL"
                        exit_trigger = "SL"
                else:
                    trigger = pos.tp_price
                    if open_price > pos.tp_price:
                        trigger = open_price
                        exit_reason = "GAP_TP"
                        exit_trigger = "gap_open"
                    else:
                        exit_reason = "TP"
                        exit_trigger = "TP"
                exit_price = self._exit_price(trigger)
                shares = pos.quantity * pos.lot_size
                comm_exit = CM.calc_commission(
                    entry_price=pos.entry_price, exit_price=exit_price, shares=shares,
                )
                total_commission = pos.entry_commission_rub + comm_exit["exit_commission_rub"]
                gross = (exit_price - pos.entry_price) * shares
                net = gross - total_commission
                holding = (ts - pd.Timestamp(pos.entry_time)).total_seconds()
                trade = ClosedTrade(
                    trade_id=pos.trade_id, figi=pos.figi, ticker=pos.ticker,
                    entry_time=str(pos.entry_time), entry_price=pos.entry_price,
                    exit_time=str(ts), exit_price=exit_price,
                    quantity=pos.quantity, lot_size=pos.lot_size, shares=shares,
                    exit_reason=exit_reason, exit_trigger=exit_trigger,
                    entry_trigger=pos.entry_trigger,
                    entry_slippage_rub=0.0,
                    exit_slippage_rub=(trigger - exit_price) * shares,
                    total_slippage_rub=(trigger - exit_price) * shares,
                    entry_commission_rub=pos.entry_commission_rub,
                    exit_commission_rub=comm_exit["exit_commission_rub"],
                    total_commission_rub=total_commission,
                    gross_pnl_rub=gross, net_pnl_rub=net,
                    scenario=self.scenario,
                    period=_period_for(date_str, self.period_boundaries),
                    holding_seconds=holding,
                )
                portfolio.close_position(figi, trade)
                log.info(f"[CLOSE] {pos.ticker} {exit_reason} @ {exit_price:.4f} net={net:+.2f}")

            # === Фаза 4: Signal generation ===
            eligible = 0
            candidates = []
            for figi, candle in group.candles.items():
                if figi not in top10_today:
                    continue
                eligible += 1
                if figi in portfolio.open_positions:
                    continue
                if figi in pending_entries:
                    continue
                candidates.append(figi)
            counters["eligible_signal_events"] += eligible

            def _sig_order(f):
                lst = top10_figis_by_date.get(date_str, [])
                return (0, lst.index(f)) if f in lst else (1, f)
            candidates.sort(key=_sig_order)

            # === Фаза 5: Pending create ===
            for figi in candidates:
                candle = group.candles[figi]
                close_price = float(candle["close"])
                df = candles_by_figi.get(figi)
                if df is None or df.empty:
                    continue
                window_start = ts - pd.Timedelta(days=C.CANDLES_LOOKBACK_DAYS)
                df_window = df[(df.index >= window_start) & (df.index <= ts)]
                if df_window.empty:
                    skipped.append((date_str, figi, "empty_window"))
                    continue
                counters["actual_get_signal_calls"] += 1
                signal, reason = self.sa.get_signal(figi, df_window, close_price, drop_incomplete=True)
                if signal != "BUY":
                    if signal == "SELL":
                        skipped.append((date_str, figi, f"SELL_ignored({reason})"))
                    continue
                next_ts = _next_candle_time(df, ts)
                if next_ts is None:
                    skipped.append((date_str, figi, "pending_no_next_candle"))
                    continue
                pending_entries[figi] = PendingEntry(
                    figi=figi, signal_ts=ts, signal_price=close_price,
                    entry_target_ts=next_ts, df_window=df_window,
                    signal_reason=reason,
                )

            # === Фаза 6: counters + equity ===
            eq = portfolio.get_equity(prices_at_ts)
            equity_curve.append((str(ts), eq))

        # Закрытие оставшихся по последней цене НЕ делаем: они остаются OPEN.
        # pending без следующей свечи — уже отменены при создании (next_ts None).
        # pending, чей entry_target_ts > последней группы — отменяем в конце.
        for figi, pending in list(pending_entries.items()):
            skipped.append((str(pending.signal_ts.date()), figi, "pending_end_of_data"))

        # max_drawdown_equity
        peak = 0.0
        max_dd_eq = 0.0
        dd_ts: Optional[str] = None
        for ts_label, eq in equity_curve:
            peak = max(peak, eq)
            dd = peak - eq
            if dd > max_dd_eq:
                max_dd_eq = dd
                dd_ts = ts_label

        return {
            "scenario": self.scenario,
            "portfolio": portfolio,
            "closed_trades": portfolio.closed_trades,
            "open_positions": list(portfolio.open_positions.values()),
            "skipped": skipped,
            "counters": counters,
            "equity_curve": equity_curve,
            "max_drawdown_equity": max_dd_eq,
            "max_drawdown_equity_ts": dd_ts,
        }