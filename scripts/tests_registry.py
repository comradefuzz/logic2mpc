#!/usr/bin/env python3
"""Реестр тестов общего набора: `tests/registry.tsv`. Правила: docs/testing.md.

    tests_registry.py check    реестр совпадает с набором, у строк есть причины, тестов спайков нет
    tests_registry.py audit    актуализация: прогон с замерами, пропуски, медленные тесты, тесты с оценкой «высокий»

`check` быстрый (сбор без прогона) и запускается Stop-хуком.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "tests" / "registry.tsv"
COLUMNS = (
    "test", "essence", "suite", "value", "value_note", "added_for", "reason_added", "status", "removed_reason",
)
VALUES = {"низкий", "средний", "высокий"}
STATUSES = {"active", "removed"}
FORBIDDEN_PREFIXES = ("spikes/", "story_tests/")
BUDGET_SECONDS = 150
SLOW_SECONDS = 2.0


def python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def read_registry() -> list[dict[str, str]]:
    lines = [x for x in REGISTRY.read_text(encoding="utf-8").splitlines() if x.strip()]
    if tuple(lines[0].split("\t")) != COLUMNS:
        raise ValueError("tests/registry.tsv: неверная шапка")
    return [dict(zip(COLUMNS, (line.split("\t") + [""] * len(COLUMNS))[: len(COLUMNS)])) for line in lines[1:]]


def collect() -> list[str]:
    """Функции общего набора (без параметров), в порядке сбора."""
    result = subprocess.run([python(), "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    found: list[str] = []
    for line in result.stdout.splitlines():
        if "::" in line:
            name = re.sub(r"\[.*\]$", "", line.strip())
            if name not in found:
                found.append(name)
    return found


def check() -> list[str]:
    errors: list[str] = []
    rows = read_registry()
    seen: dict[str, str] = {}
    for number, row in enumerate(rows, 2):
        where = f"registry.tsv:{number} {row['test']}"
        if row["test"] in seen:
            errors.append(f"{where}: повтор")
        seen[row["test"]] = row["status"]
        if row["status"] not in STATUSES:
            errors.append(f"{where}: статус {row['status']!r}, нужен active или removed")
            continue
        if row["status"] == "active":
            if row["test"].startswith(FORBIDDEN_PREFIXES):
                errors.append(f"{where}: тесты спайков и стори в реестр общего набора не входят")
            for field in ("essence", "value", "reason_added", "added_for"):
                if not row[field]:
                    errors.append(f"{where}: пустое поле {field}")
            if row["value"] not in VALUES:
                errors.append(f"{where}: оценка {row['value']!r}, нужна одна из {sorted(VALUES)}")
        elif not row["removed_reason"]:
            errors.append(f"{where}: удалённый тест без причины удаления")
    collected = collect()
    active = {r["test"] for r in rows if r["status"] == "active"}
    errors += [f"{t}: тест есть в наборе, но не внесён в реестр" for t in collected if t not in active]
    errors += [f"{t}: в реестре active, но в наборе нет: пометить removed с причиной" for t in sorted(active - set(collected))]
    for path in (ROOT / "spikes").rglob("test_*.py"):
        errors.append(f"{path.relative_to(ROOT)}: тесты спайков запрещены, нужные в ходе спайка лежат в story_tests/")
    return errors


def audit() -> int:
    errors = check()
    print(f"check: {'ошибок нет' if not errors else str(len(errors)) + ' ошибок'}")
    result = subprocess.run(
        [python(), "-m", "pytest", "-q", "-rs", "--durations=15", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True,
    )
    text = result.stdout
    total = re.search(r"in ([\d.]+)s", text)
    seconds = float(total.group(1)) if total else 0.0
    print(f"прогон: {seconds:.0f} с при бюджете {BUDGET_SECONDS} с{' (ПРЕВЫШЕН)' if seconds > BUDGET_SECONDS else ''}")
    slow = [m for m in re.findall(r"^([\d.]+)s (?:call|setup|teardown)\s+(\S+)", text, re.M) if float(m[0]) > SLOW_SECONDS]
    for duration, name in slow:
        print(f"медленный (> {SLOW_SECONDS:.0f} с): {duration} с {name}")
    skipped = re.findall(r"^SKIPPED \[(\d+)\] (.+)$", text, re.M)
    for count, reason in skipped:
        print(f"пропущено {count}: {reason[:120]}")
    for row in read_registry():
        if row["status"] == "active" and row["value"] == "высокий":
            print(f"оценка «высокий»: {row['test']}: {row['value_note']}")
    for error in errors:
        print(f"ОШИБКА: {error}")
    return 0 if not errors and seconds <= BUDGET_SECONDS else 1


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "check":
        errors = check()
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0
    if command == "audit":
        return audit()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
