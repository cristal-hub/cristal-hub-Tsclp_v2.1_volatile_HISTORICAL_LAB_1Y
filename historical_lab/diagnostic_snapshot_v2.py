# historical_lab/diagnostic_snapshot_v2.py
# Tsclp_v2.1_volatile — ЭТАП A (v2): исправленный диагностический снимок.
#
# ИСПРАВЛЕНО:
#   - regex для def ловит методы классов (^\s*def);
#   - PositionState захватывает ВСЕ строки (включая OPEN);
#   - извлекаются тела calculate_sl_tp / calculate_position_size (формулы);
#   - извлекается последовательность вызовов в trading_cycle;
#   - проверяется, от какой цены считаются SL/TP (exec_price vs price);
#   - сверка SHA256 с предыдущим отчётом.
#
# ЧЕГО НЕ ДЕЛАЕТ:
#   - не импортирует торговые модули;
#   - не обращается к T-Invest API;
#   - не читает .env, токены, research_*.csv/jsonl, trading.flag;
#   - не перезаписывает существующие файлы (суффикс _2, _3);
#   - не отправляет заявки.
#
# RESEARCH ONLY. ONLY T-INVEST SANDBOX. NO LIVE ORDERS. NO REAL MONEY.

import hashlib
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

SOURCE_PROJECT = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile")
LAB_ROOT = Path(r"C:\Users\Cristal\Desktop\Tsclp_v2.1_volatile_HISTORICAL_LAB_1Y")
SNAPSHOT_DIR = LAB_ROOT / "historical_lab" / "_snapshot"

FILES_TO_AUDIT = [
    "config.py", "strategy.py", "risk_manager.py", "screener.py",
    "main.py", "logger.py", "execution.py", "tinkoff_client.py",
    "requirements.txt",
]


def _safe_suffix_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
        return path
    stem, suffix = path.stem, path.suffix
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
    result = {}
    for line in text.splitlines():
        if not line or line.startswith((" ", "\t", "#")):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*(?:#.*)?$", line)
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _extract_defs(text: str) -> list:
    """ИСПРАВЛЕНО: ловит методы классов (^\s*def)."""
    defs = []
    for m in re.finditer(r"^(\s*)(async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
                         text, re.MULTILINE):
        indent = len(m.group(1))
        kind = "async" if m.group(2).startswith("async") else "sync"
        defs.append({
            "kind": kind,
            "name": m.group(3),
            "args": " ".join(m.group(4).split()),
            "indent": indent,
            "is_method": indent > 0,
        })
    return defs


def _extract_classes(text: str) -> list:
    return [m.group(1) for m in re.finditer(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE)]


def _extract_imports(text: str) -> list:
    return [l.strip() for l in text.splitlines() if l.strip().startswith(("import ", "from "))]


def _extract_function_body(text: str, func_name: str, max_lines: int = 80) -> str:
    """Извлекает тело функции (до следующего def того же/меньшего отступа)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(async\s+def|def)\s+" + re.escape(func_name) + r"\s*\(", line)
        if not m:
            continue
        base_indent = len(m.group(1))
        body = [line]
        for j in range(i + 1, min(i + 1 + max_lines, len(lines))):
            nxt = lines[j]
            if nxt.strip() == "":
                body.append(nxt)
                continue
            nxt_indent = len(nxt) - len(nxt.lstrip())
            if nxt_indent <= base_indent and not nxt.strip().startswith(("#", "'", '"')):
                break
            body.append(nxt)
        return "\n".join(body)
    return ""


def _extract_sl_tp_call_sites(main_text: str) -> list:
    """Ищет все вызовы rm.calculate_sl_tp(...) и аргументы."""
    results = []
    for m in re.finditer(r"rm\.calculate_sl_tp\s*\(([^)]*)\)", main_text):
        results.append({
            "call": m.group(0),
            "args": " ".join(m.group(1).split()),
            "context_before": main_text[max(0, m.start() - 120):m.start()].strip().splitlines()[-3:],
        })
    return results


def _check_sl_tp_basis(main_text: str) -> dict:
    """
    Проверяет, от какой цены считаются SL/TP.
    Ищет: rm.calculate_sl_tp(X, signal, df), где X — exec_price или price.
    """
    calls = _extract_sl_tp_call_sites(main_text)
    basis = []
    for c in calls:
        args = c["args"]
        first_arg = args.split(",")[0].strip() if args else ""
        if "exec_price" in first_arg:
            basis.append({"arg": first_arg, "basis": "execution_price (фактическая)"})
        elif "price" in first_arg:
            basis.append({"arg": first_arg, "basis": "signal_price (цена сигнала)"})
        else:
            basis.append({"arg": first_arg, "basis": "UNKNOWN"})
    return {"calls": calls, "basis": basis}


def _extract_trading_cycle_sequence(main_text: str) -> list:
    """Извлекает последовательность вызовов в trading_cycle (упрощённо)."""
    body = _extract_function_body(main_text, "trading_cycle", max_lines=200)
    if not body:
        return []
    seq = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # Ищем вызовы вида await X.y(...) или X.y(...)
        m = re.match(r"(?:await\s+)?([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\(", s)
        if m:
            seq.append(m.group(1))
        elif re.match(r"(?:await\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(", s):
            mm = re.match(r"(?:await\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(", s)
            if mm:
                seq.append(mm.group(1))
    return seq


def _extract_commission_formulas(main_text: str, risk_text: str) -> dict:
    """Извлекает точные строки формул комиссии и проскальзывания."""
    formulas = {"main": [], "risk_manager": []}
    for line in main_text.splitlines():
        s = line.strip()
        if any(k in s for k in ("commission", "slippage", "friction", "turnover")):
            if "=" in s and not s.startswith("#"):
                formulas["main"].append(s)
    for line in risk_text.splitlines():
        s = line.strip()
        if any(k in s for k in ("commission", "slippage", "friction", "risk_amount", "per_share_risk")):
            if "=" in s and not s.startswith("#"):
                formulas["risk_manager"].append(s)
    return formulas


def _extract_position_states(exec_text: str) -> list:
    """ИСПРАВЛЕНО: захватывает ВСЕ строки класса PositionState, включая OPEN."""
    m = re.search(r"class\s+PositionState\s*\([^)]*\):\s*\n((?:\s+.+\n)+)", exec_text)
    if not m:
        return []
    states = []
    for line in m.group(1).splitlines():
        mm = re.match(r"^\s+([A-Z_][A-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]", line)
        if mm:
            states.append({"name": mm.group(1), "value": mm.group(2)})
    return states


def _extract_tracked_position_fields(exec_text: str) -> list:
    m = re.search(r"@dataclass\s*\nclass\s+TrackedPosition:(.*?)(?=\nclass |\n\n\S|\Z)",
                  exec_text, re.DOTALL)
    if not m:
        return []
    fields = []
    for line in m.group(1).splitlines():
        mm = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^=]+?)(?:\s*=\s*(.+))?$", line)
        if mm:
            fields.append({
                "name": mm.group(1),
                "type": mm.group(2).strip(),
                "default": (mm.group(3) or "").strip(),
            })
    return fields


def _check_trade_fields(logger_text: str) -> list:
    m = re.search(r"TRADE_FIELDS\s*=\s*\[(.*?)\]", logger_text, re.DOTALL)
    if not m:
        return []
    return re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", m.group(1))


def _check_screener_formula(screener_text: str) -> dict:
    return {
        "REAL_EXCHANGE_MOEX": bool(re.search(r"REAL_EXCHANGE_MOEX\s*=\s*1", screener_text)),
        "uses_INSTRUMENT_STATUS_ALL": "INSTRUMENT_STATUS_ALL" in screener_text,
        "volatility_formula_present": "(atr / last_close) * 100" in screener_text,
        "atr_period_used": "config.ATR_PERIOD" in screener_text,
        "min_turnover_used": "MIN_DAILY_TURNOVER_RUB" in screener_text,
        "volatility_period_days_used": "VOLATILITY_PERIOD_DAYS" in screener_text,
    }


def _check_requirements(req_text: str) -> list:
    return [s.strip() for s in req_text.splitlines()
            if s.strip() and not s.strip().startswith("#")]


def _find_strategy_manager_instantiations(main_text: str) -> list:
    return [m.group(0) for m in re.finditer(r"StrategyManager\s*\(\s*\)", main_text)]


def _check_adx_leak(main_text: str, strategy_text: str) -> dict:
    instantiations = _find_strategy_manager_instantiations(main_text)
    stateful_fields = [f for f in ("_last_regime", "_regime_streak",
                                   "_last_regime_candidate", "_last_regime_candidate")
                       if re.search(rf"self\.{f}\s*=", strategy_text)]
    return {
        "instantiations_count": len(instantiations),
        "stateful_fields_in_strategy": stateful_fields,
        "risk": (
            "WARNING: один StrategyManager на процесс → ADX-гистерезис "
            "перетекает между тикерами. Воспроизводить как есть (Q1=A), "
            "задокументировать; дополнительно — диагностическое сравнение "
            "с изолированным StrategyManager (Q1 доп.)."
            if len(instantiations) == 1 and stateful_fields else
            "OK: либо несколько экземпляров, либо stateful-полей нет."
        ),
    }


def _check_drop_incomplete(main_text: str) -> dict:
    return {"values_found": re.findall(r"drop_incomplete\s*=\s*(True|False)", main_text)}


def _check_candles_lookback(main_text: str, config_text: str) -> dict:
    uses = re.findall(r"CANDLES_LOOKBACK_DAYS", main_text)
    cfg = _extract_top_level_assignments(config_text).get("CANDLES_LOOKBACK_DAYS")
    return {"uses_in_main": len(uses), "config_value": cfg}


def _compare_sha256_with_previous(hashes: dict) -> dict:
    """Сверяет SHA256 с предыдущим files_sha256.txt (если есть)."""
    prev_path = SNAPSHOT_DIR / "files_sha256.txt"
    if not prev_path.is_file():
        return {"status": "no_previous_report", "changes": {}}
    changes = {}
    try:
        for line in prev_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2:
                prev_hash, prev_name = parts
                if prev_name in hashes:
                    changes[prev_name] = {
                        "prev": prev_hash,
                        "curr": hashes[prev_name],
                        "same": prev_hash == hashes[prev_name],
                    }
    except Exception as e:
        return {"status": f"error: {e}", "changes": {}}
    return {"status": "compared", "changes": changes}


def main():
    print("=" * 70)
    print("Tsclp_v2.1_volatile — ЭТАП A (v2): исправленный снимок")
    print("=" * 70)

    if not SOURCE_PROJECT.is_dir():
        print(f"[ERROR] Исходный проект не найден: {SOURCE_PROJECT}")
        sys.exit(1)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    texts, hashes, missing = {}, {}, []
    for name in FILES_TO_AUDIT:
        p = SOURCE_PROJECT / name
        if not p.is_file():
            missing.append(name)
            continue
        texts[name] = _read_text(p)
        hashes[name] = _sha256(texts[name])

    cfg = texts.get("config.py", "")
    st = texts.get("strategy.py", "")
    rm = texts.get("risk_manager.py", "")
    sc = texts.get("screener.py", "")
    mn = texts.get("main.py", "")
    lg = texts.get("logger.py", "")
    ex = texts.get("execution.py", "")
    tc = texts.get("tinkoff_client.py", "")
    rq = texts.get("requirements.txt", "")

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_project": str(SOURCE_PROJECT),
        "lab_root": str(LAB_ROOT),
        "files_audited": list(texts.keys()),
        "files_missing": missing,
        "sha256": hashes,
        "sha256_comparison": _compare_sha256_with_previous(hashes),
        "config_top_level": _extract_top_level_assignments(cfg),
        "strategy_defs": _extract_defs(st),
        "strategy_classes": _extract_classes(st),
        "risk_manager_defs": _extract_defs(rm),
        "screener_defs": _extract_defs(sc),
        "main_defs": _extract_defs(mn),
        "tinkoff_client_defs": _extract_defs(tc),
        "sl_tp_body": _extract_function_body(rm, "calculate_sl_tp", max_lines=60),
        "position_size_body": _extract_function_body(rm, "calculate_position_size", max_lines=120),
        "sl_tp_call_sites": _extract_sl_tp_call_sites(mn),
        "sl_tp_basis": _check_sl_tp_basis(mn),
        "trading_cycle_sequence": _extract_trading_cycle_sequence(mn),
        "commission_formulas": _extract_commission_formulas(mn, rm),
        "position_states": _extract_position_states(ex),
        "tracked_position_fields": _extract_tracked_position_fields(ex),
        "trade_fields": _check_trade_fields(lg),
        "screener_formula_check": _check_screener_formula(sc),
        "requirements": _check_requirements(rq),
        "adx_leak_check": _check_adx_leak(mn, st),
        "drop_incomplete_check": _check_drop_incomplete(mn),
        "candles_lookback_check": _check_candles_lookback(mn, cfg),
    }

    # --- Markdown ---
    md = ["# DIAGNOSTIC REPORT v2 — ЭТАП A", "",
          f"**Сгенерирован:** {report['generated_at_utc']}",
          f"**Источник:** `{SOURCE_PROJECT}`",
          f"**Лаборатория:** `{LAB_ROOT}`", ""]

    md.append("## SHA256 и сверка с предыдущим отчётом")
    md.append("")
    md.append("| Файл | SHA256 | Изменён? |")
    md.append("|---|---|---|")
    changes = report["sha256_comparison"].get("changes", {})
    for name, h in hashes.items():
        ch = changes.get(name)
        if ch is None:
            changed = "—"
        elif ch["same"]:
            changed = "нет"
        else:
            changed = "**ДА**"
        md.append(f"| `{name}` | `{h}` | {changed} |")
    md.append("")
    if missing:
        md.append("**Отсутствуют:** " + ", ".join(missing))
        md.append("")

    md.append("## config.py — параметры")
    md.append("")
    md.append("```")
    for k, v in report["config_top_level"].items():
        md.append(f"{k} = {v}")
    md.append("```")
    md.append("")

    for section, key in [
        ("strategy.py", "strategy_defs"),
        ("risk_manager.py", "risk_manager_defs"),
        ("screener.py", "screener_defs"),
        ("main.py", "main_defs"),
        ("tinkoff_client.py", "tinkoff_client_defs"),
    ]:
        md.append(f"## {section} — сигнатуры (включая методы классов)")
        md.append("")
        md.append("| Тип | Метод? | Имя | Аргументы |")
        md.append("|---|---|---|---|")
        for d in report[key]:
            md.append(f"| {d['kind']} | {'да' if d['is_method'] else 'нет'} | `{d['name']}` | `{d['args']}` |")
        md.append("")

    md.append("## PositionState — ВСЕ состояния (ИСПРАВЛЕНО)")
    md.append("")
    md.append("| Имя | Значение |")
    md.append("|---|---|")
    for s in report["position_states"]:
        md.append(f"| `{s['name']}` | `{s['value']}` |")
    md.append("")

    md.append("## TrackedPosition — поля")
    md.append("")
    md.append("| Поле | Тип | По умолчанию |")
    md.append("|---|---|---|")
    for f in report["tracked_position_fields"]:
        md.append(f"| `{f['name']}` | `{f['type']}` | `{f['default']}` |")
    md.append("")

    md.append("## logger.py — TRADE_FIELDS")
    md.append("")
    md.append("```")
    md.append(", ".join(report["trade_fields"]))
    md.append("```")
    md.append("")

    md.append("## ⚠️ КЛЮЧЕВОЕ: от какой цены считаются SL/TP")
    md.append("")
    md.append("### Тело `calculate_sl_tp` в risk_manager.py")
    md.append("")
    md.append("```python")
    md.append(report["sl_tp_body"] or "<!-- не извлечено -->")
    md.append("```")
    md.append("")
    md.append("### Вызовы `rm.calculate_sl_tp(...)` в main.py")
    md.append("")
    for c in report["sl_tp_call_sites"]:
        md.append(f"- `{c['call']}`")
        md.append(f"  - args: `{c['args']}`")
        md.append(f"  - context: `{c['context_before']}`")
    md.append("")
    md.append("### Базис SL/TP (от какой цены)")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report["sl_tp_basis"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")

    md.append("## Тело `calculate_position_size` (фрагменты)")
    md.append("")
    md.append("```python")
    md.append(report["position_size_body"] or "<!-- не извлечено -->")
    md.append("```")
    md.append("")

    md.append("## Формулы комиссии и проскальзывания")
    md.append("")
    md.append("### main.py")
    md.append("```python")
    for line in report["commission_formulas"]["main"]:
        md.append(line)
    md.append("```")
    md.append("")
    md.append("### risk_manager.py")
    md.append("```python")
    for line in report["commission_formulas"]["risk_manager"]:
        md.append(line)
    md.append("```")
    md.append("")

    md.append("## Последовательность вызовов в trading_cycle (main.py)")
    md.append("")
    md.append("```")
    for i, call in enumerate(report["trading_cycle_sequence"], 1):
        md.append(f"{i}. {call}")
    md.append("```")
    md.append("")

    md.append("## screener — проверки")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report["screener_formula_check"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")

    md.append("## ADX-гистерезис")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report["adx_leak_check"], ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")

    md.append("## drop_incomplete / CANDLES_LOOKBACK_DAYS")
    md.append("")
    md.append("```json")
    md.append(json.dumps({
        "drop_incomplete": report["drop_incomplete_check"],
        "candles_lookback": report["candles_lookback_check"],
    }, ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")

    md.append("## requirements.txt")
    md.append("")
    md.append("```")
    for line in report["requirements"]:
        md.append(line)
    md.append("```")
    md.append("")

    md_text = "\n".join(md)
    report_path = _safe_suffix_write(SNAPSHOT_DIR / "DIAGNOSTIC_REPORT_v2.md", md_text)
    sha_path = _safe_suffix_write(SNAPSHOT_DIR / "files_sha256_v2.txt",
                                  "\n".join(f"{h}  {n}" for n, h in hashes.items()) + "\n")
    json_path = _safe_suffix_write(SNAPSHOT_DIR / "diagnostic_report_v2.json",
                                   json.dumps(report, ensure_ascii=False, indent=2))

    # --- Краткая сводка в PowerShell ---
    print()
    print(f"[OK] Файлов прочитано: {len(texts)}")
    if missing:
        print(f"[!] Отсутствуют: {', '.join(missing)}")
    changed_files = [n for n, ch in changes.items() if not ch["same"]]
    if changed_files:
        print(f"[!] Изменены с прошлого отчёта: {', '.join(changed_files)}")
    else:
        print("[OK] SHA256 совпадает с прошлым отчётом (или прошлого нет)")
    print(f"[OK] PROFILE = {report['config_top_level'].get('PROFILE', '?')}")
    print(f"[OK] StrategyManager: {report['adx_leak_check']['instantiations_count']} созданий")
    print(f"[OK] drop_incomplete: {report['drop_incomplete_check']['values_found']}")
    print(f"[OK] CANDLES_LOOKBACK_DAYS = {report['candles_lookback_check']['config_value']}")
    print()
    print(f"[KEY] SL/TP базис: {report['sl_tp_basis']['basis']}")
    print()
    print(f"[OK] Подробный отчёт: {report_path}")
    print(f"[OK] SHA256: {sha_path}")
    print(f"[OK] JSON: {json_path}")
    print()
    print("Передайте отчёт в чат. Этап B не начинается до анализа.")


if __name__ == "__main__":
    main()