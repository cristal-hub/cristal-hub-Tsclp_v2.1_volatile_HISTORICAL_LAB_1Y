# historical_lab/tools/download_market_data.py
# Tsclp_v2.1_volatile — загрузчик данных (Этап A + Этап B).
#
# Этап A: --stage daily — 720 инструментов, дневные свечи.
# Этап B: --stage intraday — 5-мин свечи (недельная пагинация) для FIGI из rolling TOP-10.
#
# RESEARCH ONLY. NO LIVE ORDERS. NO REAL MONEY.

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from t_tech.invest import AsyncClient, CandleInterval, InstrumentStatus

LAB_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = LAB_ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"
CANDLES_DIR = DATA_DIR / "candles"
INSTRUMENTS_FILE = DATA_DIR / "instruments.json"
TOP10_FILE = DATA_DIR / "top10_rolling.json"
MANIFEST_FILE = DATA_DIR / "download_manifest.json"
DAILY_COVERAGE_FILE = DATA_DIR / "daily_coverage.csv"
INTRADAY_COVERAGE_FILE = DATA_DIR / "intraday_coverage.csv"
ERRORS_FILE = DATA_DIR / "download_errors.csv"
LOG_FILE = DATA_DIR / "download.log"

REAL_EXCHANGE_MOEX = 1
DAILY_WARMUP_DAYS = 30
INTRADAY_WARMUP_DAYS = 2
INTRADAY_MAX_DAYS_PER_REQUEST = 7   # макс. период для 5-мин (документация T-Invest)
MAX_ATTEMPTS = 3
RETRY_DELAY_SEC = 5.0
API_CALL_DELAY_SEC = 0.1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _get_token() -> str:
    tok = os.environ.get("TINKOFF_READONLY_TOKEN")
    if not tok:
        log.error("Не задан TINKOFF_READONLY_TOKEN.")
        sys.exit(1)
    return tok


# ---------- Этап A: daily ----------

async def fetch_shares(client: AsyncClient) -> list:
    log.info("[shares] Запрос списка акций...")
    resp = await client.instruments.shares(
        instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL
    )
    shares = [
        s for s in resp.instruments
        if getattr(s, "real_exchange", 0) == REAL_EXCHANGE_MOEX
        and (s.currency or "").lower() == "rub"
        and s.buy_available_flag and s.sell_available_flag
    ]
    log.info(f"[shares] Всего акций MOEX (с -RM): {len(shares)}")
    return shares


async def fetch_daily_candles(client: AsyncClient, figi: str, from_dt: datetime, to_dt: datetime):
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await asyncio.sleep(API_CALL_DELAY_SEC)
            candles = []
            async for c in client.get_all_candles(
                figi=figi, from_=from_dt, to=to_dt,
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                candles.append(c)
            return candles
        except Exception as e:
            last_exc = e
            log.warning(f"[{figi}] daily попытка {attempt}/{MAX_ATTEMPTS}: {e}")
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY_SEC * attempt)
    log.error(f"[{figi}] daily не удалось: {last_exc}")
    return None


def candles_to_rows(candles: list) -> tuple:
    rows = []
    received = len(candles)
    skipped = 0
    for c in candles:
        if getattr(c, "is_complete", None) is False:
            skipped += 1
            continue
        rows.append({
            "date": c.time.isoformat(),
            "open": float(c.open.units + c.open.nano / 1e9),
            "high": float(c.high.units + c.high.nano / 1e9),
            "low": float(c.low.units + c.low.nano / 1e9),
            "close": float(c.close.units + c.close.nano / 1e9),
            "volume": int(c.volume),
        })
    return rows, received, skipped, len(rows)


def save_csv_atomic(rows: list, path: Path, fields: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(path)


def _is_loaded_ok(figi: str, expected_start: datetime, expected_end: datetime,
                  min_rows: int = 200) -> bool:
    p = DAILY_DIR / f"{figi}.csv"
    if not p.is_file():
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            dates = [row["date"] for row in reader if row.get("date")]
        if len(dates) < min_rows:
            return False
        first = datetime.fromisoformat(dates[0])
        last = datetime.fromisoformat(dates[-1])
        return (first <= expected_start + timedelta(days=5)
                and last >= expected_end - timedelta(days=5))
    except Exception:
        return False


async def stage_daily(args):
    token = _get_token()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    fetch_start = start - timedelta(days=DAILY_WARMUP_DAYS)
    log.info(f"[daily] Период: {fetch_start.date()} → {end.date()} (прогрев {DAILY_WARMUP_DAYS}д)")

    async with AsyncClient(token) as client:
        shares = await fetch_shares(client)
        if not shares:
            log.error("[daily] Нет акций MOEX.")
            return

        instruments = []
        for s in shares:
            instruments.append({
                "figi": s.figi, "ticker": s.ticker, "name": s.name,
                "lot": int(s.lot or 1), "real_exchange": int(s.real_exchange or 0),
                "currency": (s.currency or "").lower(),
                "api_trade_available_flag": bool(getattr(s, "api_trade_available_flag", False)),
                "first_1day_candle_date": (
                    s.first_1day_candle_date.isoformat()
                    if getattr(s, "first_1day_candle_date", None) else None
                ),
            })
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(INSTRUMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(instruments, f, ensure_ascii=False, indent=2)
        log.info(f"[daily] instruments.json: {len(instruments)}")

        coverage = []
        errors = []
        for i, inst in enumerate(instruments, 1):
            figi = inst["figi"]
            ticker = inst["ticker"]
            if args.resume and _is_loaded_ok(figi, fetch_start, end):
                log.info(f"[{i}/{len(instruments)}] {ticker}: resume")
                coverage.append({"figi": figi, "ticker": ticker, "status": "skipped_resume",
                                 "received": 0, "skipped_incomplete": 0, "saved": 0,
                                 "first": None, "last": None})
                continue
            log.info(f"[{i}/{len(instruments)}] {ticker}: загрузка...")
            candles = await fetch_daily_candles(client, figi, fetch_start, end)
            if candles is None:
                errors.append({"figi": figi, "ticker": ticker, "error": "fetch_failed"})
                coverage.append({"figi": figi, "ticker": ticker, "status": "error",
                                 "received": 0, "skipped_incomplete": 0, "saved": 0,
                                 "first": None, "last": None})
                continue
            rows, received, skipped, saved = candles_to_rows(candles)
            if saved == 0:
                errors.append({"figi": figi, "ticker": ticker, "error": "no_complete_candles"})
                coverage.append({"figi": figi, "ticker": ticker, "status": "no_data",
                                 "received": received, "skipped_incomplete": skipped,
                                 "saved": 0, "first": None, "last": None})
                continue
            save_csv_atomic(rows, DAILY_DIR / f"{figi}.csv",
                            ["date", "open", "high", "low", "close", "volume"])
            coverage.append({"figi": figi, "ticker": ticker, "status": "ok",
                             "received": received, "skipped_incomplete": skipped,
                             "saved": saved, "first": rows[0]["date"], "last": rows[-1]["date"]})
            log.info(f"[{i}/{len(instruments)}] {ticker}: {saved} ({rows[0]['date'][:10]} → {rows[-1]['date'][:10]})")

    with open(DAILY_COVERAGE_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(coverage[0].keys()))
        w.writeheader()
        for r in coverage:
            w.writerow(r)
    if errors:
        with open(ERRORS_FILE, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["figi", "ticker", "error"])
            w.writeheader()
            for r in errors:
                w.writerow(r)
    _write_manifest("daily", args, instruments, coverage, errors,
                    start, end, fetch_start)


def _write_manifest(stage: str, args, instruments: list, coverage: list,
                    errors: list, start: datetime, end: datetime, fetch_start: datetime):
    rm_count = sum(1 for i in instruments if "-RM" in (i["ticker"] or "").upper())
    rm_api = sum(1 for i in instruments
                 if "-RM" in (i["ticker"] or "").upper() and i.get("api_trade_available_flag"))
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "variant": "A_no_RM_filter",
        "requested_start": args.start,
        "requested_end": args.end,
        "fetch_start": fetch_start.isoformat(),
        "fetch_end": end.isoformat(),
        "sdk_version": "1.51.0",
        "instruments_count": len(instruments),
        "ok_count": sum(1 for c in coverage if c["status"] == "ok"),
        "error_count": len(errors),
        "resume_count": sum(1 for c in coverage if c["status"] == "skipped_resume"),
        "total_received": sum(c["received"] for c in coverage),
        "total_saved": sum(c["saved"] for c in coverage),
        "total_skipped_incomplete": sum(c["skipped_incomplete"] for c in coverage),
        "rm_count": rm_count,
        "rm_api_trade_available": rm_api,
        "sha256_instruments_json": _sha256(INSTRUMENTS_FILE.read_text(encoding="utf-8"))
            if INSTRUMENTS_FILE.is_file() else None,
        "limitations": [
            "Survivorship bias: Shares возвращает ТЕКУЩИЙ состав.",
            f"443 -RM (иностранные): api_trade_available=True только у {rm_api}.",
            "is_complete=False исключены из CSV.",
            "4-строчные FIGI — не акции (облигации/фонды), оставлены как в production.",
        ],
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log.info(f"[{stage}] manifest: {MANIFEST_FILE}")
    log.info(f"[{stage}] Готово. OK={manifest['ok_count']}, errors={manifest['error_count']}, "
             f"saved={manifest['total_saved']}, rm={rm_count} (api_avail={rm_api})")


# ---------- Этап B: intraday (5 мин) ----------

def _get_top10_figis() -> list:
    """Объединение всех FIGI, входивших в rolling TOP-10 хотя бы раз."""
    if not TOP10_FILE.is_file():
        log.error(f"Нет {TOP10_FILE}. Сначала: universe_selector.build_rolling_top10().")
        return []
    data = json.loads(TOP10_FILE.read_text(encoding="utf-8"))
    figis = set()
    for lst in data.values():
        for item in lst:
            figis.add(item["figi"])
    return sorted(figis)


async def fetch_5min_chunk(client: AsyncClient, figi: str, chunk_start: datetime,
                           chunk_end: datetime):
    """Один запрос (≤7 дней). Retry при ошибках."""
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await asyncio.sleep(API_CALL_DELAY_SEC)
            candles = []
            async for c in client.get_all_candles(
                figi=figi, from_=chunk_start, to=chunk_end,
                interval=CandleInterval.CANDLE_INTERVAL_5_MIN,
            ):
                candles.append(c)
            return candles
        except Exception as e:
            last_exc = e
            log.warning(f"[{figi}] 5min chunk {chunk_start.date()} попытка {attempt}/{MAX_ATTEMPTS}: {e}")
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY_SEC * attempt)
    log.error(f"[{figi}] 5min chunk {chunk_start.date()} не удалось: {last_exc}")
    return None


async def fetch_5min_weekly(client: AsyncClient, figi: str, from_dt: datetime, to_dt: datetime):
    """Разбивает [from_dt, to_dt] на недельные чанки и объединяет результаты."""
    all_rows = []
    total_received = 0
    total_skipped = 0
    total_requests = 0
    cur = from_dt
    while cur < to_dt:
        chunk_end = min(cur + timedelta(days=INTRADAY_MAX_DAYS_PER_REQUEST), to_dt)
        chunk = await fetch_5min_chunk(client, figi, cur, chunk_end)
        total_requests += 1
        if chunk is None:
            return None, total_received, total_skipped, total_requests
        rows, received, skipped, saved = candles_to_rows(chunk)
        # candles_to_rows returns "date" key; для 5min используем "time".
        for r in rows:
            r["time"] = r.pop("date")
        all_rows.extend(rows)
        total_received += received
        total_skipped += skipped
        cur = chunk_end
    # Сортировка + дедупликация по time
    seen = set()
    unique = []
    for r in sorted(all_rows, key=lambda x: x["time"]):
        if r["time"] in seen:
            continue
        seen.add(r["time"])
        unique.append(r)
    return unique, total_received, total_skipped, total_requests


def _is_intraday_loaded_ok(figi: str, expected_start: datetime, expected_end: datetime) -> bool:
    p = CANDLES_DIR / f"{figi}.csv"
    if not p.is_file():
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            times = [row["time"] for row in reader if row.get("time")]
        if len(times) < 1000:   # год ~40k свечей; 1000 — минимум
            return False
        first = datetime.fromisoformat(times[0])
        last = datetime.fromisoformat(times[-1])
        return (first <= expected_start + timedelta(days=5)
                and last >= expected_end - timedelta(days=5))
    except Exception:
        return False


async def stage_intraday(args):
    token = _get_token()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    fetch_start = start - timedelta(days=INTRADAY_WARMUP_DAYS)

    figis = _get_top10_figis()
    if not figis:
        log.error("[intraday] Нет FIGI из TOP-10. Выход.")
        return
    log.info(f"[intraday] FIGI из rolling TOP-10 (объединение): {len(figis)}")
    log.info(f"[intraday] Период: {fetch_start.date()} → {end.date()} (прогрев {INTRADAY_WARMUP_DAYS}д)")

    instruments_by_figi = {}
    if INSTRUMENTS_FILE.is_file():
        for inst in json.loads(INSTRUMENTS_FILE.read_text(encoding="utf-8")):
            instruments_by_figi[inst["figi"]] = inst

    async with AsyncClient(token) as client:
        coverage = []
        errors = []
        for i, figi in enumerate(figis, 1):
            ticker = instruments_by_figi.get(figi, {}).get("ticker", figi)
            if args.resume and _is_intraday_loaded_ok(figi, fetch_start, end):
                log.info(f"[{i}/{len(figis)}] {ticker}: resume")
                coverage.append({"figi": figi, "ticker": ticker, "status": "skipped_resume",
                                 "requests": 0, "received": 0, "skipped_incomplete": 0,
                                 "saved": 0, "first": None, "last": None})
                continue
            log.info(f"[{i}/{len(figis)}] {ticker}: загрузка (недельные чанки)...")
            rows, received, skipped, n_requests = await fetch_5min_weekly(client, figi, fetch_start, end)
            if rows is None:
                errors.append({"figi": figi, "ticker": ticker, "error": "fetch_failed"})
                coverage.append({"figi": figi, "ticker": ticker, "status": "error",
                                 "requests": n_requests, "received": received,
                                 "skipped_incomplete": skipped, "saved": 0,
                                 "first": None, "last": None})
                continue
            if not rows:
                errors.append({"figi": figi, "ticker": ticker, "error": "no_complete_candles"})
                coverage.append({"figi": figi, "ticker": ticker, "status": "no_data",
                                 "requests": n_requests, "received": received,
                                 "skipped_incomplete": skipped, "saved": 0,
                                 "first": None, "last": None})
                continue
            save_csv_atomic(rows, CANDLES_DIR / f"{figi}.csv",
                            ["time", "open", "high", "low", "close", "volume"])
            coverage.append({"figi": figi, "ticker": ticker, "status": "ok",
                             "requests": n_requests, "received": received,
                             "skipped_incomplete": skipped, "saved": len(rows),
                             "first": rows[0]["time"], "last": rows[-1]["time"]})
            log.info(f"[{i}/{len(figis)}] {ticker}: {len(rows)} 5min свечей, "
                     f"{n_requests} запросов ({rows[0]['time'][:10]} → {rows[-1]['time'][:10]})")

    with open(INTRADAY_COVERAGE_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(coverage[0].keys()))
        w.writeheader()
        for r in coverage:
            w.writerow(r)
    if errors:
        with open(ERRORS_FILE, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["figi", "ticker", "error"])
            w.writeheader()
            for r in errors:
                w.writerow(r)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "intraday",
        "requested_start": args.start,
        "requested_end": args.end,
        "fetch_start": fetch_start.isoformat(),
        "fetch_end": end.isoformat(),
        "sdk_version": "1.51.0",
        "top10_figis_count": len(figis),
        "ok_count": sum(1 for c in coverage if c["status"] == "ok"),
        "error_count": len(errors),
        "resume_count": sum(1 for c in coverage if c["status"] == "skipped_resume"),
        "total_requests": sum(c["requests"] for c in coverage),
        "total_received": sum(c["received"] for c in coverage),
        "total_saved": sum(c["saved"] for c in coverage),
        "total_skipped_incomplete": sum(c["skipped_incomplete"] for c in coverage),
        "limitations": [
            "5-мин: макс. период одного запроса — 7 дней (недельная пагинация).",
            "Только FIGI из rolling TOP-10 (объединение за период).",
            "is_complete=False исключены.",
        ],
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log.info(f"[intraday] manifest: {MANIFEST_FILE}")
    log.info(f"[intraday] Готово. OK={manifest['ok_count']}, errors={manifest['error_count']}, "
             f"requests={manifest['total_requests']}, saved={manifest['total_saved']}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="Tsclp_v2.1_volatile — загрузчик (A/B)")
    parser.add_argument("--stage", choices=["daily", "intraday", "audit"], default="daily")
    parser.add_argument("--start", default="2025-11-10")
    parser.add_argument("--end", default="2026-11-10")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.stage == "daily":
        asyncio.run(stage_daily(args))
    elif args.stage == "intraday":
        asyncio.run(stage_intraday(args))
    elif args.stage == "audit":
        log.info("[audit] Используйте --stage daily/intraday для загрузки, audit — отдельно.")


if __name__ == "__main__":
    main()