# historical_lab/tools/diag_5m.py
# Аудит 5M данных. Только чтение.
import csv, json
from pathlib import Path
from collections import Counter

LAB = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y\historical_lab")
CANDLES = LAB / "data" / "candles"
TOP10 = LAB / "data" / "top10_rolling.json"
OUT = LAB / "output" / "diagnostics" / "trade_count_investigation"
OUT.mkdir(parents=True, exist_ok=True)

def read_times(path):
    with open(path, encoding="utf-8") as f:
        return [r["time"] for r in csv.DictReader(f) if r.get("time")]

files = sorted(CANDLES.glob("*.csv"))
print(f"5M files: {len(files)}")
rows = []
for f in files:
    times = read_times(f)
    if not times:
        rows.append({"figi": f.stem, "status": "empty"})
        continue
    dates = [t[:10] for t in times]
    by_date = Counter(dates)
    c_0355 = sum(1 for t in times if t[11:16] == "03:55")
    c_0400 = sum(1 for t in times if t[11:16] == "04:00")
    dup = len(times) - len(set(times))
    sorted_ok = all(times[i] <= times[i+1] for i in range(len(times)-1))
    rows.append({"figi": f.stem, "rows": len(times), "trading_days": len(by_date),
                 "first": times[0], "last": times[-1],
                 "min_per_day": min(by_date.values()), "max_per_day": max(by_date.values()),
                 "avg_per_day": round(sum(by_date.values())/len(by_date), 1),
                 "days_with_1": sum(1 for v in by_date.values() if v == 1),
                 "count_0355": c_0355, "count_0400": c_0400,
                 "duplicates": dup, "sorted_ok": sorted_ok})
    print(f"{f.stem}: rows={len(times)} days={len(by_date)} per_day={min(by_date.values())}-{max(by_date.values())} 0355={c_0355} 0400={c_0400} dup={dup} sorted={sorted_ok}")

with open(OUT / "data_coverage_diagnostic.csv", "w", encoding="utf-8", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows: w.writerow(r)

top = json.loads(TOP10.read_text(encoding="utf-8"))
figis_with_5m = {f.stem for f in files}
all_top = set()
empty_dates = 0
for d, lst in top.items():
    if not lst: empty_dates += 1; continue
    for item in lst: all_top.add(item["figi"])
missing = all_top - figis_with_5m
print(f"\nTOP-10 dates: {len(top)} (empty: {empty_dates})")
print(f"unique FIGI in TOP-10: {len(all_top)}")
print(f"FIGI with 5M: {len(figis_with_5m)}")
print(f"FIGI in TOP-10 but no 5M: {len(missing)}")
if missing: print("  missing:", sorted(missing)[:20])
