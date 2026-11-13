# historical_lab/tools/count_expected_calls.py
# Tsclp_v2.1_volatile — диагностика ожидаемого числа событий v2.
#
# Считает по данным (без вызова get_signal, без backtest):
#   - eligible_signal_events: FIGI с свечой в G(ts) ∩ TOP-10(date(ts))
#   - position_monitoring_events: верхняя оценка (все FIGI с позицией)
#   - potential_get_signal_calls: FIGI eligible без открытой позиции/pending
#
# RESEARCH ONLY. NO LIVE ORDERS. NO API CALLS.

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parent.parent
DATA = LAB / "data"
TOP10 = DATA / "top10_rolling.json"
INSTRUMENTS = DATA / "instruments.json"
CANDLES = DATA / "candles"
OUT = LAB / "output" / "diagnostics" / "call_frequency_audit"


def load_top10():
    return json.loads(TOP10.read_text(encoding="utf-8"))


def load_instruments():
    return json.loads(INSTRUMENTS.read_text(encoding="utf-8"))


def load_5min(figi):
    p_csv = CANDLES / f"{figi}.csv"
    if not p_csv.is_file():
        return None
    df = pd.read_csv(p_csv)
    if "time" not in df.columns:
        return None
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    return df


def build_groups(top10, candles_by_figi):
    """Группы (ts, {figi: candle}) — как в backtest_engine_v2."""
    streams = []
    for figi, df in candles_by_figi.items():
        if df is None or df.empty:
            continue
        for ts, row in df.iterrows():
            streams.append((ts, figi))
    streams.sort(key=lambda x: (x[0], x[1]))

    groups = []
    current_ts = None
    current_figis = []
    for ts, figi in streams:
        if current_ts is None or ts != current_ts:
            if current_ts is not None:
                groups.append((current_ts, current_figis))
            current_ts = ts
            current_figis = [figi]
        else:
            current_figis.append(figi)
    if current_ts is not None:
        groups.append((current_ts, current_figis))
    return groups


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    if not TOP10.is_file():
        print(f"Нет {TOP10}")
        sys.exit(1)
    if not INSTRUMENTS.is_file():
        print(f"Нет {INSTRUMENTS}")
        sys.exit(1)

    top10 = load_top10()
    instruments = load_instruments()

    figis_needed = set()
    for date_str, lst in top10.items():
        for item in lst:
            figis_needed.add(item["figi"])

    candles_by_figi = {}
    for figi in figis_needed:
        df = load_5min(figi)
        if df is not None and not df.empty:
            candles_by_figi[figi] = df
        else:
            print(f"[WARN] нет 5M для {figi}")

    top10_by_date = {d: [i["figi"] for i in lst] for d, lst in top10.items()}

    groups = build_groups(top10, candles_by_figi)
    print(f"FIGI в TOP-10: {len(figis_needed)}")
    print(f"FIGI с 5M: {len(candles_by_figi)}")
    print(f"Групп событий: {len(groups)}")
    print(f"Дат в top10: {len(top10_by_date)}")

    total_eligible = 0
    total_monitoring_upper = 0
    total_potential_calls = 0

    by_date = defaultdict(lambda: {"eligible": 0, "monitoring_upper": 0,
                                   "potential_calls": 0, "groups": 0})
    by_figi = Counter()

    # Для подсчёта potential_calls (FIGI без позиции/pending) —
    # упрощённо: считаем, что в любой момент нет открытых позиций (верхняя оценка).
    # Реальное число — из backtest_engine_v2. Здесь — верхняя граница.
    for ts, figis in groups:
        date_str = ts.date().isoformat()
        top10_today = set(top10_by_date.get(date_str, []))
        in_top = [f for f in figis if f in top10_today]
        eligible = len(in_top)
        monitoring_upper = len(figis)   # если бы все были с позицией
        potential_calls = eligible      # если бы никто не имел позицию/pending

        total_eligible += eligible
        total_monitoring_upper += monitoring_upper
        total_potential_calls += potential_calls

        by_date[date_str]["eligible"] += eligible
        by_date[date_str]["monitoring_upper"] += monitoring_upper
        by_date[date_str]["potential_calls"] += potential_calls
        by_date[date_str]["groups"] += 1

        for f in in_top:
            by_figi[f] += 1

    # Сохранение
    summary = {
        "figis_in_top10": len(figis_needed),
        "figis_with_5m": len(candles_by_figi),
        "dates": len(top10_by_date),
        "groups": len(groups),
        "totals": {
            "eligible_signal_events": total_eligible,
            "position_monitoring_events_upper": total_monitoring_upper,
            "potential_get_signal_calls_upper": total_potential_calls,
        },
        "notes": [
            "position_monitoring_events_upper и potential_get_signal_calls_upper — "
            "верхние оценки (предполагают отсутствие открытых позиций). "
            "Фактические значения — только из backtest_engine_v2.",
        ],
    }
    (OUT / "expected_calls_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with open(OUT / "expected_calls_by_date.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "groups", "eligible", "monitoring_upper", "potential_calls"])
        for d in sorted(by_date.keys()):
            r = by_date[d]
            w.writerow([d, r["groups"], r["eligible"], r["monitoring_upper"], r["potential_calls"]])

    with open(OUT / "expected_calls_by_figi.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["figi", "eligible_calls"])
        for figi, n in sorted(by_figi.items(), key=lambda x: -x[1]):
            w.writerow([figi, n])

    print()
    print("=== ИТОГИ ===")
    print(f"eligible_signal_events:              {total_eligible}")
    print(f"position_monitoring_events (upper):  {total_monitoring_upper}")
    print(f"potential_get_signal_calls (upper):  {total_potential_calls}")
    print()
    print(f"Отчёты: {OUT}")


if __name__ == "__main__":
    main()