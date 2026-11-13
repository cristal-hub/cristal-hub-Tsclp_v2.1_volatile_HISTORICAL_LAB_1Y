# historical_lab/tools/diag_calls.py
# Аудит частоты вызовов get_signal. Только чтение.
import csv, json, sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from historical_lab import config_lab as C
from historical_lab import data_loader
from historical_lab import strategy_adapter as SA
from historical_lab import _config_shim
_config_shim.install()

LAB = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y\historical_lab")
TOP10 = LAB / "data" / "top10_rolling.json"
OUT = LAB / "output" / "diagnostics" / "call_frequency_audit"
OUT.mkdir(parents=True, exist_ok=True)

def main():
    top = json.loads(TOP10.read_text(encoding="utf-8"))
    sa = SA.SharedStrategyAdapter()

    calls_by_inst = defaultdict(list)
    calls_by_date = Counter()

    for date_str in sorted(top.keys()):
        t = pd.Timestamp(date_str, tz="UTC").normalize()
        window_start = t - pd.Timedelta(days=C.CANDLES_LOOKBACK_DAYS)
        for item in top[date_str]:
            figi = item["figi"]
            try:
                df = data_loader.load_5min(figi)
            except data_loader.DataMissingError:
                continue
            df_window = df[(df.index >= window_start) & (df.index <= t)]
            if df_window.empty:
                continue
            last_close = float(df_window["close"].iloc[-1])
            last_time = df_window.index[-1]
            signal, reason = sa.get_signal(figi, df_window, last_close, drop_incomplete=True)  # ← FIX
            calls_by_inst[figi].append({
                "date": date_str, "call_timestamp": str(last_time),
                "signal": signal, "reason": reason,
            })
            calls_by_date[date_str] += 1

    with open(OUT / "calls_by_instrument.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["figi", "calls", "unique_dates", "unique_timestamps", "first", "last",
                    "min_per_day", "max_per_day", "avg_per_day", "buy", "sell", "hold"])
        for figi, lst in sorted(calls_by_inst.items()):
            dates = [c["date"] for c in lst]
            times = [c["call_timestamp"] for c in lst]
            by_date = Counter(dates)
            w.writerow([figi, len(lst), len(set(dates)), len(set(times)),
                        min(times), max(times),
                        min(by_date.values()), max(by_date.values()),
                        round(len(lst)/len(set(dates)), 2),
                        sum(1 for c in lst if c["signal"] == "BUY"),
                        sum(1 for c in lst if c["signal"] == "SELL"),
                        sum(1 for c in lst if c["signal"] == "HOLD")])

    with open(OUT / "calls_by_date.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "calls"])
        for d, n in sorted(calls_by_date.items()):
            w.writerow([d, n])

    with open(OUT / "candle_vs_call_coverage.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["figi", "total_5m_candles", "possible_calls_1_per_candle",
                    "actual_calls", "coverage_pct"])
        for figi, lst in sorted(calls_by_inst.items()):
            df = data_loader.load_5min(figi)
            total = len(df)
            actual = len(lst)
            pct = round(actual / total * 100, 4) if total else 0
            w.writerow([figi, total, total, actual, pct])

    sample_figi = "BBG00F6NKQX3"
    sample_date = "2026-03-02"
    t = pd.Timestamp(sample_date, tz="UTC").normalize()
    ws = t - pd.Timedelta(days=C.CANDLES_LOOKBACK_DAYS)
    df = data_loader.load_5min(sample_figi)
    df_window = df[(df.index >= ws) & (df.index <= t)]
    with open(OUT / "example_intraday_timeline.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["time", "close", "called_get_signal"])
        last_time = df_window.index[-1] if not df_window.empty else None
        for ts, row in df_window.iterrows():
            w.writerow([ts, float(row["close"]), "YES" if ts == last_time else "no"])

    print(f"FIGI: {len(calls_by_inst)}")
    print(f"Total calls: {sum(len(v) for v in calls_by_inst.values())}")
    print(f"Dates: {len(calls_by_date)}")
    print(f"Calls per date: min={min(calls_by_date.values())} max={max(calls_by_date.values())}")
    print(f"Sample: {sample_figi} @ {sample_date}: "
          f"5M candles={len(df_window)}, get_signal calls=1")
    print(f"\nReports: {OUT}")

if __name__ == "__main__":
    main()