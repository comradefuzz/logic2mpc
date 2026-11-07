#!/usr/bin/env python3
"""Контроль качества по уровням. Правила: docs/testing.md.

    gate.py sanity   формат базы знаний и стори, реестр тестов, синтаксис и импорт кода (секунды)
    gate.py commit   sanity и smoke-тесты, smoke только если в индексе есть код или тесты (для коммита)
    gate.py dev      sanity и тесты областей, затронутых изменениями (build, web, core, tools), для цикла разработки
    gate.py full     sanity и полный общий набор (для /approve и /accept); один прогон на состояние кода:
                     если набор уже зелёный для текущего состояния (штамп), прогон пропускается
    gate.py full --force   полный набор без учёта штампа

Код возврата не 0, если уровень не пройден.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIXES = (".py",)
CODE_FILES = ("pytest.ini", "requirements.txt", "tests/registry.tsv")
CODE_PREFIXES = ("logic2mpc/spec/",)
AREA_PATHS = {
    "build": ("logic2mpc/adapters/xpj", "logic2mpc/adapters/mpcfile", "logic2mpc/spec/", "docs/contracts/", "scripts/build_spec.py",
              "tests/test_xpj_spec.py", "tests/test_export.py", "tests/test_mpcfile.py", "tests/test_overview.py"),
    "web": ("logic2mpc/adapters/web.py", "logic2mpc/web/"),
    "core": ("logic2mpc/core/", "logic2mpc/adapters/logic", "tests/test_analysis.py", "tests/test_edit.py", "tests/test_groups.py",
             "tests/test_real_project.py", "tests/test_session.py", "tests/test_start.py"),
    "tools": ("scripts/", "pytest.ini", "conftest.py"),
}
ALL_AREAS = ("build", "web", "core", "tools")
STAMP = ROOT / ".gate_full_ok"
STAMP_EXCLUDE = ("story_tests/", "spikes/")


def python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def run(*args: str) -> int:
    return subprocess.run([python(), *args], cwd=ROOT).returncode


def touches_code(paths: list[str]) -> bool:
    """Нужны ли тесты: изменён код, тесты, описание формата для экспорта или конфигурация набора."""
    return any(p.endswith(CODE_SUFFIXES) or p in CODE_FILES or p.startswith(CODE_PREFIXES) for p in paths)


def areas_for(paths: list[str]) -> set[str]:
    """Области, которых касаются изменения. Код вне известных путей (например app.py) затрагивает все области."""
    found: set[str] = set()
    for path in paths:
        if not touches_code([path]):
            continue
        matched = {area for area, prefixes in AREA_PATHS.items() if path.startswith(prefixes)}
        found |= matched or set(ALL_AREAS)
    return found


def changed() -> list[str]:
    result = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    return [line[3:].split(" -> ")[-1] for line in result.stdout.splitlines() if line]


def staged() -> list[str]:
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def fingerprint(paths: list[str], read=lambda p: (ROOT / p).read_bytes()) -> str:
    """Хеш состояния, от которого зависит результат общего набора: код, тесты, спека, конфигурация."""
    digest = hashlib.sha256()
    for path in sorted(p for p in paths if touches_code([p]) and not p.startswith(STAMP_EXCLUDE)):
        digest.update(path.encode())
        digest.update(read(path))
    return digest.hexdigest()


def tracked_and_new() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line and (ROOT / line).is_file()]


def stamped() -> str | None:
    return STAMP.read_text().split()[0] if STAMP.is_file() and STAMP.read_text().split() else None


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
    if level not in {"sanity", "commit", "dev", "full"}:
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
    if level == "dev":
        areas = sorted(areas_for(changed()), key=ALL_AREAS.index)
        if not areas:
            print("dev: код не менялся, тесты не нужны")
            return 0
        print(f"dev: области {', '.join(areas)}")
        if run("-m", "pytest", "-q", "-m", " or ".join(areas)):
            print("Тесты областей красные.", file=sys.stderr)
            return 1
    if level == "full":
        state = fingerprint(tracked_and_new())
        if "--force" not in sys.argv and stamped() == state:
            print("full: набор уже зелёный для этого состояния кода (штамп), прогон пропущен; --force запускает заново")
            return 0
        if run("-m", "pytest", "-q"):
            print("Полный набор красный.", file=sys.stderr)
            return 1
        STAMP.write_text(f"{state} {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
