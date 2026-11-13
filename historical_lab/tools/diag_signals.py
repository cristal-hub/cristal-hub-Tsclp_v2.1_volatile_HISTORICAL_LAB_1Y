# historical_lab/tools/diag_signals.py
# Аудит сигналов. Только чтение.
import csv
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from historical_lab import config_lab as C
from historical_lab import data_loader
from historical_lab import strategy_adapter as SA
from historical_lab import _config_shim
_config_shim.install()

LAB = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y\historical_lab")
TOP10 = LAB / "data" / "top10_rolling.json"
OUT = LAB / "output" / "diagnostics" / "trade_count_investigation"
OUT.mkdir(parents=True, exist_ok=True)

FIELDS = ["date", "figi", "status", "window_len", "window_first", "window_last",
          "signal", "reason", "regime"]

def main():
    top = json.loads(TOP10.read_text(encoding="utf-8"))
    sa = SA.SharedStrategyAdapter()
    rows = []
    for date_str in sorted(top.keys()):
        t = pd.Timestamp(date_str, tz="UTC").normalize()
        window_start = t - pd.Timedelta(days=C.CANDLES_LOOKBACK_DAYS)
        for item in top[date_str]:
            figi = item["figi"]
            base = {"date": date_str, "figi": figi, "status": "ok",
                    "window_len": 0, "window_first": "", "window_last": "",
                    "signal": "", "reason": "", "regime": ""}
            try:
                df = data_loader.load_5min(figi)
            except data_loader.DataMissingError:
                base["status"] = "no_5m"
                rows.append(base); continue
            df_window = df[(df.index >= window_start) & (df.index <= t)]
            if df_window.empty:
                base["status"] = "empty_window"
                rows.append(base); continue
            last_close = float(df_window["close"].iloc[-1])
            signal, reason = sa.get_signal(figi, df_window, last_close, drop_incomplete=True)
            base.update({
                "window_len": len(df_window),
                "window_first": str(df_window.index.min()),
                "window_last": str(df_window.index.max()),
                "signal": signal, "reason": reason,
                "regime": getattr(sa.strategy_manager, "_last_regime", None),
            })
            rows.append(base)
    with open(OUT / "signal_flow_diagnostic.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})

    sig_counts = Counter(r["signal"] for r in rows if r["signal"])
    print("Signals:", dict(sig_counts))
    reasons = Counter(r["reason"] for r in rows if r["reason"])
    print("\nTop reasons:")
    for rr, n in reasons.most_common(20):
        print(f"  {n:5d}  {rr}")
    wl = [r["window_len"] for r in rows if r["window_len"]]
    if wl:
        print(f"\nwindow_len: min={min(wl)} max={max(wl)} avg={sum(wl)/len(wl):.1f}")
    by_figi = Counter(r["figi"] for r in rows if r["signal"])
    print(f"\nCalls per figi (top 10): {by_figi.most_common(10)}")
    statuses = Counter(r["status"] for r in rows)
    print(f"\nStatuses: {dict(statuses)}")

if __name__ == "__main__":
    main()