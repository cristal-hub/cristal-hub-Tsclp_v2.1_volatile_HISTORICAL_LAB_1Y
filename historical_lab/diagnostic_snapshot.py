# historical_lab/diagnostic_snapshot.py
# Tsclp_v2.1_volatile — ЭТАП A: диагностический снимок исходников.
#
# ЧТО ДЕЛАЕТ:
#   1. Читает исходники как ТЕКСТ (не импорт).
#   2. Считает SHA256.
#   3. Извлекает сигнатуры, константы, параметры, схему использования StrategyManager.
#   4. Проверяет потенциальную утечку ADX-гистерезиса между инструментами.
#   5. Пишет подробный отчёт в historical_lab/_snapshot/DIAGNOSTIC_REPORT.md
#      и SHA256 в historical_lab/_snapshot/files_sha256.txt.
#
# ЧЕГО НЕ ДЕЛАЕТ:
#   - не импортирует торговые модули;
#   - не обращается к T-Invest API;
#   - не читает .env, токены, research_*.csv/jsonl, trading.flag;
#   - не перезаписывает существующие файлы (суффикс _2, _3);
#   - не отправляет заявки.
#
# RESEARCH ONLY. ONLY T-INVEST SANDBOX. NO LIVE ORDERS. NO REAL MONEY.

import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# --- Пути (при необходимости измените) ---
SOURCE_PROJECT = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile")
LAB_ROOT = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y")
SNAPSHOT_DIR = LAB_ROOT / "historical_lab" / "_snapshot"

FILES_TO_AUDIT = [
    "config.py",
    "strategy.py",
    "risk_manager.py",
    "screener.py",
    "main.py",
    "logger.py",
    "execution.py",
    "tinkoff_client.py",
    "requirements.txt",
]

# Файлы, которые НЕ читаем (секреты / данные / кеш)
FORBIDDEN = {
    ".env", "trading.flag",
    "research_trades.csv", "research_events.jsonl",
    "research_trades_pilot.csv", "research_events_pilot.jsonl",
}


def _safe_suffix_write(path: Path, content: str) -> Path:
    """Пишет файл, не перезаписывая: при коллизии добавляет _2, _3, ..."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
        return path
    stem = path.stem
    suffix = path.suffix
    i = 2
    while True:
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            candidate.write_text(content, encoding="utf-8")
            return candidate
        i += 1


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _extract_top_level_assignments(text: str) -> dict:
    """Извлекает `NAME = value` на верхнем уровне (без вложенности)."""
    result = {}
    for line in text.splitlines():
        if not line or line.startswith((" ", "\t", "#")):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*(?:#.*)?$", line)
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _extract_defs(text: str) -> list:
    """Сигнатуры def/async def (имя + аргументы) — regex, без выполнения."""
    defs = []
    for m in re.finditer(r"^(async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
                         text, re.MULTILINE):
        kind = "async" if m.group(1).startswith("async") else "sync"
        defs.append({
            "kind": kind,
            "name": m.group(2),
            "args": " ".join(m.group(3).split()),
        })
    return defs


def _extract_classes(text: str) -> list:
    return [m.group(1) for m in re.finditer(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE)]


def _extract_imports(text: str) -> list:
    imports = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("import ", "from ")):
            imports.append(s)
    return imports


def _find_strategy_manager_instantiations(main_text: str) -> list:
    """Ищет все `sm = StrategyManager()` / `StrategyManager()` в main.py."""
    matches = []
    for m in re.finditer(r"StrategyManager\s*\(\s*\)", main_text):
        start = max(0, m.start() - 80)
        end = min(len(main_text), m.end() + 20)
        snippet = main_text[start:end].replace("\n", " ")
        matches.append(snippet)
    return matches


def _check_adx_leak(main_text: str, strategy_text: str) -> dict:
    """
    Проверяет, один ли StrategyManager на процесс.
    Если да — _last_regime / _regime_streak общие для всех инструментов.
    Это ПОТЕНЦИАЛЬНЫЙ баг: гистерезис ADX "перетекает" между инструментами.
    Фиксируем как WARNING, не воспроизводим.
    """
    instantiations = _find_strategy_manager_instantiations(main_text)
    stateful_fields = []
    for f in ("_last_regime", "_regime_streak",
              "_last_regime_candidate", "_last_regime_candle_time"):
        if re.search(rf"self\.{f}\s*=", strategy_text):
            stateful_fields.append(f)
    return {
        "instantiations_count": len(instantiations),
        "instantiations": instantiations,
        "stateful_fields_in_strategy": stateful_fields,
        "risk": (
            "WARNING: StrategyManager создаётся один раз (или несколько), "
            "но _last_regime / _regime_streak — атрибуты экземпляра. "
            "Если экземпляр ОДИН на все инструменты, ADX-гистерезис "
            "перетекает между тикерами. Это воспроизводить как есть "
            "(STRATEGY LOGIC: UNCHANGED), но задокументировать."
            if len(instantiations) == 1 and stateful_fields else
            "OK: либо несколько экземпляров, либо stateful-полей нет."
        ),
    }


def _check_drop_incomplete(main_text: str) -> dict:
    """Ищет `drop_incomplete=True/False` в main.py."""
    matches = re.findall(r"drop_incomplete\s*=\s*(True|False)", main_text)
    return {"values_found": matches}


def _check_candles_lookback(main_text: str, config_text: str) -> dict:
    """Ищет `CANDLES_LOOKBACK_DAYS` в main.py и значение в config.py."""
    uses = re.findall(r"CANDLES_LOOKBACK_DAYS", main_text)
    cfg = _extract_top_level_assignments(config_text).get("CANDLES_LOOKBACK_DAYS")
    return {"uses_in_main": len(uses), "config_value": cfg}


def _check_trade_fields(logger_text: str) -> list:
    """Извлекает TRADE_FIELDS из logger.py."""
    m = re.search(r"TRADE_FIELDS\s*=\s*\[(.*?)\]", logger_text, re.DOTALL)
    if not m:
        return []
    fields = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", m.group(1))
    return fields


def _check_execution_states(exec_text: str) -> list:
    """Извлекает значения PositionState из execution.py."""
    m = re.search(r"class PositionState\(str,\s*Enum\):\s*(.*?)(?=\nclass |\n\n\S)",
                  exec_text, re.DOTALL)
    if not m:
        return []
    return re.findall(r"^\s+([A-Z_]+)\s*=\s*['\"]([^'\"]+)['\"]", m.group(1), re.MULTILINE)


def _check_tracked_position_fields(exec_text: str) -> list:
    """Извлекает поля dataclass TrackedPosition."""
    m = re.search(r"@dataclass\s*class\s+TrackedPosition:(.*?)(?=\nclass |\n\n\S)",
                  exec_text, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    fields = []
    for line in body.splitlines():
        mm = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^=]+?)(?:\s*=\s*(.+))?$", line)
        if mm:
            fields.append({
                "name": mm.group(1),
                "type": mm.group(2).strip(),
                "default": (mm.group(3) or "").strip(),
            })
    return fields


def _check_screener_formula(screener_text: str) -> dict:
    """Извлекает формулу волатильности и константы скринера."""
    return {
        "REAL_EXCHANGE_MOEX": bool(re.search(r"REAL_EXCHANGE_MOEX\s*=\s*1", screener_text)),
        "uses_INSTRUMENT_STATUS_ALL": "INSTRUMENT_STATUS_ALL" in screener_text,
        "volatility_formula_present": "(atr / last_close) * 100" in screener_text,
        "atr_period_used": "config.ATR_PERIOD" in screener_text,
        "min_turnover_used": "MIN_DAILY_TURNOVER_RUB" in screener_text,
        "volatility_period_days_used": "VOLATILITY_PERIOD_DAYS" in screener_text,
    }


def _check_requirements(req_text: str) -> list:
    lines = []
    for line in req_text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return lines


def main():
    print("=" * 70)
    print("Tsclp_v2.1_volatile — ЭТАП A: диагностический снимок")
    print("=" * 70)

    if not SOURCE_PROJECT.is_dir():
        print(f"[ERROR] Исходный проект не найден: {SOURCE_PROJECT}")
        sys.exit(1)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Чтение файлов ---
    texts = {}
    hashes = {}
    missing = []
    for name in FILES_TO_AUDIT:
        p = SOURCE_PROJECT / name
        if not p.is_file():
            missing.append(name)
            continue
        texts[name] = _read_text(p)
        hashes[name] = _sha256(texts[name])

    # --- Аудит ---
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_project": str(SOURCE_PROJECT),
        "lab_root": str(LAB_ROOT),
        "files_audited": list(texts.keys()),
        "files_missing": missing,
        "sha256": hashes,
    }

    cfg = texts.get("config.py", "")
    st = texts.get("strategy.py", "")
    rm = texts.get("risk_manager.py", "")
    sc = texts.get("screener.py", "")
    mn = texts.get("main.py", "")
    lg = texts.get("logger.py", "")
    ex = texts.get("execution.py", "")
    tc = texts.get("tinkoff_client.py", "")
    rq = texts.get("requirements.txt", "")

    report["config_top_level"] = _extract_top_level_assignments(cfg)
    report["strategy_defs"] = _extract_defs(st)
    report["strategy_classes"] = _extract_classes(st)
    report["strategy_imports"] = _extract_imports(st)
    report["risk_manager_defs"] = _extract_defs(rm)
    report["screener_defs"] = _extract_defs(sc)
    report["main_defs"] = _extract_defs(mn)
    report["main_imports"] = _extract_imports(mn)
    report["logger_trade_fields"] = _check_trade_fields(lg)
    report["execution_states"] = _check_execution_states(ex)
    report["tracked_position_fields"] = _check_tracked_position_fields(ex)
    report["tinkoff_client_defs"] = _extract_defs(tc)
    report["requirements"] = _check_requirements(rq)

    report["adx_leak_check"] = _check_adx_leak(mn, st)
    report["drop_incomplete_check"] = _check_drop_incomplete(mn)
    report["candles_lookback_check"] = _check_candles_lookback(mn, cfg)
    report["screener_formula_check"] = _check_screener_formula(sc)

    # --- Markdown-отчёт ---
    md = []
    md.append("# DIAGNOSTIC REPORT — ЭТАП A")
    md.append("")
    md.append(f"**Сгенерирован:** {report['generated_at_utc']}")
    md.append(f"**Источник (только чтение):** `{SOURCE_PROJECT}`")
    md.append(f"**Лаборатория (запись):** `{LAB_ROOT}`")
    md.append("")
    md.append("## SHA256 исходных файлов")
    md.append("")
    md.append("| Файл | SHA256 |")
    md.append("|---|---|")
    for name, h in hashes.items():
        md.append(f"| `{name}` | `{h}` |")
    if missing:
        md.append("")
        md.append("**Отсутствуют:** " + ", ".join(missing))
    md.append("")

    md.append("## config.py — верхнеуровневые параметры")
    md.append("")
    md.append("```")
    for k, v in report["config_top_level"].items():
        md.append(f"{k} = {v}")
    md.append("```")
    md.append("")

    md.append("## strategy.py — сигнатуры и классы")
    md.append("")
    md.append("**Классы:** " + ", ".join(report["strategy_classes"]))
    md.append("")
    md.append("| Тип | Имя | Аргументы |")
    md.append("|---|---|---|")
    for d in report["strategy_defs"]:
        md.append(f"| {d['kind']} | `{d['name']}` | `{d['args']}` |")
    md.append("")
    md.append("**Импорты:**")
    md.append("```")
    for imp in report["strategy_imports"]:
        md.append(imp)
    md.append("```")
    md.append("")

    md.append("## risk_manager.py — сигнатуры")
    md.append("")
    md.append("| Тип | Имя | Аргументы |")
    md.append("|---|---|---|")
    for d in report["risk_manager_defs"]:
        md.append(f"| {d['kind']} | `{d['name']}` | `{d['args']}` |")
    md.append("")

    md.append("## screener.py — сигнатуры и проверки")
    md.append("")
    md.append("| Тип | Имя | Аргументы |")
    md.append("|---|---|---|")
    for d in report["screener_defs"]:
        md.append(f"| {d['kind']} | `{d['name']}` | `{d['args']}` |")
    md.append("")
    md.append("**Проверки:**")
    md.append("```json")
    md.append(json.dumps(report["screener_formula_check"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")

    md.append("## main.py — сигнатуры и проверки")
    md.append("")
    md.append("| Тип | Имя | Аргументы |")
    md.append("|---|---|---|")
    for d in report["main_defs"]:
        md.append(f"| {d['kind']} | `{d['name']}` | `{d['args']}` |")
    md.append("")
    md.append("### Проверка ADX-гистерезиса (потенциальная утечка)")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report["adx_leak_check"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")
    md.append("### Проверка drop_incomplete")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report["drop_incomplete_check"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")
    md.append("### Проверка CANDLES_LOOKBACK_DAYS")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report["candles_lookback_check"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")

    md.append("## logger.py — TRADE_FIELDS")
    md.append("")
    md.append("```")
    md.append(", ".join(report["logger_trade_fields"]))
    md.append("```")
    md.append("")

    md.append("## execution.py — PositionState")
    md.append("")
    md.append("```")
    for name, val in report["execution_states"]:
        md.append(f"{name} = {val}")
    md.append("```")
    md.append("")
    md.append("### TrackedPosition — поля")
    md.append("")
    md.append("| Поле | Тип | По умолчанию |")
    md.append("|---|---|---|")
    for f in report["tracked_position_fields"]:
        md.append(f"| `{f['name']}` | `{f['type']}` | `{f['default']}` |")
    md.append("")

    md.append("## tinkoff_client.py — сигнатуры")
    md.append("")
    md.append("| Тип | Имя | Аргументы |")
    md.append("|---|---|---|")
    for d in report["tinkoff_client_defs"]:
        md.append(f"| {d['kind']} | `{d['name']}` | `{d['args']}` |")
    md.append("")

    md.append("## requirements.txt")
    md.append("")
    md.append("```")
    for line in report["requirements"]:
        md.append(line)
    md.append("```")
    md.append("")

    # --- Запись ---
    md_text = "\n".join(md)
    report_path = _safe_suffix_write(SNAPSHOT_DIR / "DIAGNOSTIC_REPORT.md", md_text)
    sha_path = _safe_suffix_write(
        SNAPSHOT_DIR / "files_sha256.txt",
        "\n".join(f"{h}  {n}" for n, h in hashes.items()) + "\n",
    )
    json_path = _safe_suffix_write(
        SNAPSHOT_DIR / "diagnostic_report.json",
        json.dumps(report, ensure_ascii=False, indent=2),
    )

    # --- Краткая сводка в PowerShell ---
    print()
    print(f"[OK] Файлов прочитано: {len(texts)}")
    if missing:
        print(f"[!] Отсутствуют: {', '.join(missing)}")
    print(f"[OK] PROFILE = {report['config_top_level'].get('PROFILE', '?')}")
    print(f"[OK] StrategyManager: найдено {report['adx_leak_check']['instantiations_count']} "
          f"созданий в main.py")
    print(f"[{'WARN' if 'WARNING' in report['adx_leak_check']['risk'] else 'OK'}] "
          f"ADX-гистерезис: см. отчёт")
    print(f"[OK] drop_incomplete: {report['drop_incomplete_check']['values_found'] or 'не найден'}")
    print(f"[OK] CANDLES_LOOKBACK_DAYS = {report['candles_lookback_check']['config_value']}")
    print()
    print(f"[OK] Подробный отчёт: {report_path}")
    print(f"[OK] SHA256: {sha_path}")
    print(f"[OK] JSON: {json_path}")
    print()
    print("Передайте отчёт в чат для анализа. Этап B не начинается до анализа.")


if __name__ == "__main__":
    main()