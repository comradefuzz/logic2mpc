#!/usr/bin/env python3
"""Контроль качества по уровням. Правила: docs/testing.md.

    gate.py sanity   формат базы знаний и стори, реестр тестов, синтаксис и импорт кода (секунды)
    gate.py commit   sanity и smoke-тесты, smoke только если в индексе есть код или тесты (для коммита)
    gate.py full     sanity и полный общий набор (для /approve и /accept)

Код возврата не 0, если уровень не пройден.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIXES = (".py",)
CODE_FILES = ("pytest.ini", "requirements.txt", "tests/registry.tsv")
CODE_PREFIXES = ("logic2mpc/spec/",)


def python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def run(*args: str) -> int:
    return subprocess.run([python(), *args], cwd=ROOT).returncode


def touches_code(paths: list[str]) -> bool:
    """Нужны ли тесты: изменён код, тесты, описание формата для экспорта или конфигурация набора."""
    return any(p.endswith(CODE_SUFFIXES) or p in CODE_FILES or p.startswith(CODE_PREFIXES) for p in paths)


def staged() -> list[str]:
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def sanity() -> int:
    steps = (
        ("формат базы знаний и стори", ("-B", "scripts/formats_check.py")),
        ("реестр тестов", ("-B", "scripts/tests_registry.py", "check")),
        ("синтаксис", ("-m", "compileall", "-q", "logic2mpc", "scripts")),
        ("импорт приложения", ("-c", "import logic2mpc.app, logic2mpc.adapters.xpj")),
    )
    for name, args in steps:
        if run(*args):
            print(f"sanity: не пройден шаг «{name}»", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    level = sys.argv[1] if len(sys.argv) > 1 else ""
    if level not in {"sanity", "commit", "full"}:
        print(__doc__)
        return 2
    if sanity():
        return 1
    if level == "commit":
        files = staged()
        if files and not touches_code(files):
            return 0
        if run("-m", "pytest", "-q", "-m", "smoke", "-x"):
            print("Коммит заблокирован: smoke-тесты красные.", file=sys.stderr)
            return 1
    if level == "full" and run("-m", "pytest", "-q"):
        print("Полный набор красный.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
